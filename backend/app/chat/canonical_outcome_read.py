"""Tri-state reader for CanonicalPlanningOutcome on pipeline state.

Production dispatch, validation, and the invariant gate must use
``read_canonical_planning_outcome`` — never collapse malformed payloads into absent.
``outcome_from_state`` remains for backward-compatible reads until all callers migrate.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import ValidationError

from app.chat.contracts.canonical_planning_outcome import (
    FAILURE_STATUSES,
    NON_EXECUTING_STATUSES,
    CanonicalPlanningOutcome,
)

_EXECUTED_STATUSES = frozenset(
    {
        "executed",
        "executed_mock_evidence",
        "executed_live_evidence",
        "success",
    }
)


class OutcomeReadKind(str, Enum):
    VALID = "valid"
    ABSENT = "absent"
    MALFORMED = "malformed"


@dataclass(frozen=True)
class OutcomeReadResult:
    kind: OutcomeReadKind
    outcome: CanonicalPlanningOutcome | None = None
    error: str | None = None


def read_canonical_planning_outcome(state: dict[str, Any]) -> OutcomeReadResult:
    """Parse ``canonical_planning_outcome`` without collapsing malformed into absent."""
    raw = state.get("canonical_planning_outcome")
    if raw is None:
        return OutcomeReadResult(kind=OutcomeReadKind.ABSENT)
    if isinstance(raw, CanonicalPlanningOutcome):
        return OutcomeReadResult(kind=OutcomeReadKind.VALID, outcome=raw)
    if isinstance(raw, dict):
        try:
            outcome = CanonicalPlanningOutcome.model_validate(raw)
        except ValidationError as exc:
            return OutcomeReadResult(kind=OutcomeReadKind.MALFORMED, error=str(exc))
        return OutcomeReadResult(kind=OutcomeReadKind.VALID, outcome=outcome)
    return OutcomeReadResult(
        kind=OutcomeReadKind.MALFORMED,
        error=f"unexpected canonical_planning_outcome type: {type(raw).__name__}",
    )


def _state_resource_plan_committed(state: dict[str, Any]) -> bool:
    evidence = state.get("evidence_plan")
    if not isinstance(evidence, dict):
        return False
    resource = evidence.get("resource_plan")
    if not isinstance(resource, dict):
        return False
    provenance = resource.get("provenance") or {}
    return bool(provenance.get("committed"))


def validate_cross_state_consistency(
    state: dict[str, Any],
    outcome: CanonicalPlanningOutcome,
) -> list[str]:
    """Return violation codes when typed outcome and pipeline state disagree."""
    reasons: list[str] = []
    status = outcome.status
    state_ep = state.get("evidence_plan")

    if status == "planned":
        if not isinstance(state_ep, dict):
            reasons.append("planned_outcome_missing_state_evidence_plan")
        elif state_ep.get("canonical_failure"):
            reasons.append("planned_outcome_with_canonical_failure_on_ep")
        if outcome.resource_plan:
            provenance = outcome.resource_plan.get("provenance") or {}
            if not provenance.get("committed"):
                reasons.append("planned_outcome_rp_not_committed")
        if _state_resource_plan_committed(state) and outcome.resource_plan is None:
            reasons.append("planned_state_ep_committed_without_outcome_rp")

    elif status == "clarification_required":
        if state_ep is not None:
            reasons.append("clarification_with_evidence_plan_in_state")
        if _state_resource_plan_committed(state):
            reasons.append("clarification_with_committed_resource_plan_in_state")

    elif status == "policy_blocked":
        if outcome.resource_plan is not None:
            reasons.append("policy_blocked_outcome_carries_resource_plan")
        if _state_resource_plan_committed(state):
            reasons.append("policy_blocked_with_committed_resource_plan_in_state")
        execution = state.get("execution")
        if isinstance(execution, dict) and str(execution.get("status") or "") in _EXECUTED_STATUSES:
            reasons.append("policy_blocked_with_executed_execution")

    elif status in NON_EXECUTING_STATUSES:
        if outcome.resource_plan is not None:
            reasons.append(f"{status}_outcome_carries_resource_plan")
        if _state_resource_plan_committed(state):
            reasons.append(f"{status}_with_committed_resource_plan_in_state")

    return list(dict.fromkeys(reasons))
