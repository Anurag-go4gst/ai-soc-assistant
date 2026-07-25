"""Response-layer validation before final chat emission."""

from __future__ import annotations

from typing import Any, Literal

from app.chat.contracts.canonical_planning_outcome import (
    NON_EXECUTING_STATUSES,
    outcome_from_state,
)
from app.chat.durable_planning_telemetry import persist_planning_event
from app.chat.planning_telemetry import emit_planning_event
from app.planner.resource_plan import ResourcePlan

ValidationOutcome = Literal["ok", "failed"]


def validate_final_response(state: dict[str, Any]) -> tuple[ValidationOutcome, list[str]]:
    """Validate committed plan execution before response generation.

    Branches on ``CanonicalPlanningOutcome.status`` first. Only a ``planned`` outcome
    has an EvidencePlan and a committed ResourcePlan to validate; requiring them
    unconditionally failed every clarification turn.
    """
    reasons: list[str] = []
    outcome = outcome_from_state(state)

    if outcome is not None and outcome.status == "clarification_required":
        clarification = outcome.clarification
        if clarification is None or not clarification.unresolved_fields:
            reasons.append("clarification_missing_unresolved_fields")
        if clarification is None or not clarification.question:
            reasons.append("clarification_missing_question")
        if clarification is not None and not clarification.handoff_id:
            reasons.append("clarification_handoff_not_persisted")
        if state.get("evidence_plan") is not None:
            reasons.append("clarification_must_not_carry_evidence_plan")
        return ("failed", reasons) if reasons else ("ok", [])

    if outcome is not None and outcome.status != "planned":
        # Policy block or typed failure: nothing was planned or executed. Report the
        # typed outcome honestly rather than as a missing-plan validation failure.
        if outcome.status in NON_EXECUTING_STATUSES and outcome.resource_plan is not None:
            reasons.append("non_planned_outcome_carries_resource_plan")
        return ("failed", reasons) if reasons else ("ok", [])

    evidence = state.get("evidence_plan")
    if not isinstance(evidence, dict):
        reasons.append("missing_evidence_plan")
        return "failed", reasons

    resource_payload = evidence.get("resource_plan")
    if not isinstance(resource_payload, dict):
        reasons.append("missing_resource_plan")
        return "failed", reasons

    plan = ResourcePlan.model_validate(resource_payload)
    provenance = plan.provenance or {}
    plan_id = provenance.get("resource_plan_id")
    executed_id = (state.get("plan_dispatch_trace") or {}).get("resource_plan_id")
    if plan_id and executed_id and plan_id != executed_id:
        reasons.append("resource_plan_id_mismatch")

    if evidence.get("canonical_failure"):
        reasons.append("canonical_failure_present")

    if evidence.get("answer_mode") == "clarification" and not evidence.get("clarification_questions"):
        reasons.append("clarification_suppressed")

    # All planned steps should have terminal status when dispatch completed
    dispatch = state.get("plan_dispatch_trace") or {}
    if dispatch.get("dispatch_source") == "plan_dispatch" and plan.steps:
        terminal = {"executed", "skipped_unavailable", "blocked_policy", "not_run", "not_onboarded", "fallback_taken"}
        if any(step.status == "planned" for step in plan.steps):
            reasons.append("incomplete_plan_steps")

    return ("failed", reasons) if reasons else ("ok", [])


def emit_response_validated(state: dict[str, Any], *, ok: bool, reasons: list[str]) -> dict[str, Any]:
    payload = {
        "trace_id": state.get("trace_id"),
        "session_id": state.get("session_id"),
        "status": "completed" if ok else "failed",
        "validation_reasons": reasons,
        "node_name": "response_validation",
    }
    persist_planning_event({**payload, "event": "response.validated"})
    return emit_planning_event(
        state,
        event="response.validated",
        node_name="response_validation",
        decision_reason="response_layer_validation",
        payload=payload,
    ) or state


def emit_response_generated(state: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "trace_id": state.get("trace_id"),
        "session_id": state.get("session_id"),
        "status": "completed",
        "node_name": "response_assembly",
    }
    persist_planning_event({**payload, "event": "response.generated"})
    return emit_planning_event(
        state,
        event="response.generated",
        node_name="response_assembly",
        decision_reason="final_response_assembled",
        payload=payload,
    ) or state


def emit_request_failed(state: dict[str, Any], *, reason: str, error_category: str = "response_validation") -> dict[str, Any]:
    payload = {
        "trace_id": state.get("trace_id"),
        "session_id": state.get("session_id"),
        "status": "failed",
        "reason": reason,
        "error_category": error_category,
        "node_name": "request_terminal",
    }
    persist_planning_event({**payload, "event": "request.failed"})
    return emit_planning_event(
        state,
        event="request.failed",
        node_name="request_terminal",
        decision_reason=reason,
        payload=payload,
    ) or state
