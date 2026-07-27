"""Build CanonicalPlanningInput from pipeline state fragments."""

from __future__ import annotations

import uuid
from typing import Any

from app.chat.contracts.canonical_planning_input import (
    CanonicalPlanningInput,
    DetailState,
    GovernanceContext,
    GuidedResolutionSnapshot,
    MessageContext,
    PlanningGoal,
    QueryUnderstandingSnapshot,
    RoutingContext,
    TraceContext,
)
from app.chat.contracts.gap_resolution import GapResolutionResult
from app.chat.known_detail_completion import KnownCompletenessResult
from app.chat.lane_router import lane_for_match_path
from app.chat.reference_qualification import extract_reference_ids


def new_handoff_id() -> str:
    return f"cpi:{uuid.uuid4().hex[:12]}"


def build_canonical_planning_input(
    *,
    query: str,
    query_understanding: Any,
    routed: dict[str, Any],
    intent_classification: dict[str, Any],
    trace_id: str | None = None,
    handoff_id: str | None = None,
    handoff_version: int = 1,
    resolved_tier: str | None = None,
    processing_lane: str | None = None,
    completeness: KnownCompletenessResult | None = None,
    gap: GapResolutionResult | None = None,
    reference_ids: list[str] | None = None,
    route_reason: str = "",
) -> CanonicalPlanningInput:
    match_path = str(getattr(query_understanding, "deterministic_match_path", "") or "out_of_registry")
    initial, resolved, default_lane = lane_for_match_path(match_path, resolved_tier=resolved_tier)  # type: ignore[arg-type]
    lane = processing_lane or default_lane
    skill = str(routed.get("skill") or intent_classification.get("primary_intent") or "knowledge_recall")
    family = str(intent_classification.get("intent_family") or "clarification_required")
    intent_source_raw = str(intent_classification.get("llm_intent_status") or "classifier")
    intent_source = "stub" if intent_source_raw == "skipped" else intent_source_raw
    if intent_source not in {"stub", "classifier", "short_circuit", "diversion"}:
        intent_source = "classifier"
    answer_goal = str(
        intent_classification.get("answer_goal_primary")
        or (intent_classification.get("answer_goal") or ["live_investigation"])[0]
    )

    entities = getattr(query_understanding, "entities", None)
    ent_payload = entities.model_dump() if hasattr(entities, "model_dump") else {}
    signals = {}
    refs = reference_ids or extract_reference_ids(query, entities)
    use_case_id = None
    mapped = getattr(query_understanding, "mapped_use_case_ids", None)
    if isinstance(mapped, list) and mapped:
        use_case_id = str(mapped[0])

    detail = DetailState()
    if completeness:
        detail.planner_required_fields = [
            k for k, c in completeness.missing_field_categories.items() if c == "planner_required"
        ]
        detail.tool_discoverable_fields = [
            k for k, c in completeness.missing_field_categories.items() if c == "tool_discoverable"
        ]
        detail.user_only_fields = [
            k for k, c in completeness.missing_field_categories.items() if c == "user_only"
        ]
        detail.optional_fields = list(completeness.optional_fields)
        detail.present_fields = list(completeness.present_fields)
        detail.missing_fields = list(completeness.missing_fields)

    if gap:
        detail.field_values = {k: v.value for k, v in gap.known_details.items()}
        detail.field_sources = dict(gap.field_sources)
        detail.field_confidence = dict(gap.field_confidence)
        detail.conflicts = [c.model_dump() for c in gap.conflicts]

    guided = GuidedResolutionSnapshot()
    if gap:
        guided.attempted = True
        guided.resolution_id = gap.resolution_id
        guided.selected_tools = list(gap.selected_tools)
        guided.tool_statuses = dict(gap.tool_statuses)
        guided.resolved_fields = list(gap.resolved_details.keys())
        guided.unresolved_fields = list(gap.unresolved_details)
        guided.resolution_status = gap.resolution_status
        guided.retry_count = gap.retry_count
        guided.clarification_required = gap.clarification_required

    governance = GovernanceContext(
        safe=not bool(intent_classification.get("requires_clarification")),
        rag_allowed=family in {"reference_knowledge", "knowledge_only", "policy_knowledge", "sop_or_playbook"},
        spl_generation_allowed=family in {"spl_generation_only", "spl_generation_and_run", "hybrid_alert_review", "live_investigation"},
        spl_execution_allowed=False,
        mcp_allowed=False,
        action_allowed=False,
        remediation_allowed=False,
        approval_required=bool(intent_classification.get("requires_hil")),
    )

    return CanonicalPlanningInput(
        trace=TraceContext(
            trace_id=trace_id,
            handoff_id=handoff_id or new_handoff_id(),
            handoff_version=handoff_version,
        ),
        message=MessageContext(
            content_reference=query,
            normalized_query=str(getattr(query_understanding, "normalized_query", query) or query),
        ),
        routing=RoutingContext(
            initial_tier=initial,
            resolved_tier=resolved if resolved_tier else initial,
            match_path=match_path,
            catalogue_tier=resolved if resolved_tier else initial,
            processing_lane=lane,  # type: ignore[arg-type]
            route_reason=route_reason or str(routed.get("reasons", ["route"])[0] if routed.get("reasons") else "route"),
            use_case_id=use_case_id,
            primary_skill=skill,
            original_skill=gap.original_skill if gap else None,
            intent_family=family,
            intent_source=intent_source,  # type: ignore[arg-type]
            answer_goal=answer_goal,
        ),
        query_understanding=QueryUnderstandingSnapshot(
            entities=ent_payload,
            signals=signals,
            time_window=getattr(entities, "time_window", None) if entities else None,
            reference_ids=refs,
            candidate_use_cases=list(mapped or []),
            confidence=float(getattr(query_understanding, "confidence", 0.0) or 0.0),
        ),
        detail_state=detail,
        guided_resolution=guided,
        planning_goal=PlanningGoal(
            requested_outcomes=[answer_goal],
            evidence_requirements=list(completeness.required_fields) if completeness else [],
            limitations=list(completeness.limitations if completeness else []),
        ),
        governance=governance,
    )
