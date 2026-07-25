"""Durable planning telemetry via DecisionRecord.payload."""

from __future__ import annotations

import time
from typing import Any

from app.chat.canonical_mode import CONTRACT_VERSION, NODE_VERSION
from app.chat.contracts.canonical_planning_input import CanonicalPlanningInput
from app.chat.decision_record import emit_decision_record
from app.planner.planner_hierarchy import DecisionRecord, new_decision_record_id

_EVENT_LOG: list[dict[str, Any]] = []
_LAST_DECISION_ID: str | None = None


def reset_planning_telemetry_for_tests() -> None:
    global _LAST_DECISION_ID
    _EVENT_LOG.clear()
    _LAST_DECISION_ID = None


def planning_events() -> list[dict[str, Any]]:
    return list(_EVENT_LOG)


def last_decision_id() -> str | None:
    return _LAST_DECISION_ID


def _base_payload(
    *,
    event: str,
    trace_id: str | None = None,
    turn_id: str | None = None,
    handoff_id: str | None = None,
    handoff_version: int | None = None,
    resource_plan_id: str | None = None,
    parent_decision_id: str | None = None,
    status: str = "completed",
    duration_ms: int | None = None,
    error_category: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event": event,
        "trace_id": trace_id,
        "turn_id": turn_id,
        "handoff_id": handoff_id,
        "handoff_version": handoff_version,
        "resource_plan_id": resource_plan_id,
        "node_version": NODE_VERSION,
        "contract_version": CONTRACT_VERSION,
        "status": status,
    }
    if duration_ms is not None:
        payload["duration_ms"] = duration_ms
    if error_category:
        payload["error_category"] = error_category
    if parent_decision_id:
        payload["parent_decision_id"] = parent_decision_id
    if extra:
        payload.update(extra)
    return payload


def emit_planning_event(
    state: dict[str, Any] | None,
    *,
    event: str,
    node_name: str,
    decision_reason: str,
    payload: dict[str, Any],
    authority: str = "deterministic",
    duration_ms: int | None = None,
    parent_decision_id: str | None = None,
) -> dict[str, Any] | None:
    """Emit durable planning telemetry through DecisionRecord.payload."""
    global _LAST_DECISION_ID
    record_id = new_decision_record_id()
    _LAST_DECISION_ID = record_id
    full_payload = {
        **_base_payload(
            event=event,
            trace_id=payload.get("trace_id") or (state or {}).get("trace_id"),
            turn_id=payload.get("turn_id"),
            handoff_id=payload.get("handoff_id"),
            handoff_version=payload.get("handoff_version"),
            resource_plan_id=payload.get("resource_plan_id"),
            parent_decision_id=parent_decision_id or _LAST_DECISION_ID,
            status=str(payload.get("status") or "completed"),
            duration_ms=duration_ms,
            error_category=payload.get("error_category"),
            extra=payload,
        ),
    }
    _EVENT_LOG.append(full_payload)
    from app.chat.durable_planning_telemetry import persist_planning_event

    persist_payload = {**full_payload, "decision_id": record_id, "node_name": node_name}
    persist_planning_event(persist_payload)
    if state is None:
        return None
    return emit_decision_record(
        state,
        DecisionRecord(
            record_id=record_id,
            node=node_name,
            authority=authority,
            decision_reason=decision_reason,
            inputs_ref=["state"],
            outputs_ref=["state"],
            payload=full_payload,
        ),
    )


def timed_emit(
    state: dict[str, Any],
    *,
    event: str,
    node_name: str,
    decision_reason: str,
    payload: dict[str, Any],
    started: float,
) -> dict[str, Any]:
    duration_ms = int((time.monotonic() - started) * 1000)
    result = emit_planning_event(
        state,
        event=event,
        node_name=node_name,
        decision_reason=decision_reason,
        payload={**payload, "duration_ms": duration_ms},
        duration_ms=duration_ms,
    )
    return result or state


def emit_lane_router_decided(
    state: dict[str, Any] | None,
    *,
    trace_id: str | None,
    match_path: str,
    initial_tier: str,
    resolved_tier: str,
    processing_lane: str,
    route_reason: str = "",
) -> dict[str, Any] | None:
    return emit_planning_event(
        state,
        event="lane_router.decided",
        node_name="lane_router",
        decision_reason="lane_router_decided",
        payload={
            "trace_id": trace_id,
            "match_path": match_path,
            "initial_tier": initial_tier,
            "resolved_tier": resolved_tier,
            "catalogue_tier": resolved_tier,
            "processing_lane": processing_lane,
            "route_reason": route_reason,
        },
    )


def emit_known_completeness_evaluated(state: dict[str, Any] | None, result: dict[str, Any]) -> dict[str, Any] | None:
    return emit_planning_event(
        state,
        event="known_completeness.evaluated",
        node_name="known_detail_completion",
        decision_reason="known_completeness_evaluated",
        payload=result,
    )


def emit_guided_resolution_started(state: dict[str, Any] | None, handoff_id: str, **extra: Any) -> dict[str, Any] | None:
    return emit_planning_event(
        state,
        event="guided_resolution.started",
        node_name="guided_detail_resolution",
        decision_reason="guided_resolution_started",
        payload={"handoff_id": handoff_id, **extra},
    )


def emit_tier_resolved(
    state: dict[str, Any] | None,
    *,
    initial_tier: str,
    resolved_tier: str,
    processing_lane: str,
    **extra: Any,
) -> dict[str, Any] | None:
    return emit_planning_event(
        state,
        event="tier.resolved",
        node_name="tier_resolver",
        decision_reason="tier_resolved",
        payload={
            "initial_tier": initial_tier,
            "resolved_tier": resolved_tier,
            "processing_lane": processing_lane,
            **extra,
        },
    )


def emit_detail_tool_event(
    state: dict[str, Any] | None,
    *,
    event_suffix: str,
    tool: str,
    handoff_id: str,
    handoff_version: int | None = None,
    tool_call_id: str | None = None,
    status: str = "completed",
    error_category: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    event = f"detail_tool.{event_suffix}"
    payload: dict[str, Any] = {
        "handoff_id": handoff_id,
        "handoff_version": handoff_version,
        "selected_tools": [tool],
        "tool_call_ids": [tool_call_id] if tool_call_id else [],
        "tool_statuses": {tool: status},
        "status": status,
    }
    if error_category:
        payload["error_category"] = error_category
    if extra:
        payload.update(extra)
    return emit_planning_event(
        state,
        event=event,
        node_name="detail_tool",
        decision_reason=event,
        payload=payload,
    )


def emit_detail_merge_completed(state: dict[str, Any] | None, payload: dict[str, Any]) -> dict[str, Any] | None:
    return emit_planning_event(
        state,
        event="detail_merge.completed",
        node_name="detail_merge",
        decision_reason="detail_merge_completed",
        payload=payload,
    )


def emit_post_guided_completeness_evaluated(state: dict[str, Any] | None, payload: dict[str, Any]) -> dict[str, Any] | None:
    return emit_planning_event(
        state,
        event="post_guided_completeness.evaluated",
        node_name="post_guided_completeness",
        decision_reason="post_guided_completeness_evaluated",
        payload=payload,
    )


def emit_clarification_requested(state: dict[str, Any] | None, payload: dict[str, Any]) -> dict[str, Any] | None:
    return emit_planning_event(
        state,
        event="clarification.requested",
        node_name="clarification",
        decision_reason="clarification_requested",
        payload=payload,
    )


def emit_planner_handoff_created(state: dict[str, Any] | None, canonical: CanonicalPlanningInput) -> dict[str, Any] | None:
    return emit_planning_event(
        state,
        event="planner_handoff.created",
        node_name="canonical_handoff_builder",
        decision_reason="planner_handoff_created",
        payload=decision_payload_from_canonical(canonical),
    )


def emit_planner_handoff_consumed(
    state: dict[str, Any] | None,
    canonical: CanonicalPlanningInput,
    *,
    consumed_fields: list[str],
    ignored_fields: list[str],
    resource_plan_id: str,
) -> dict[str, Any] | None:
    return emit_planning_event(
        state,
        event="planner_handoff.consumed",
        node_name="plan_evidence_from_canonical",
        decision_reason="planner_handoff_consumed",
        payload={
            **decision_payload_from_canonical(canonical),
            "consumed_fields": consumed_fields,
            "ignored_fields": ignored_fields,
            "defaulted_fields": [],
            "resource_plan_id": resource_plan_id,
        },
    )


def emit_resource_plan_created(
    state: dict[str, Any] | None,
    canonical: CanonicalPlanningInput,
    *,
    resource_plan_id: str,
) -> dict[str, Any] | None:
    return emit_planning_event(
        state,
        event="resource_plan.created",
        node_name="plan_evidence_from_canonical",
        decision_reason="resource_plan_created",
        payload={
            "resource_plan_id": resource_plan_id,
            "handoff_id": canonical.trace.handoff_id,
            "handoff_version": canonical.trace.handoff_version,
            "processing_lane": canonical.routing.processing_lane,
        },
    )


def emit_execution_event(
    state: dict[str, Any],
    *,
    event: str,
    resource_plan_id: str | None = None,
    handoff_id: str | None = None,
    handoff_version: int | None = None,
    status: str = "completed",
    error_category: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "resource_plan_id": resource_plan_id,
        "handoff_id": handoff_id,
        "handoff_version": handoff_version,
        "trace_id": state.get("trace_id"),
        "status": status,
    }
    if error_category:
        payload["error_category"] = error_category
    if extra:
        payload.update(extra)
    result = emit_planning_event(
        state,
        event=event,
        node_name="execution",
        decision_reason=event,
        payload=payload,
    )
    return result or state


def decision_payload_from_canonical(canonical: CanonicalPlanningInput) -> dict[str, Any]:
    return {
        "handoff_id": canonical.trace.handoff_id,
        "handoff_version": canonical.trace.handoff_version,
        "trace_id": canonical.trace.trace_id,
        "initial_tier": canonical.routing.initial_tier,
        "resolved_tier": canonical.routing.resolved_tier,
        "match_path": canonical.routing.match_path,
        "catalogue_tier": canonical.routing.catalogue_tier,
        "processing_lane": canonical.routing.processing_lane,
        "primary_skill": canonical.routing.primary_skill,
        "original_skill": canonical.routing.original_skill,
        "intent_family": canonical.routing.intent_family,
        "intent_source": canonical.routing.intent_source,
        "answer_goal": canonical.routing.answer_goal,
        "route_reason": canonical.routing.route_reason,
        "present_fields": canonical.detail_state.present_fields,
        "missing_fields": canonical.detail_state.missing_fields,
        "missing_field_categories": {
            **{k: "planner_required" for k in canonical.detail_state.planner_required_fields},
            **{k: "tool_discoverable" for k in canonical.detail_state.tool_discoverable_fields},
            **{k: "user_only" for k in canonical.detail_state.user_only_fields},
        },
        "resolved_fields": canonical.guided_resolution.resolved_fields,
        "unresolved_fields": canonical.guided_resolution.unresolved_fields,
        "selected_tools": canonical.guided_resolution.selected_tools,
        "tool_statuses": canonical.guided_resolution.tool_statuses,
        "retry_count": canonical.guided_resolution.retry_count,
    }
