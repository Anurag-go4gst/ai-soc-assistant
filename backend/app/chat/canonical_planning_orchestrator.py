"""Canonical planning orchestration — lane, completeness, gap resolution, final planner."""

from __future__ import annotations

from typing import Any

from app.chat.canonical_handoff_builder import build_canonical_planning_input, new_handoff_id
from app.chat.canonical_handoff_store import (
    CanonicalHandoffRecord,
    get_handoff,
    save_clarification_handoff,
    save_handoff,
)
from app.chat.contracts.gap_resolution import FieldProvenance
from app.chat.guided_detail_resolution import run_guided_detail_resolution
from app.chat.intent_classifier import build_query_to_intent
from app.chat.intent_family_defaults import build_known_path_intent_stub, build_t0_knowledge_stub
from app.chat.known_detail_completion import evaluate_known_detail_completion
from app.chat.lane_router import is_known_catalogue_match, lane_for_match_path
from app.chat.plan_evidence_from_canonical import plan_evidence_from_canonical
from app.chat.planning_telemetry import (
    emit_clarification_requested,
    emit_guided_resolution_started,
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


def _merge_user_clarification(
    record: CanonicalHandoffRecord,
    user_answer: str,
) -> dict[str, Any]:
    """Merge clarification answer into known field values without re-classifying."""
    canonical = dict(record.canonical_planning_input or {})
    detail = dict(canonical.get("detail_state") or {})
    field_values = dict(detail.get("field_values") or {})
    field_sources = dict(detail.get("field_sources") or {})
    unresolved = list(record.unresolved_fields or [])
    if unresolved:
        target = unresolved[0]
        field_values[target] = user_answer.strip()
        field_sources[target] = "user"
    detail["field_values"] = field_values
    detail["field_sources"] = field_sources
    detail["present_fields"] = list(dict.fromkeys([*detail.get("present_fields", []), *field_values.keys()]))
    detail["missing_fields"] = [k for k in detail.get("missing_fields", []) if k not in field_values]
    canonical["detail_state"] = detail
    return canonical


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
        resumed_record = get_handoff(str(resume["handoff_id"]), int(resume.get("handoff_version") or 1))
        if resumed_record is not None and resumed_record.status == "clarification_required":
            handoff_id = resumed_record.handoff_id
            handoff_version = resumed_record.handoff_version + 1
            user_answer = str(resume.get("user_answer") or query)
            merged_canonical = _merge_user_clarification(resumed_record, user_answer)
            save_handoff(
                CanonicalHandoffRecord(
                    handoff_id=handoff_id,
                    handoff_version=handoff_version,
                    status="in_progress",
                    trace_id=str(trace_id) if trace_id else resumed_record.trace_id,
                    session_id=session_id or resumed_record.session_id,
                    original_query=resumed_record.original_query,
                    original_skill=resumed_record.original_skill,
                    original_use_case_id=resumed_record.original_use_case_id,
                    original_answer_goal=resumed_record.original_answer_goal,
                    initial_tier=resumed_record.initial_tier,
                    resolved_tier=resumed_record.resolved_tier,
                    canonical_planning_input=merged_canonical,
                    gap_resolution=resumed_record.gap_resolution,
                )
            )
            query = str(resumed_record.original_query or query)
            match_path = str(
                (merged_canonical.get("routing") or {}).get("match_path") or match_path
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
        canonical_dict = dict(resumed_record.canonical_planning_input or {})
        routing = dict(canonical_dict.get("routing") or {})
        intent_classification = {
            "intent_family": routing.get("intent_family"),
            "primary_intent": routing.get("primary_skill"),
            "answer_goal_primary": routing.get("answer_goal"),
            "answer_goal": [routing.get("answer_goal")],
            "llm_intent_status": routing.get("intent_source", "diversion"),
            "requires_clarification": False,
            "requires_hil": False,
            "action_mode": "recommend_only",
            "reason": "handoff_resume",
        }
        processing_lane = str(routing.get("processing_lane") or processing_lane)
        resolved_tier = str(routing.get("resolved_tier") or resolved_tier)
        completeness = evaluate_known_detail_completion(
            use_case_id=use_case_id,
            query_to_intent={"query_signals": signals, "handoff_resume": True},
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
        query_to_intent = {"query_signals": signals}
        completeness = evaluate_known_detail_completion(
            use_case_id=use_case_id,
            query_to_intent=query_to_intent,
            query_understanding=qu,
        )
        state = emit_known_completeness_evaluated(state, completeness.model_dump()) or state

        skill = str(routed.get("skill") or "knowledge_recall")
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
            intent_classification = build_known_path_intent_stub(skill=skill, use_case_id=use_case_id)
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
            intent_classification = build_known_path_intent_stub(skill=skill, use_case_id=use_case_id)
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
                unsafe=bool(signals.get("block_or_contain") and signals.get("run_execution")),
                state=state,
            )
            route_reason = "t4_guided_resolution"

    post = None
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
            intent_classification = {
                **intent_classification,
                "requires_clarification": True,
                "intent_family": "clarification_required",
                "answer_goal_primary": "clarification",
                "answer_goal": ["clarification"],
            }

    assert intent_classification is not None
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

    if clarification_required:
        save_clarification_handoff(
            handoff_id=handoff_id,
            handoff_version=handoff_version,
            canonical_planning_input=canonical.model_dump(),
            gap_resolution=gap.model_dump() if gap else None,
            unresolved_fields=list(gap.unresolved_details if gap else completeness.missing_fields if completeness else []),
            clarification_reason=route_reason or "clarification_required",
            trace_id=str(trace_id) if trace_id else None,
            session_id=str(session_id) if session_id else None,
            original_query=query,
            original_skill=str(routed.get("skill") or intent_classification.get("primary_intent")),
            original_use_case_id=use_case_id,
            original_answer_goal=str(intent_classification.get("answer_goal_primary")),
            initial_tier=initial,
            resolved_tier=resolved_tier,
        )
        state = emit_clarification_requested(
            state,
            {
                "handoff_id": handoff_id,
                "handoff_version": handoff_version,
                "clarification_reason": route_reason,
                "unresolved_fields": list(gap.unresolved_details if gap else []),
            },
        ) or state
        evidence_plan_payload = {
            "answer_mode": "clarification",
            "requires_hil": True,
            "needs_clarification": True,
            "reasons": ["canonical_clarification_required"],
            "resource_plan": None,
        }
        return {
            **state,
            "routed": routed,
            "intent_classification": intent_classification,
            "query_to_intent": query_to_intent,
            "canonical_planning_input": canonical.model_dump(),
            "gap_resolution": gap.model_dump() if gap else None,
            "known_completeness": completeness.model_dump() if completeness else None,
            "evidence_plan": evidence_plan_payload,
            "processing_lane": processing_lane,
            "resolved_tier": resolved_tier,
            "initial_tier": initial,
            "pending_handoff_id": handoff_id,
            "pending_handoff_version": handoff_version,
        }

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

    return {
        **state,
        "routed": routed,
        "intent_classification": intent_classification,
        "query_to_intent": query_to_intent,
        "canonical_planning_input": canonical.model_dump(),
        "gap_resolution": gap.model_dump() if gap else None,
        "known_completeness": completeness.model_dump() if completeness else None,
        "evidence_plan": evidence_plan.model_dump(),
        "planner_consumed_fields": consumed,
        "planner_ignored_fields": ignored,
        "processing_lane": processing_lane,
        "resolved_tier": resolved_tier,
        "initial_tier": initial,
        "handoff_id": handoff_id,
        "handoff_version": handoff_version,
    }
