"""One named test per CanonicalPlanningOutcome status, plus the invariant guards."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.chat.contracts.canonical_planning_outcome import (
    FAILURE_STATUSES,
    CanonicalPlanningOutcome,
    clarification_outcome,
    failure_outcome,
    outcome_from_state,
    planned_outcome,
    policy_blocked_outcome,
)

_CANONICAL_INPUT = {"routing": {"processing_lane": "guided", "resolved_tier": "T4"}}
_EVIDENCE_PLAN = {"answer_mode": "live_investigation", "mcp_allowed": False}
_RESOURCE_PLAN = {"provenance": {"resource_plan_id": "rp-1"}, "steps": []}


def test_outcome_planned() -> None:
    outcome = planned_outcome(
        canonical_input=_CANONICAL_INPUT,
        evidence_plan=_EVIDENCE_PLAN,
        resource_plan=_RESOURCE_PLAN,
    )
    assert outcome.status == "planned"
    assert outcome.is_planned and outcome.is_executable
    assert outcome.resource_plan == _RESOURCE_PLAN


def test_outcome_clarification_required() -> None:
    outcome = clarification_outcome(
        canonical_input=_CANONICAL_INPUT,
        question="Which host should I scope the investigation to?",
        unresolved_fields=["host"],
        handoff_id="h-1",
        handoff_version=1,
        reason="known_clarification",
    )
    assert outcome.status == "clarification_required"
    assert outcome.evidence_plan is None
    assert outcome.resource_plan is None
    assert not outcome.is_executable
    assert outcome.clarification is not None
    assert outcome.clarification.unresolved_fields == ["host"]
    assert outcome.clarification.handoff_id == "h-1"


def test_outcome_policy_blocked() -> None:
    outcome = policy_blocked_outcome(
        canonical_input=_CANONICAL_INPUT,
        policy_reason="unsafe_execution_request",
    )
    assert outcome.status == "policy_blocked"
    assert outcome.resource_plan is None
    assert not outcome.is_executable


def test_outcome_resolution_failed() -> None:
    outcome = failure_outcome("resolution_failed", category="detail_tool", reason="tool_unavailable")
    assert outcome.status == "resolution_failed"
    assert outcome.failure is not None and outcome.failure.category == "detail_tool"
    assert outcome.evidence_plan is None and outcome.resource_plan is None


def test_outcome_planning_failed() -> None:
    outcome = failure_outcome("planning_failed", category="planner", reason="no_plan_produced")
    assert outcome.status == "planning_failed"
    assert not outcome.is_executable


def test_outcome_unsupported() -> None:
    outcome = failure_outcome("unsupported", category="route", reason="out_of_scope_request")
    assert outcome.status == "unsupported"


def test_outcome_execution_failed() -> None:
    outcome = failure_outcome("execution_failed", category="mcp", reason="search_timeout")
    assert outcome.status == "execution_failed"


def test_outcome_persistence_failed() -> None:
    outcome = failure_outcome("persistence_failed", category="database", reason="handoff_write_failed")
    assert outcome.status == "persistence_failed"


@pytest.mark.parametrize("status", sorted(FAILURE_STATUSES | {"clarification_required", "policy_blocked"}))
def test_non_planned_outcome_rejects_resource_plan(status: str) -> None:
    with pytest.raises(ValidationError):
        CanonicalPlanningOutcome.model_validate(
            {
                "status": status,
                "resource_plan": _RESOURCE_PLAN,
                "clarification": {
                    "question": "q",
                    "unresolved_fields": ["host"],
                    "handoff_id": "h-1",
                    "handoff_version": 1,
                },
                "failure": {"category": "c", "reason": "r"},
                "policy_reason": "blocked",
            }
        )


def test_clarification_outcome_rejects_evidence_plan() -> None:
    """The exact regression: a partial EvidencePlan on the clarification path."""
    with pytest.raises(ValidationError):
        CanonicalPlanningOutcome.model_validate(
            {
                "status": "clarification_required",
                "evidence_plan": {"answer_mode": "clarification", "resource_plan": None},
                "clarification": {
                    "question": "q",
                    "unresolved_fields": ["host"],
                    "handoff_id": "h-1",
                    "handoff_version": 1,
                },
            }
        )


def test_clarification_outcome_requires_unresolved_fields() -> None:
    with pytest.raises(ValidationError):
        clarification_outcome(
            canonical_input=None,
            question="q",
            unresolved_fields=[],
            handoff_id="h-1",
            handoff_version=1,
        )


def test_planned_outcome_requires_committed_resource_plan() -> None:
    with pytest.raises(ValidationError):
        CanonicalPlanningOutcome.model_validate(
            {"status": "planned", "canonical_input": _CANONICAL_INPUT, "evidence_plan": _EVIDENCE_PLAN}
        )


def test_outcome_round_trips_through_pipeline_state() -> None:
    outcome = clarification_outcome(
        canonical_input=_CANONICAL_INPUT,
        question="Which host?",
        unresolved_fields=["host"],
        handoff_id="h-9",
        handoff_version=2,
    )
    restored = outcome_from_state({"canonical_planning_outcome": outcome.model_dump()})
    assert restored is not None
    assert restored.status == "clarification_required"
    assert restored.clarification is not None
    assert restored.clarification.handoff_version == 2
    assert outcome_from_state({}) is None
