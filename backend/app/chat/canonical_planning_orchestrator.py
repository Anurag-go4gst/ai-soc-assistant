"""Canonical planning orchestration — lane, completeness, gap resolution, final planner."""

from __future__ import annotations

from typing import Any

from app.chat.canonical_handoff_builder import build_canonical_planning_input, new_handoff_id
from app.chat.canonical_query_to_intent_resume import (
    normalize_resume_answer_goal,
    resume_answer_goal_for_skill,
)
from app.chat.canonical_handoff_store import (
    CanonicalHandoffRecord,
    save_clarification_handoff,
    save_handoff,
)
from app.chat.contracts.canonical_planning_outcome import (
    clarification_outcome,
    planned_outcome,
    policy_blocked_outcome,
)
from app.chat.contracts.gap_resolution import FieldProvenance
from app.chat.guided_detail_resolution import run_guided_detail_resolution
from app.chat.intent_classifier import build_query_to_intent
from app.chat.intent_family_defaults import build_known_path_intent_stub, build_t0_knowledge_stub
from app.chat.known_detail_completion import evaluate_known_detail_completion
from app.chat.lane_router import is_known_catalogue_match, lane_for_match_path
from app.chat.canonical_policy_boundary import resolve_canonical_policy_block_reason
from app.chat.plan_evidence_from_canonical import plan_evidence_from_canonical
from app.chat.planning_telemetry import (
    emit_clarification_requested,
    emit_guided_resolution_started,
    emit_handoff_persisted,
    emit_handoff_resumed,
    emit_known_completeness_evaluated,
    emit_lane_router_decided,
    emit_planning_event,
    emit_post_guided_completeness_evaluated,
    emit_tier_resolved,
)
from app.chat.post_guided_completeness import evaluate_post_guided_completeness
from app.chat.query_signals import extract_query_signals
from app.chat.reference_qualification import extract_reference_ids, qualify_reference_query

ChatPipelineState = dict[str, Any]

#: Deterministic clarification phrasing per unresolved field. The outcome contract
#: requires a non-empty question, so a missing entry falls back to the generic form
#: rather than emitting an empty prompt.
_FIELD_QUESTIONS: dict[str, str] = {
    "host": "Which host should I scope this investigation to?",
    "hostname": "Which host should I scope this investigation to?",
    "user": "Which user account should I scope this investigation to?",
    "username": "Which user account should I scope this investigation to?",
    "alert_id": "Which alert ID should I investigate?",
    "time_range": "What time range should I use for this investigation?",
    "index": "Which index should I search?",
    "sourcetype": "Which sourcetype should I search?",
    "ip": "Which IP address should I scope this investigation to?",
    "source_ip": "Which source IP address should I scope this investigation to?",
}


def _primary_goal(intent: dict[str, Any]) -> str | None:
    """First declared answer goal — downstream reads ``answer_goal_primary``."""
    existing = intent.get("answer_goal_primary")
    if existing:
        return str(existing)
    goals = intent.get("answer_goal") or []
    return str(goals[0]) if goals else None


def build_clarification_question(unresolved_fields: list[str]) -> str:
    """Deterministic question text for the first unresolved field."""
    for field in unresolved_fields:
        question = _FIELD_QUESTIONS.get(str(field).strip().lower())
        if question:
            return question
    if unresolved_fields:
        joined = ", ".join(str(field) for field in unresolved_fields)
        return f"I need more detail before planning this investigation. Please provide: {joined}."
    return "I need more detail before planning this investigation. What should I scope it to?"


def run_canonical_planning(state: ChatPipelineState) -> ChatPipelineState:
    """Single shared canonical planning seam for imperative and RP entry points.

    Owns lane routing, completeness, intent classification, canonical planning,
    route resolution, and planning_decision projection. Both production runtimes
    must call this callable — not a duplicated node sequence.
    """
    from app.chat.canonical_handoff_repository import HandoffPersistenceError
    from app.chat.canonical_mode import build_persistence_failed_state
    from app.chat.pipeline import (  # circular: pipeline state nodes
        _graph_node_planning_decision_from_canonical,
        graph_node_route_contract,
        graph_node_route_resolution,
    )

    try:
        state = graph_node_lane_and_canonical_planning(state)
        from app.chat.canonical_outcome_gate import enforce_canonical_outcome_invariant

        state = enforce_canonical_outcome_invariant(state)
        state = graph_node_route_resolution(state)
        state = graph_node_route_contract(state)
        state = _graph_node_planning_decision_from_canonical(state)
        return state
    except HandoffPersistenceError as exc:
        return build_persistence_failed_state(
            state,
            reason=exc.reason,
            detail=exc.detail,
            category="database",
        )


def graph_node_lane_and_canonical_planning(state: ChatPipelineState) -> ChatPipelineState:
    """Lane router → completeness/guided resolution → canonical handoff → final planner."""
    request = state["request"]
    query = state.get("effective_query") or request.message
    qu = state.get("query_understanding")
    routed = dict(state.get("routed") or {})
    trace_id = state.get("trace_id")
    session_id = state.get("session_id")
    match_path = str(getattr(qu, "deterministic_match_path", "") or "out_of_registry")

    state = emit_planning_event(
        state,
        event="query_understanding.completed",
        node_name="understand_query",
        decision_reason="query_understanding_completed",
        payload={
            "trace_id": trace_id,
            "match_path": match_path,
            "normalized_query": str(getattr(qu, "normalized_query", query) or query),
        },
    ) or state

    resume = state.get("handoff_resume")
    handoff_id = new_handoff_id()
    handoff_version = 1
    resumed_record: CanonicalHandoffRecord | None = None
    if isinstance(resume, dict) and resume.get("handoff_id"):
        from app.chat.canonical_handoff_resumption import (
            ClarificationResumeError,
            resume_clarification_handoff,
        )
        from app.chat.canonical_mode import build_canonical_failure_state

        try:
            resume_result = resume_clarification_handoff(
                handoff_id=str(resume["handoff_id"]),
                handoff_version=int(resume.get("handoff_version") or 1),
                user_answer=str(resume.get("user_answer") or query),
                session_id=str(session_id) if session_id else None,
                trace_id=str(trace_id) if trace_id else None,
            )
        except ClarificationResumeError as exc:
            return build_canonical_failure_state(
                state,
                outcome="resolution_failed",
                reason=exc.reason,
                detail=exc.detail,
            )
        resumed_record = resume_result.record
        handoff_id = resumed_record.handoff_id
        handoff_version = resumed_record.handoff_version
        state = emit_handoff_resumed(
            state,
            handoff_id=handoff_id,
            handoff_version=handoff_version,
            prior_handoff_version=int(resume.get("handoff_version") or handoff_version - 1),
            idempotent_replay=resume_result.idempotent_replay,
            trace_id=str(trace_id) if trace_id else None,
            session_id=str(session_id) if session_id else None,
        ) or state
        query = str(resumed_record.original_query or query)
        match_path = str(
            (resume_result.merged_canonical.get("routing") or {}).get("match_path") or match_path
        )

    initial, resolved, lane = lane_for_match_path(match_path)
    if resumed_record is not None:
        initial = str(resumed_record.initial_tier or initial)
        resolved = str(resumed_record.resolved_tier or resolved)
        lane = str((resumed_record.canonical_planning_input or {}).get("routing", {}).get("processing_lane") or lane)

    state = emit_lane_router_decided(
        state,
        trace_id=str(trace_id) if trace_id else None,
        match_path=match_path,
        initial_tier=initial,
        resolved_tier=resolved,
        processing_lane=lane,
        route_reason="handoff_resume" if resumed_record else "initial_route",
    ) or state

    gap = None
    completeness = None
    intent_classification: dict[str, Any] | None = None
    query_to_intent: dict[str, Any] | None = state.get("query_to_intent")
    processing_lane = lane
    resolved_tier = resolved
    known_query_to_intent_built = False
    route_reason = "handoff_resume" if resumed_record else ""

    use_case_id = None
    selected_use_case = state.get("selected_use_case")
    if selected_use_case is not None:
        use_case_id = getattr(selected_use_case, "use_case_id", None)
    if not use_case_id and qu is not None:
        mapped = getattr(qu, "mapped_use_case_ids", None)
        if isinstance(mapped, list) and mapped:
            use_case_id = str(mapped[0])
    if resumed_record and resumed_record.original_use_case_id:
        use_case_id = resumed_record.original_use_case_id

    reference_ids = extract_reference_ids(query, getattr(qu, "entities", None) if qu else None)
    signals = extract_query_signals(query, qu)

    if resumed_record is not None:
        from app.chat.canonical_mode import build_canonical_failure_state
        from app.chat.canonical_query_to_intent_resume import (
            build_intent_classification_from_handoff,
            query_to_intent_contract_error,
            reconstruct_query_to_intent_for_resume,
        )

        canonical_dict = dict(resumed_record.canonical_planning_input or {})
        routing = dict(canonical_dict.get("routing") or {})
        intent_classification = build_intent_classification_from_handoff(
            resumed_record=resumed_record,
            routing=routing,
        )
        if intent_classification is None:
            return build_canonical_failure_state(
                state,
                outcome="resolution_failed",
                reason="invalid_handoff_intent_contract",
                detail="missing_original_skill_or_answer_goal",
            )
        query_to_intent = reconstruct_query_to_intent_for_resume(
            resumed_record=resumed_record,
            merged_canonical=canonical_dict,
            query=query,
            query_understanding=qu,
            routed=routed,
        )
        contract_error = query_to_intent_contract_error(query_to_intent)
        if contract_error:
            return build_canonical_failure_state(
                state,
                outcome="resolution_failed",
                reason=contract_error,
                detail="invalid_handoff_query_to_intent_contract",
            )
        known_query_to_intent_built = True
        if resumed_record.gap_resolution and not state.get("gap_resolution"):
            state = {**state, "gap_resolution": resumed_record.gap_resolution}
        processing_lane = str(routing.get("processing_lane") or processing_lane)
        resolved_tier = str(routing.get("resolved_tier") or resolved_tier)
        completeness = evaluate_known_detail_completion(
            use_case_id=use_case_id,
            query_to_intent=query_to_intent,
            query_understanding=qu,
        )
        state = emit_known_completeness_evaluated(state, completeness.model_dump()) or state
        if completeness.clarification_required and not completeness.divert_to_guided:
            route_reason = "resume_still_missing_user_fields"
        elif completeness.divert_to_guided or completeness.missing_fields:
            state = emit_guided_resolution_started(
                state,
                handoff_id,
                handoff_version=handoff_version,
                resumed=True,
            ) or state
            gap = run_guided_detail_resolution(
                query=query,
                handoff_id=handoff_id,
                handoff_version=handoff_version,
                intent_family=str(intent_classification.get("intent_family")),
                answer_goal=str(intent_classification.get("answer_goal_primary")),
                completeness=completeness,
                reference_ids=reference_ids,
                original_skill=resumed_record.original_skill,
                original_answer_goal=resumed_record.original_answer_goal,
                known_values=dict((canonical_dict.get("detail_state") or {}).get("field_values") or {}),
                state=state,
            )
            route_reason = "resume_guided_resolution"
        else:
            route_reason = "resume_complete"
    elif is_known_catalogue_match(match_path):
        # The known lane skips the intent *classifier* hop for routing (the canonical
        # stub below is the authority), but ``query_to_intent`` is also the response and
        # telemetry surface: ``candidate_mappings`` carries match_path/question_ref and
        # downstream consumers read intent_classification from it. Emitting a
        # ``{"query_signals": ...}`` stub dropped both, which is why every sentinel row
        # reported match_path/mapped_question_ref/intent_family/requires_clarification
        # as None. ``build_query_to_intent`` is deterministic — the LLM advisory is an
        # injected argument, never called here — so building it costs no model hop.
        known_q2i = build_query_to_intent(
            query=query,
            query_understanding=qu,
            routed_skill=str(routed.get("skill") or None),
            routing_provenance=routed.get("routing_provenance")
            if isinstance(routed.get("routing_provenance"), dict)
            else None,
        )
        query_to_intent = known_q2i.model_dump()
        known_query_to_intent_built = True
        completeness = evaluate_known_detail_completion(
            use_case_id=use_case_id,
            query_to_intent=query_to_intent,
            query_understanding=qu,
        )
        state = emit_known_completeness_evaluated(state, completeness.model_dump()) or state

        skill = str(routed.get("skill") or "knowledge_recall")
        # Intent family comes from the deterministic classifier, not from the routed
        # skill. ``build_known_path_intent_stub`` maps skill -> family through a small
        # lookup table, which is a lossy proxy: SPL-authoring questions routed to
        # alert_summary/attack_discovery were relabelled hybrid_alert_review and lost
        # their spl_generation_only family (and with it the governed SPL artifact).
        # The classifier is already computed above and costs no model hop.
        known_intent = dict(query_to_intent.get("intent_classification") or {})
        if known_intent:
            # The deterministic classifier ran; the *LLM* intent hop deliberately did not.
            # The known lane's contract is "no model hop", which this records honestly.
            known_intent.setdefault("answer_goal_primary", _primary_goal(known_intent))
            known_intent["llm_intent_status"] = "skipped"
            # Deterministic routing stays the authority for *which skill runs*; the
            # classifier only supplies the intent family and answer goals that shape the
            # answer. Letting the classifier's primary_intent through would override the
            # selected skill on the known lane, which routing owns.
            known_intent["primary_intent"] = skill
        else:
            known_intent = build_known_path_intent_stub(skill=skill, use_case_id=use_case_id)
        if completeness.clarification_required and not completeness.divert_to_guided:
            intent_classification = {
                "intent_family": "clarification_required",
                "primary_intent": "human_review",
                "requires_clarification": True,
                "requires_hil": True,
                "action_mode": "recommend_only",
                "answer_goal": ["clarification"],
                "answer_goal_primary": "clarification",
                "llm_intent_status": "stub",
                "reason": "known_path_missing_user_only_fields",
            }
            route_reason = "known_clarification"
        elif completeness.divert_to_guided:
            processing_lane = "guided"
            state = emit_guided_resolution_started(
                state, handoff_id, handoff_version=handoff_version
            ) or state
            intent_classification = known_intent
            gap = run_guided_detail_resolution(
                query=query,
                handoff_id=handoff_id,
                handoff_version=handoff_version,
                intent_family=str(intent_classification.get("intent_family")),
                answer_goal=str(intent_classification.get("answer_goal_primary")),
                completeness=completeness,
                reference_ids=reference_ids,
                original_skill=skill,
                original_answer_goal=str(intent_classification.get("answer_goal_primary")),
                state=state,
            )
            route_reason = completeness.divert_reason or "known_divert_guided"
        else:
            intent_classification = known_intent
            route_reason = "known_complete"
    else:
        q2i = build_query_to_intent(
            query=query,
            query_understanding=qu,
            routed_skill=str(routed.get("skill") or None),
            routing_provenance=routed.get("routing_provenance")
            if isinstance(routed.get("routing_provenance"), dict)
            else None,
        )
        query_to_intent = q2i.model_dump()
        intent_classification = dict(query_to_intent.get("intent_classification") or {})
        family = str(intent_classification.get("intent_family") or "")

        state = emit_planning_event(
            state,
            event="guided_intent.resolved",
            node_name="intent_classifier",
            decision_reason="guided_intent_resolved",
            payload={
                "handoff_id": handoff_id,
                "intent_family": family,
                "intent_source": "classifier",
                "answer_goal": intent_classification.get("answer_goal_primary"),
            },
        ) or state

        qualification = qualify_reference_query(
            query,
            intent_family=family,
            signals=signals,
            entities=getattr(qu, "entities", None) if qu else None,
        )

        if qualification.resolves_to_t0:
            resolved_tier = "T0"
            processing_lane = "knowledge_short_circuit"
            routed["skill"] = "knowledge_recall"
            intent_classification = build_t0_knowledge_stub(reference_ids=reference_ids)
            state = emit_tier_resolved(
                state,
                initial_tier=initial,
                resolved_tier=resolved_tier,
                processing_lane=processing_lane,
                intent_family="reference_knowledge",
                intent_source="classifier",
                primary_skill="knowledge_recall",
                answer_goal="reference_explanation",
            ) or state
            route_reason = "t4_resolved_t0"
        else:
            processing_lane = "guided"
            state = emit_guided_resolution_started(
                state, handoff_id, handoff_version=handoff_version
            ) or state
            answer_goal = str(intent_classification.get("answer_goal_primary") or "live_investigation")
            if not answer_goal:
                goals = intent_classification.get("answer_goal") or []
                answer_goal = str(goals[0]) if goals else "live_investigation"
            completeness = evaluate_known_detail_completion(
                use_case_id=use_case_id,
                query_to_intent=query_to_intent,
                query_understanding=qu,
            )
            gap = run_guided_detail_resolution(
                query=query,
                handoff_id=handoff_id,
                handoff_version=handoff_version,
                intent_family=family,
                answer_goal=answer_goal,
                completeness=completeness,
                reference_ids=reference_ids,
                original_skill=str(routed.get("skill") or ""),
                original_answer_goal=answer_goal,
                unsafe=bool(signals.get("block_or_contain")),
                state=state,
            )
            route_reason = "t4_guided_resolution"

    post = None
    preserved_answer_goal = ""
    if intent_classification is not None:
        preserved_answer_goal = str(intent_classification.get("answer_goal_primary") or "").strip()
    if gap is not None:
        post = evaluate_post_guided_completeness(
            gap,
            planner_required_fields=[
                k
                for k, c in (completeness.missing_field_categories if completeness else {}).items()
                if c == "planner_required"
            ],
            user_only_fields=[
                k
                for k, c in (completeness.missing_field_categories if completeness else {}).items()
                if c == "user_only"
            ],
        )
        state = emit_post_guided_completeness_evaluated(state, post.model_dump()) or state
        if post.clarification_required and intent_classification is not None:
            if preserved_answer_goal in {"", "clarification"}:
                gap_goal = normalize_resume_answer_goal(str(gap.original_answer_goal or ""))
                if gap_goal:
                    preserved_answer_goal = gap_goal
                else:
                    preserved_answer_goal = resume_answer_goal_for_skill(
                        str(routed.get("skill") or intent_classification.get("primary_intent") or "")
                    )
            intent_classification = {
                **intent_classification,
                "requires_clarification": True,
                "intent_family": "clarification_required",
                "answer_goal_primary": "clarification",
                "answer_goal": ["clarification"],
            }

    assert intent_classification is not None
    # Mirror canonical intent onto the query_to_intent this node built for the known
    # lane, so the response surface and the planner cannot disagree there. The T4/T0
    # branch is left alone: it deliberately reclassifies a qualified reference question
    # to ``reference_knowledge`` for planning while ``query_to_intent`` keeps the
    # classifier's own read, and that split is pinned by existing golden tests.
    if known_query_to_intent_built and isinstance(query_to_intent, dict):
        query_to_intent = {**query_to_intent, "intent_classification": intent_classification}

    canonical = build_canonical_planning_input(
        query=query,
        query_understanding=qu,
        routed=routed,
        intent_classification=intent_classification,
        trace_id=str(trace_id) if trace_id else None,
        handoff_id=handoff_id,
        handoff_version=handoff_version,
        resolved_tier=resolved_tier,
        processing_lane=processing_lane,
        completeness=completeness,
        gap=gap,
        reference_ids=reference_ids,
        route_reason=route_reason,
    )

    clarification_required = bool(
        intent_classification.get("requires_clarification")
        or (post is not None and post.clarification_required)
        or (gap is not None and gap.clarification_required)
    )

    policy_reason = resolve_canonical_policy_block_reason(
        intent_classification=intent_classification,
        query_understanding=qu,
        gap=gap,
        post=post,
    )
    if policy_reason:
        outcome = policy_blocked_outcome(
            canonical_input=canonical.model_dump(),
            policy_reason=policy_reason,
        )
        policy_state = {
            **state,
            "routed": routed,
            "intent_classification": intent_classification,
            "query_to_intent": query_to_intent,
            "canonical_planning_input": canonical.model_dump(),
            "canonical_planning_outcome": outcome.model_dump(),
            "gap_resolution": gap.model_dump() if gap else None,
            "known_completeness": completeness.model_dump() if completeness else None,
            "processing_lane": processing_lane,
            "resolved_tier": resolved_tier,
            "initial_tier": initial,
        }
        policy_state.pop("evidence_plan", None)
        return policy_state

    if clarification_required:
        unresolved_fields = list(
            gap.unresolved_details if gap else completeness.missing_fields if completeness else []
        )
        if not unresolved_fields:
            # The outcome contract requires at least one unresolved field; without this
            # the clarification would be unanswerable and the handoff unresumable.
            unresolved_fields = ["investigation_scope"]
        save_clarification_handoff(
            handoff_id=handoff_id,
            handoff_version=handoff_version,
            canonical_planning_input=canonical.model_dump(),
            gap_resolution=gap.model_dump() if gap else None,
            unresolved_fields=unresolved_fields,
            clarification_reason=route_reason or "clarification_required",
            trace_id=str(trace_id) if trace_id else None,
            session_id=str(session_id) if session_id else None,
            original_query=query,
            original_skill=str(routed.get("skill") or intent_classification.get("primary_intent")),
            original_use_case_id=use_case_id,
            original_answer_goal=preserved_answer_goal
            or str(intent_classification.get("answer_goal_primary") or ""),
            initial_tier=initial,
            resolved_tier=resolved_tier,
        )
        state = emit_handoff_persisted(
            state,
            handoff_id=handoff_id,
            handoff_version=handoff_version,
            handoff_status="awaiting_clarification",
            trace_id=str(trace_id) if trace_id else None,
            session_id=str(session_id) if session_id else None,
        ) or state
        state = emit_clarification_requested(
            state,
            {
                "handoff_id": handoff_id,
                "handoff_version": handoff_version,
                "clarification_reason": route_reason,
                "unresolved_fields": unresolved_fields,
            },
        ) or state
        # No EvidencePlan on this path. A partial dict here is what produced nine
        # missing-field ValidationErrors in every downstream consumer that reached
        # ``EvidencePlan.model_validate``. Downstream branches on outcome status.
        outcome = clarification_outcome(
            canonical_input=canonical.model_dump(),
            question=build_clarification_question(unresolved_fields),
            unresolved_fields=unresolved_fields,
            handoff_id=handoff_id,
            handoff_version=handoff_version,
            reason=route_reason or "clarification_required",
        )
        clarification_state = {
            **state,
            "routed": routed,
            "intent_classification": intent_classification,
            "query_to_intent": query_to_intent,
            "canonical_planning_input": canonical.model_dump(),
            "canonical_planning_outcome": outcome.model_dump(),
            "gap_resolution": gap.model_dump() if gap else None,
            "known_completeness": completeness.model_dump() if completeness else None,
            "processing_lane": processing_lane,
            "resolved_tier": resolved_tier,
            "initial_tier": initial,
            "pending_handoff_id": handoff_id,
            "pending_handoff_version": handoff_version,
        }
        clarification_state.pop("evidence_plan", None)
        return clarification_state

    save_handoff(
        CanonicalHandoffRecord(
            handoff_id=handoff_id,
            handoff_version=handoff_version,
            status="in_progress",
            trace_id=str(trace_id) if trace_id else None,
            session_id=str(session_id) if session_id else None,
            original_query=query,
            original_skill=str(routed.get("skill") or intent_classification.get("primary_intent")),
            original_use_case_id=use_case_id,
            original_answer_goal=str(intent_classification.get("answer_goal_primary")),
            initial_tier=initial,
            resolved_tier=resolved_tier,
            canonical_planning_input=canonical.model_dump(),
            gap_resolution=gap.model_dump() if gap else None,
        )
    )
    state = emit_handoff_persisted(
        state,
        handoff_id=handoff_id,
        handoff_version=handoff_version,
        handoff_status="in_progress",
        trace_id=str(trace_id) if trace_id else None,
        session_id=str(session_id) if session_id else None,
    ) or state

    evidence_plan, consumed, ignored = plan_evidence_from_canonical(
        canonical,
        state=state,
        intent_classification=intent_classification,
        query_to_intent=query_to_intent,
        query_understanding=qu,
        routed=routed,
        selected_use_case=selected_use_case,
        user_query=query,
    )

    evidence_payload = evidence_plan.model_dump()
    # Audit projection of the MCP authorisation decision. The legacy planning node set
    # this on its own payload; the canonical planner must too, or the parity checklist
    # sees a plan with no recorded decision.
    from app.chat.pipeline import _mcp_allowed_decision_from_plan  # circular: pipeline state

    evidence_payload["mcp_allowed_normalized"] = _mcp_allowed_decision_from_plan(evidence_payload)
    committed_resource_plan = evidence_payload.get("resource_plan")
    outcome = planned_outcome(
        canonical_input=canonical.model_dump(),
        evidence_plan=evidence_payload,
        resource_plan=committed_resource_plan,
    )

    return {
        **state,
        "routed": routed,
        "intent_classification": intent_classification,
        "query_to_intent": query_to_intent,
        "canonical_planning_input": canonical.model_dump(),
        "canonical_planning_outcome": outcome.model_dump(),
        "gap_resolution": gap.model_dump() if gap else None,
        "known_completeness": completeness.model_dump() if completeness else None,
        "evidence_plan": evidence_payload,
        "planner_consumed_fields": consumed,
        "planner_ignored_fields": ignored,
        "processing_lane": processing_lane,
        "resolved_tier": resolved_tier,
        "initial_tier": initial,
        "handoff_id": handoff_id,
        "handoff_version": handoff_version,
    }
