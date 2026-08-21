"""Canonical planning orchestration — lane, completeness, gap resolution, final planner."""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Any

from app.chat.canonical_answer_mode_policy import CanonicalAnswerModePolicyError
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
    awaiting_investigation_plan_outcome,
    clarification_outcome,
    planned_outcome,
    policy_blocked_outcome,
)
from app.chat.contracts.gap_resolution import FieldProvenance
from app.chat.guided_detail_resolution import run_guided_detail_resolution
from app.chat.intent_classifier import build_query_to_intent
from app.chat.resolved_query_builder import apply_session_continuity, build_resolved_query_contract
from app.chat.semantic_t4_understanding import maybe_enrich_t4_semantic
from app.chat.session_context import _generic_scope_delta
from app.chat.intent_family_defaults import build_known_path_intent_stub, build_t0_knowledge_stub
from app.chat.known_detail_completion import evaluate_known_detail_completion
from app.chat.lane_router import is_known_catalogue_match, lane_for_match_path
from app.chat.canonical_policy_boundary import resolve_canonical_policy_block_reason
from app.chat.canonical_mode import build_typed_planning_failure_state
from app.chat.plan_evidence_from_canonical import plan_evidence_from_canonical
from app.chat.investigation_shaped import is_investigation_shaped_final_rqc
from app.chat.capability_snapshot import maybe_attach_capability_snapshot
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
from app.config import settings

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
    from app.synthesis.turn_timing import record_canonical_planning_ms

    started = time.monotonic()
    try:
        state = graph_node_lane_and_canonical_planning(state)
        from app.chat.canonical_outcome_gate import enforce_canonical_outcome_invariant

        state = enforce_canonical_outcome_invariant(state)
        if not isinstance(state.get("route_adjudication"), dict):
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
    finally:
        record_canonical_planning_ms(int((time.monotonic() - started) * 1000))


@dataclass(frozen=True)
class _PlanningIntake:
    """Stage 1 output — resume reconciliation and lane routing settled.

    ``terminal_state`` is a completed pipeline state the caller must return
    immediately (resume failure); every other field is undefined when it is set.
    """

    state: ChatPipelineState
    query: str
    handoff_id: str
    handoff_version: int
    resumed_record: CanonicalHandoffRecord | None
    initial_tier: str
    resolved_tier: str
    processing_lane: str
    observed_match_path: str
    effective_match_path: str
    match_path: str
    terminal_state: ChatPipelineState | None = None


@dataclass(frozen=True)
class _LaneResolution:
    """Stage 2 output — intent, completeness, and gap resolution settled."""

    state: ChatPipelineState
    routed: dict[str, Any]
    intent_classification: dict[str, Any] | None
    query_to_intent: dict[str, Any] | None
    known_query_to_intent_built: bool
    completeness: Any | None
    gap: Any | None
    post: Any | None
    processing_lane: str
    resolved_tier: str
    route_reason: str
    preserved_answer_goal: str
    use_case_id: str | None
    reference_ids: list[str]
    terminal_state: ChatPipelineState | None = None


def _prepare_planning_intake(state: ChatPipelineState) -> _PlanningIntake:
    """Stage 1 — query/handoff resume preparation and lane routing.

    Creates no plan and takes no planning decision; it only settles which handoff
    version this turn continues and which lane the match path implies.
    """
    request = state["request"]
    query = state.get("effective_query") or request.message
    qu = state.get("query_understanding")
    trace_id = state.get("trace_id")
    session_id = state.get("session_id")
    observed_match_path = str(
        state.get("observed_catalogue_match_path")
        or getattr(qu, "deterministic_match_path", "")
        or "out_of_registry"
    )
    effective_match_path = str(
        state.get("effective_catalogue_match_path") or observed_match_path
    )
    match_path = effective_match_path

    state = emit_planning_event(
        state,
        event="query_understanding.completed",
        node_name="understand_query",
        decision_reason="query_understanding_completed",
        payload={
            "trace_id": trace_id,
            "match_path": observed_match_path,
            "effective_match_path": effective_match_path,
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
            return _PlanningIntake(
                state=state,
                query=query,
                handoff_id=handoff_id,
                handoff_version=handoff_version,
                resumed_record=None,
                initial_tier="",
                resolved_tier="",
                processing_lane="",
                observed_match_path=observed_match_path,
                effective_match_path=effective_match_path,
                match_path=match_path,
                terminal_state=build_canonical_failure_state(
                    state,
                    outcome="resolution_failed",
                    reason=exc.reason,
                    detail=exc.detail,
                ),
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
        resumed_routing = resume_result.merged_canonical.get("routing") or {}
        observed_match_path = str(
            resumed_routing.get("observed_match_path")
            or resumed_routing.get("match_path")
            or observed_match_path
        )
        effective_match_path = str(
            resumed_routing.get("effective_match_path")
            or resumed_routing.get("match_path")
            or effective_match_path
        )
        match_path = effective_match_path

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

    return _PlanningIntake(
        state=state,
        query=query,
        handoff_id=handoff_id,
        handoff_version=handoff_version,
        resumed_record=resumed_record,
        initial_tier=initial,
        resolved_tier=resolved,
        processing_lane=lane,
        observed_match_path=observed_match_path,
        effective_match_path=effective_match_path,
        match_path=match_path,
    )


def _resolve_lane_intent_and_details(
    state: ChatPipelineState,
    *,
    intake: _PlanningIntake,
) -> _LaneResolution:
    """Stage 2 — resume / known / T4 lane resolution and post-guided completeness.

    Classifies intent and resolves missing detail. It composes no Resource Plan;
    ``plan_evidence_from_canonical`` remains the sole plan creator.
    """
    query = intake.query
    qu = state.get("query_understanding")
    routed = dict(state.get("routed") or {})
    handoff_id = intake.handoff_id
    handoff_version = intake.handoff_version
    resumed_record = intake.resumed_record
    match_path = intake.match_path
    initial = intake.initial_tier

    gap = None
    completeness = None
    intent_classification: dict[str, Any] | None = None
    query_to_intent: dict[str, Any] | None = state.get("query_to_intent")
    processing_lane = intake.processing_lane
    resolved_tier = intake.resolved_tier
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

    def _terminal(failure_state: ChatPipelineState) -> _LaneResolution:
        return _LaneResolution(
            state=state,
            routed=routed,
            intent_classification=None,
            query_to_intent=query_to_intent,
            known_query_to_intent_built=False,
            completeness=None,
            gap=None,
            post=None,
            processing_lane=processing_lane,
            resolved_tier=resolved_tier,
            route_reason=route_reason,
            preserved_answer_goal="",
            use_case_id=use_case_id,
            reference_ids=reference_ids,
            terminal_state=failure_state,
        )

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
            return _terminal(
                build_canonical_failure_state(
                    state,
                    outcome="resolution_failed",
                    reason="invalid_handoff_intent_contract",
                    detail="missing_original_skill_or_answer_goal",
                )
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
            return _terminal(
                build_canonical_failure_state(
                    state,
                    outcome="resolution_failed",
                    reason=contract_error,
                    detail="invalid_handoff_query_to_intent_contract",
                )
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
            # Deterministic routing owns the selected skill; the classifier supplies
            # intent family and answer goals only — do not overwrite primary_intent.
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

    return _LaneResolution(
        state=state,
        routed=routed,
        intent_classification=intent_classification,
        query_to_intent=query_to_intent,
        known_query_to_intent_built=known_query_to_intent_built,
        completeness=completeness,
        gap=gap,
        post=post,
        processing_lane=processing_lane,
        resolved_tier=resolved_tier,
        route_reason=route_reason,
        preserved_answer_goal=preserved_answer_goal,
        use_case_id=use_case_id,
        reference_ids=reference_ids,
    )


def _durable_canonical_payload(canonical: Any, resolved_query_contract: dict[str, Any] | None) -> dict[str, Any]:
    """Persist the final RQC beside canonical input without a DB migration."""
    payload = canonical.model_dump()
    if resolved_query_contract:
        payload["resolved_query_contract"] = resolved_query_contract
    return payload


def _persist_clarification_outcome(
    state: ChatPipelineState,
    *,
    intake: _PlanningIntake,
    lane: _LaneResolution,
    canonical: Any,
    intent_classification: dict[str, Any],
    query_to_intent: dict[str, Any] | None,
    resolved_query_contract: dict[str, Any] | None = None,
) -> ChatPipelineState:
    """Stage 4 — persist the clarification handoff and return its terminal state."""
    handoff_id = intake.handoff_id
    handoff_version = intake.handoff_version
    trace_id = state.get("trace_id")
    session_id = state.get("session_id")
    gap = lane.gap
    completeness = lane.completeness
    route_reason = lane.route_reason

    unresolved_fields = list(
        gap.unresolved_details if gap else completeness.missing_fields if completeness else []
    )
    rqc_unresolved = list((resolved_query_contract or {}).get("unresolved_fields") or [])
    for field in rqc_unresolved:
        if field not in unresolved_fields:
            unresolved_fields.append(field)
    if not unresolved_fields:
        # The outcome contract requires at least one unresolved field; without this
        # the clarification would be unanswerable and the handoff unresumable.
        unresolved_fields = ["investigation_scope"]
    save_clarification_handoff(
        handoff_id=handoff_id,
        handoff_version=handoff_version,
        canonical_planning_input=_durable_canonical_payload(canonical, resolved_query_contract),
        gap_resolution=gap.model_dump() if gap else None,
        unresolved_fields=unresolved_fields,
        clarification_reason=(
            (resolved_query_contract or {}).get("clarification_reason")
            or route_reason
            or "clarification_required"
        ),
        trace_id=str(trace_id) if trace_id else None,
        session_id=str(session_id) if session_id else None,
        original_query=intake.query,
        original_skill=str(lane.routed.get("skill") or intent_classification.get("primary_intent")),
        original_use_case_id=lane.use_case_id,
        original_answer_goal=lane.preserved_answer_goal
        or str(intent_classification.get("answer_goal_primary") or ""),
        initial_tier=intake.initial_tier,
        resolved_tier=lane.resolved_tier,
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
        "routed": lane.routed,
        "intent_classification": intent_classification,
        "query_to_intent": query_to_intent,
        "resolved_query_contract": resolved_query_contract,
        "canonical_planning_input": canonical.model_dump(),
        "canonical_planning_outcome": outcome.model_dump(),
        "gap_resolution": gap.model_dump() if gap else None,
        "known_completeness": completeness.model_dump() if completeness else None,
        "processing_lane": lane.processing_lane,
        "resolved_tier": lane.resolved_tier,
        "initial_tier": intake.initial_tier,
        "pending_handoff_id": handoff_id,
        "pending_handoff_version": handoff_version,
    }
    clarification_state.pop("evidence_plan", None)
    return clarification_state


def _bind_final_route_from_rqc(
    state: ChatPipelineState,
    *,
    intake: _PlanningIntake,
    lane: _LaneResolution,
    canonical: Any,
    intent_classification: dict[str, Any],
    query_to_intent: dict[str, Any] | None,
    resolved_query_contract: dict[str, Any] | None,
) -> tuple[ChatPipelineState, _LaneResolution, Any]:
    """Commit final route ownership from the final RQC before ResourcePlan creation."""
    ready: ChatPipelineState = {
        **state,
        "routed": lane.routed,
        "intent_classification": intent_classification,
        "query_to_intent": query_to_intent,
        "resolved_query_contract": resolved_query_contract,
        "canonical_planning_input": canonical.model_dump(),
        "processing_lane": lane.processing_lane,
        "resolved_tier": lane.resolved_tier,
        "initial_tier": intake.initial_tier,
    }
    if ready.get("request") is None:
        return ready, lane, canonical
    from app.chat.pipeline import graph_node_route_contract, graph_node_route_resolution

    if ready.get("route_plan_shadow") is None:
        ready = {**ready, "route_plan_shadow": {}}
    ready = graph_node_route_resolution(ready)
    ready = graph_node_route_contract(ready)
    adjudication = ready.get("route_adjudication")
    final_route = None
    if isinstance(adjudication, dict):
        final_route = adjudication.get("final_route") or adjudication.get("route")
    if not final_route:
        return ready, lane, canonical
    routed = dict(ready.get("routed") or lane.routed)
    routed["skill"] = str(final_route)
    ready = {**ready, "routed": routed}
    canonical = canonical.model_copy(
        update={
            "routing": canonical.routing.model_copy(update={"primary_skill": str(final_route)})
        }
    )
    return ready, replace(lane, routed=routed), canonical


def _commit_planned_outcome(
    state: ChatPipelineState,
    *,
    intake: _PlanningIntake,
    lane: _LaneResolution,
    canonical: Any,
    intent_classification: dict[str, Any],
    query_to_intent: dict[str, Any] | None,
    resolved_query_contract: dict[str, Any] | None = None,
) -> ChatPipelineState:
    """Stage 5 — persist the in-progress handoff and commit the planned outcome.

    ``plan_evidence_from_canonical`` stays the sole plan creator; this stage only
    persists around it and projects the committed plan onto the returned state.

    When ``ai_soc_investigation_plan_before_resource_plan_enabled`` is on,
    investigation-shaped Final RQCs stop here without calling the plan creator
    (P0 wait-state — no ResourcePlan until envelope approval in P4).
    """
    state, lane, canonical = _bind_final_route_from_rqc(
        state,
        intake=intake,
        lane=lane,
        canonical=canonical,
        intent_classification=intent_classification,
        query_to_intent=query_to_intent,
        resolved_query_contract=resolved_query_contract,
    )
    handoff_id = intake.handoff_id
    handoff_version = intake.handoff_version
    trace_id = state.get("trace_id")
    session_id = state.get("session_id")
    qu = state.get("query_understanding")
    selected_use_case = state.get("selected_use_case")
    routed = lane.routed
    gap = lane.gap
    completeness = lane.completeness

    primary_skill = str(
        (canonical.routing.primary_skill if canonical is not None else None)
        or routed.get("skill")
        or intent_classification.get("primary_intent")
        or ""
    )
    investigation_wait = bool(
        settings.ai_soc_investigation_plan_before_resource_plan_enabled
        and is_investigation_shaped_final_rqc(
            resolved_query_contract=resolved_query_contract,
            primary_skill=primary_skill,
            intent_classification=intent_classification,
            query_understanding=qu,
        )
    )
    handoff_status = "awaiting_investigation_plan" if investigation_wait else "in_progress"

    save_handoff(
        CanonicalHandoffRecord(
            handoff_id=handoff_id,
            handoff_version=handoff_version,
            status=handoff_status,  # type: ignore[arg-type]
            trace_id=str(trace_id) if trace_id else None,
            session_id=str(session_id) if session_id else None,
            original_query=intake.query,
            original_skill=str(routed.get("skill") or intent_classification.get("primary_intent")),
            original_use_case_id=lane.use_case_id,
            original_answer_goal=str(intent_classification.get("answer_goal_primary")),
            initial_tier=intake.initial_tier,
            resolved_tier=lane.resolved_tier,
            canonical_planning_input=_durable_canonical_payload(canonical, resolved_query_contract),
            gap_resolution=gap.model_dump() if gap else None,
        )
    )
    state = emit_handoff_persisted(
        state,
        handoff_id=handoff_id,
        handoff_version=handoff_version,
        handoff_status=handoff_status,
        trace_id=str(trace_id) if trace_id else None,
        session_id=str(session_id) if session_id else None,
    ) or state

    if investigation_wait:
        outcome = awaiting_investigation_plan_outcome(canonical_input=canonical.model_dump())
        wait_state: ChatPipelineState = {
            **state,
            "routed": routed,
            "intent_classification": intent_classification,
            "query_to_intent": query_to_intent,
            "resolved_query_contract": resolved_query_contract,
            "canonical_planning_input": canonical.model_dump(),
            "canonical_planning_outcome": outcome.model_dump(),
            "gap_resolution": gap.model_dump() if gap else None,
            "known_completeness": completeness.model_dump() if completeness else None,
            "processing_lane": lane.processing_lane,
            "resolved_tier": lane.resolved_tier,
            "initial_tier": intake.initial_tier,
            "observed_catalogue_match_path": intake.observed_match_path,
            "effective_catalogue_match_path": intake.effective_match_path,
            "handoff_id": handoff_id,
            "handoff_version": handoff_version,
            "pending_handoff_id": handoff_id,
            "pending_handoff_version": handoff_version,
        }
        wait_state.pop("evidence_plan", None)
        wait_state.pop("execution", None)
        wait_state.pop("mcp_evidence", None)
        return wait_state

    try:
        evidence_plan, consumed, ignored = plan_evidence_from_canonical(
            canonical,
            state=state,
            intent_classification=intent_classification,
            query_to_intent=query_to_intent,
            query_understanding=qu,
            routed=routed,
            selected_use_case=selected_use_case,
            user_query=intake.query,
        )
    except CanonicalAnswerModePolicyError as exc:
        failure_state = build_typed_planning_failure_state(
            {
                **state,
                "routed": routed,
                "intent_classification": intent_classification,
                "query_to_intent": query_to_intent,
                "canonical_planning_input": canonical.model_dump(),
                "processing_lane": lane.processing_lane,
                "resolved_tier": lane.resolved_tier,
                "initial_tier": intake.initial_tier,
            },
            failure_status="planning_failed",
            reason=exc.reason,
            detail=exc.detail,
            category=exc.category,
        )
        failure_state.pop("evidence_plan", None)
        failure_state.pop("execution", None)
        failure_state.pop("mcp_evidence", None)
        return failure_state

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
        "resolved_query_contract": resolved_query_contract,
        "canonical_planning_input": canonical.model_dump(),
        "canonical_planning_outcome": outcome.model_dump(),
        "gap_resolution": gap.model_dump() if gap else None,
        "known_completeness": completeness.model_dump() if completeness else None,
        "evidence_plan": evidence_payload,
        "planner_consumed_fields": consumed,
        "planner_ignored_fields": ignored,
        "processing_lane": lane.processing_lane,
        "resolved_tier": lane.resolved_tier,
        "initial_tier": intake.initial_tier,
        "observed_catalogue_match_path": intake.observed_match_path,
        "effective_catalogue_match_path": intake.effective_match_path,
        "handoff_id": handoff_id,
        "handoff_version": handoff_version,
    }


def graph_node_lane_and_canonical_planning(state: ChatPipelineState) -> ChatPipelineState:
    """Lane router → completeness/guided resolution → canonical handoff → final planner.

    Ordered stage seam. Each stage is separately typed and testable; none of them
    creates a Resource Plan, and the stage order is the planning contract:
    intake/resume → lane+intent/detail → canonical input + policy outcome →
    clarification persistence *or* plan commit.
    """
    intake = _prepare_planning_intake(state)
    if intake.terminal_state is not None:
        return intake.terminal_state
    state = intake.state

    lane = _resolve_lane_intent_and_details(state, intake=intake)
    if lane.terminal_state is not None:
        return lane.terminal_state
    state = lane.state

    intent_classification = lane.intent_classification
    assert intent_classification is not None
    query_to_intent = lane.query_to_intent
    # Mirror canonical intent onto the query_to_intent this node built for the known
    # lane, so the response surface and the planner cannot disagree there. The T4/T0
    # branch is left alone: it deliberately reclassifies a qualified reference question
    # to ``reference_knowledge`` for planning while ``query_to_intent`` keeps the
    # classifier's own read, and that split is pinned by existing golden tests.
    if lane.known_query_to_intent_built and isinstance(query_to_intent, dict):
        query_to_intent = {**query_to_intent, "intent_classification": intent_classification}

    session_resolution = state.get("session_context_resolution")
    prior_rqc = None
    delta_remainder = None
    follow_up_kind = None
    pins = getattr(session_resolution, "pins", None)
    if pins is not None:
        follow_up_kind = getattr(session_resolution, "follow_up_kind", None)
        prior_rqc = getattr(pins, "last_rqc_redacted", None)
        if follow_up_kind == "scope_delta":
            delta_remainder = _generic_scope_delta(" ".join(intake.query.lower().split()))

    resolved_query = maybe_enrich_t4_semantic(
        apply_session_continuity(
            build_resolved_query_contract(
                query=intake.query,
                query_understanding=state.get("query_understanding"),
                qualification_tier=lane.resolved_tier,  # type: ignore[arg-type]
                qualification_source=intake.match_path,
                query_to_intent=query_to_intent,
                provenance={"route_reason": lane.route_reason},
            ),
            prior_rqc=prior_rqc if isinstance(prior_rqc, dict) else None,
            delta_remainder=delta_remainder,
            follow_up_kind=follow_up_kind if isinstance(follow_up_kind, str) else None,
        ),
        query=intake.query,
    )
    resolved_query_contract = resolved_query.model_dump(mode="json")
    state = {**state, "resolved_query_contract": resolved_query_contract}
    # P1: CapabilitySnapshot attaches after Final RQC (flag-gated). Same snapshot
    # whether T4 ran — vocabulary is need × availability only.
    state = maybe_attach_capability_snapshot(
        state,
        resolved_query_contract=resolved_query_contract,
    )

    canonical = build_canonical_planning_input(
        query=intake.query,
        query_understanding=state.get("query_understanding"),
        routed=lane.routed,
        intent_classification=intent_classification,
        trace_id=str(state.get("trace_id")) if state.get("trace_id") else None,
        handoff_id=intake.handoff_id,
        handoff_version=intake.handoff_version,
        resolved_tier=lane.resolved_tier,
        processing_lane=lane.processing_lane,
        completeness=lane.completeness,
        gap=lane.gap,
        reference_ids=lane.reference_ids,
        route_reason=lane.route_reason,
        observed_match_path=intake.observed_match_path,
        effective_match_path=intake.effective_match_path,
    )

    clarification_required = bool(
        resolved_query.clarification_required
        or resolved_query.ambiguity_state in {"clarification_required", "policy_blocked"}
        or (lane.post is not None and lane.post.clarification_required)
        or (lane.gap is not None and lane.gap.clarification_required)
    )

    policy_reason = resolve_canonical_policy_block_reason(
        intent_classification=intent_classification,
        query_understanding=state.get("query_understanding"),
        gap=lane.gap,
        post=lane.post,
    )
    if policy_reason:
        outcome = policy_blocked_outcome(
            canonical_input=canonical.model_dump(),
            policy_reason=policy_reason,
        )
        policy_state = {
            **state,
            "routed": lane.routed,
            "intent_classification": intent_classification,
            "query_to_intent": query_to_intent,
            "resolved_query_contract": resolved_query_contract,
            "canonical_planning_input": canonical.model_dump(),
            "canonical_planning_outcome": outcome.model_dump(),
            "gap_resolution": lane.gap.model_dump() if lane.gap else None,
            "known_completeness": lane.completeness.model_dump() if lane.completeness else None,
            "processing_lane": lane.processing_lane,
            "resolved_tier": lane.resolved_tier,
            "initial_tier": intake.initial_tier,
        }
        policy_state.pop("evidence_plan", None)
        return policy_state

    if clarification_required:
        return _persist_clarification_outcome(
            state,
            intake=intake,
            lane=lane,
            canonical=canonical,
            intent_classification=intent_classification,
            query_to_intent=query_to_intent,
            resolved_query_contract=resolved_query_contract,
        )

    return _commit_planned_outcome(
        state,
        intake=intake,
        lane=lane,
        canonical=canonical,
        intent_classification=intent_classification,
        query_to_intent=query_to_intent,
        resolved_query_contract=resolved_query_contract,
    )
