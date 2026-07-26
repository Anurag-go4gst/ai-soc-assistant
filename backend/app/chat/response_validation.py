"""Response-layer validation before final chat emission (plan item 22).

Two phases:

1. ``validate_final_response`` — pre-assembly, branches on ``CanonicalPlanningOutcome``
   and validates committed plan / execution / evidence state.
2. ``validate_assembled_response`` — post-assembly, validates the analyst-visible envelope
   before ``response.generated`` / ``request.completed``.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Literal

from app.chat.contracts.canonical_planning_outcome import (
    NON_EXECUTING_STATUSES,
    outcome_from_state,
)
from app.chat.planning_telemetry import (
    _mark_terminal_request_event,
    emit_planning_event,
    terminal_request_event_emitted,
)
from app.planner.resource_plan import ResourcePlan

_LOGGER = logging.getLogger("ai_soc.response_validation")

ValidationOutcome = Literal["ok", "failed"]

_TERMINAL_STEP_STATUSES = frozenset(
    {
        "executed",
        "skipped_unavailable",
        "blocked_policy",
        "not_run",
        "not_onboarded",
        "fallback_taken",
        "failed",
        "failed_retryable",
        "failed_terminal",
    }
)

_EXECUTED_STATUSES = frozenset(
    {
        "executed",
        "executed_mock_evidence",
        "executed_live_evidence",
        "success",
    }
)

_REMEDIATION_CLAIM_PATTERN = re.compile(
    r"\b(was|were|has been|have been|successfully)\s+(applied|completed|executed|isolated|blocked|contained|remediated|disabled)\b"
    r"|\b(applied|completed|executed|isolated|blocked|contained|remediated|disabled)\s+(successfully|the host|host|account|ip)\b",
    flags=re.IGNORECASE,
)


def _finalize(reasons: list[str]) -> tuple[ValidationOutcome, list[str]]:
    deduped = list(dict.fromkeys(reasons))
    return ("failed", deduped) if deduped else ("ok", [])


def _primary_answer_goal(state: dict[str, Any]) -> str | None:
    contract = state.get("answer_contract")
    if isinstance(contract, dict):
        goals = contract.get("answer_goal") or []
        if goals:
            return str(goals[0])
        primary = contract.get("answer_goal_primary")
        if primary:
            return str(primary)
    intent = state.get("intent_classification")
    if isinstance(intent, dict):
        primary = intent.get("answer_goal_primary")
        if primary:
            return str(primary)
        goals = intent.get("answer_goal") or []
        if goals:
            return str(goals[0])
    cpi = state.get("canonical_planning_input")
    if isinstance(cpi, dict):
        routing = cpi.get("routing") or {}
        goal = routing.get("answer_goal")
        if goal:
            return str(goal)
    return None


def _has_source_evidence(state: dict[str, Any]) -> bool:
    evidence = state.get("source_evidence")
    if isinstance(evidence, list) and evidence:
        return True
    structured = state.get("structured_context")
    if isinstance(structured, dict):
        chunks = structured.get("chunks") or structured.get("rag_chunks") or []
        if chunks:
            return True
    return False


def _has_knowledge_citation(state: dict[str, Any], analyst_response: Any | None = None) -> bool:
    if analyst_response is not None:
        for field in ("reference_facts", "retrieved_playbook"):
            value = getattr(analyst_response, field, None)
            if value:
                return True
    return _has_source_evidence(state)


def _has_spl_artifact(state: dict[str, Any]) -> bool:
    spl_validation = state.get("spl_validation")
    if isinstance(spl_validation, dict) and spl_validation.get("approved"):
        return True
    candidate = state.get("candidate_spl")
    if isinstance(candidate, dict) and str(candidate.get("candidate_spl") or candidate.get("normalized_spl") or "").strip():
        return True
    return False


def _tool_failures_surfaced(state: dict[str, Any]) -> bool:
    gap = state.get("gap_resolution")
    if not isinstance(gap, dict):
        return True
    tool_statuses = gap.get("tool_statuses") or {}
    if not isinstance(tool_statuses, dict):
        return True
    failed_tools = [tool for tool, status in tool_statuses.items() if str(status) == "error"]
    if not failed_tools:
        return True
    limitations: list[str] = []
    evidence = state.get("evidence_plan")
    if isinstance(evidence, dict):
        limitations.extend(str(item) for item in evidence.get("limitations") or [])
    contract = state.get("answer_contract")
    if isinstance(contract, dict):
        limitations.extend(str(item) for item in contract.get("limitations") or [])
    joined = " ".join(limitations).lower()
    return any(str(tool).lower() in joined or "tool" in joined for tool in failed_tools)


def _validate_clarification(state: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    outcome = outcome_from_state(state)
    if outcome is None or outcome.status != "clarification_required":
        return reasons
    clarification = outcome.clarification
    if clarification is None or not clarification.unresolved_fields:
        reasons.append("clarification_missing_unresolved_fields")
    if clarification is None or not clarification.question:
        reasons.append("clarification_missing_question")
    if clarification is not None and not clarification.handoff_id:
        reasons.append("clarification_handoff_not_persisted")
    if state.get("evidence_plan") is not None:
        reasons.append("clarification_must_not_carry_evidence_plan")
    return reasons


def _validate_non_planned_outcome(state: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    outcome = outcome_from_state(state)
    if outcome is None or outcome.status == "planned":
        return reasons
    if outcome.status in NON_EXECUTING_STATUSES and outcome.resource_plan is not None:
        reasons.append("non_planned_outcome_carries_resource_plan")
    if outcome.status == "policy_blocked":
        execution = state.get("execution")
        if isinstance(execution, dict) and str(execution.get("status") or "") in _EXECUTED_STATUSES:
            reasons.append("policy_restriction_violated")
    return reasons


def _validate_planned_pipeline_state(state: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    evidence = state.get("evidence_plan")
    if not isinstance(evidence, dict):
        reasons.append("missing_evidence_plan")
        return reasons

    resource_payload = evidence.get("resource_plan")
    if not isinstance(resource_payload, dict):
        reasons.append("missing_resource_plan")
        return reasons

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

    if bool(provenance.get("committed")) and not plan_id:
        reasons.append("executable_missing_resource_plan_id")

    missing_required = evidence.get("missing_required_evidence") or []
    if missing_required and not (evidence.get("limitations") or []):
        reasons.append("missing_required_evidence")

    execution = state.get("execution") if isinstance(state.get("execution"), dict) else {}
    if evidence.get("mcp_allowed") is False and str(execution.get("status") or "") in _EXECUTED_STATUSES:
        reasons.append("policy_restriction_violated")

    if str(execution.get("status") or "") in {"failed", "failed_terminal", "failed_retryable"}:
        reasons.append("failed_execution_step")

    dispatch = state.get("plan_dispatch_trace") or {}
    if dispatch.get("dispatch_source") == "plan_dispatch" and plan.steps:
        if any(step.status == "planned" for step in plan.steps):
            reasons.append("incomplete_plan_steps")
        if any(str(step.status) in {"failed", "failed_terminal", "failed_retryable"} for step in plan.steps):
            reasons.append("failed_execution_step")

    if dispatch.get("dispatch_source") == "plan_dispatch" and str(execution.get("status") or "") == "running":
        reasons.append("execution_terminal_state_invalid")

    if not _tool_failures_surfaced(state):
        reasons.append("tool_failure_not_surfaced")

    answer_goal = _primary_answer_goal(state)
    if answer_goal in {"spl_artifact", "spl_generation"} and evidence.get("needs_spl") and not _has_spl_artifact(state):
        reasons.append("answer_goal_unsatisfied")

    if evidence.get("answer_mode") == "rag_only" and answer_goal in {
        "reference_lookup",
        "reference_explanation",
        "policy_citation",
        "knowledge_only",
    }:
        if not _has_knowledge_citation(state):
            reasons.append("missing_knowledge_citation")

    return reasons


def _validate_policy_blocked(state: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    outcome = outcome_from_state(state)
    if outcome is None or outcome.status != "policy_blocked":
        return reasons
    if not outcome.policy_reason:
        reasons.append("policy_blocked_missing_reason")
    if outcome.resource_plan is not None:
        reasons.append("policy_blocked_carrying_resource_plan")
    if state.get("evidence_plan") is not None and isinstance(state.get("evidence_plan"), dict):
        if state["evidence_plan"].get("resource_plan"):
            reasons.append("policy_blocked_carrying_resource_plan")
    execution = state.get("execution")
    if isinstance(execution, dict) and str(execution.get("status") or "") in _EXECUTED_STATUSES:
        reasons.append("policy_restriction_violated")
    return reasons


def validate_final_response(state: dict[str, Any]) -> tuple[ValidationOutcome, list[str]]:
    """Validate pipeline state before analyst-response assembly."""
    outcome = outcome_from_state(state)
    if outcome is not None and outcome.status == "clarification_required":
        return _finalize(_validate_clarification(state))

    if outcome is not None and outcome.status == "policy_blocked":
        return _finalize(_validate_policy_blocked(state))

    if outcome is not None and outcome.status != "planned":
        return _finalize(_validate_non_planned_outcome(state))

    return _finalize(_validate_planned_pipeline_state(state))


def _response_field_values(analyst_response: Any, field: str) -> list[str]:
    value = getattr(analyst_response, field, None)
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value]
    return []


def _claims_executed_remediation(analyst_response: Any) -> bool:
    for field in ("recommended_actions", "investigation_steps", "analyst_checklist", "direct_answer_summary"):
        for item in _response_field_values(analyst_response, field):
            if _REMEDIATION_CLAIM_PATTERN.search(item):
                return True
    return False


def validate_assembled_response(
    state: dict[str, Any],
    *,
    analyst_response: Any | None = None,
    answer_contract: dict[str, Any] | None = None,
) -> tuple[ValidationOutcome, list[str]]:
    """Validate the assembled analyst envelope before terminal success events."""
    if terminal_request_event_emitted(state) == "request.failed":
        return "ok", []

    reasons: list[str] = []
    outcome = outcome_from_state(state)
    if outcome is not None and outcome.status != "planned":
        return "ok", []

    response = analyst_response if analyst_response is not None else state.get("analyst_response")
    if response is None:
        reasons.append("response_assembly_failure")
        return _finalize(reasons)

    contract = answer_contract if answer_contract is not None else state.get("answer_contract")
    if isinstance(contract, dict):
        goals = [str(item) for item in contract.get("answer_goal") or []]
        profile = str(getattr(response, "response_profile", "") or "")
        if "analyst_action_guidance" in goals and profile == "spl_only":
            actions = _response_field_values(response, "recommended_actions")
            if not actions:
                reasons.append("answer_goal_unsatisfied")

    evidence = state.get("evidence_plan")
    if isinstance(evidence, dict) and evidence.get("answer_mode") == "rag_only":
        if not _has_knowledge_citation(state, response):
            reasons.append("missing_knowledge_citation")

    execution = state.get("execution") if isinstance(state.get("execution"), dict) else {}
    if _claims_executed_remediation(response) and str(execution.get("status") or "") not in _EXECUTED_STATUSES:
        reasons.append("unexecuted_remediation_claim")

    return _finalize(reasons)


def should_emit_response_generated(state: dict[str, Any]) -> bool:
    if terminal_request_event_emitted(state) is not None:
        return False
    return True


def emit_response_validated(state: dict[str, Any], *, ok: bool, reasons: list[str]) -> dict[str, Any]:
    payload = {
        "trace_id": state.get("trace_id"),
        "session_id": state.get("session_id"),
        "status": "completed" if ok else "failed",
        "validation_reasons": reasons,
        "node_name": "response_validation",
    }
    return emit_planning_event(
        state,
        event="response.validated",
        node_name="response_validation",
        decision_reason="response_layer_validation",
        payload=payload,
    ) or state


def emit_response_generated(state: dict[str, Any]) -> dict[str, Any]:
    if not should_emit_response_generated(state):
        return state
    payload = {
        "trace_id": state.get("trace_id"),
        "session_id": state.get("session_id"),
        "status": "completed",
        "node_name": "response_assembly",
    }
    return emit_planning_event(
        state,
        event="response.generated",
        node_name="response_assembly",
        decision_reason="final_response_assembled",
        payload=payload,
    ) or state


def emit_request_failed(state: dict[str, Any], *, reason: str, error_category: str = "response_validation") -> dict[str, Any]:
    if terminal_request_event_emitted(state) is not None:
        return state
    payload = {
        "trace_id": state.get("trace_id"),
        "session_id": state.get("session_id"),
        "status": "failed",
        "reason": reason,
        "error_category": error_category,
        "node_name": "request_terminal",
    }
    result = emit_planning_event(
        state,
        event="request.failed",
        node_name="request_terminal",
        decision_reason=reason,
        payload=payload,
        durable=True,
    )
    return _mark_terminal_request_event(result or state, "request.failed")
