"""Tests for tri-state canonical outcome reader and cross-state validators."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.chat.canonical_outcome_read import (
    OutcomeReadKind,
    read_canonical_planning_outcome,
    validate_cross_state_consistency,
)
from app.chat.contracts.canonical_planning_outcome import (
    clarification_outcome,
    planned_outcome,
    policy_blocked_outcome,
)

_CANONICAL_INPUT = {"routing": {"processing_lane": "guided"}}
_EVIDENCE_PLAN = {"answer_mode": "live_investigation", "resource_plan": {"provenance": {"committed": True}}}
_RESOURCE_PLAN = {"provenance": {"committed": True, "resource_plan_id": "rp-1"}, "steps": []}


def test_read_absent_when_key_missing() -> None:
    read = read_canonical_planning_outcome({})
    assert read.kind == OutcomeReadKind.ABSENT
    assert read.outcome is None


def test_read_malformed_does_not_collapse_to_absent() -> None:
    read = read_canonical_planning_outcome({"canonical_planning_outcome": {"status": "planned"}})
    assert read.kind == OutcomeReadKind.MALFORMED
    assert read.error


def test_read_valid_round_trip() -> None:
    outcome = clarification_outcome(
        canonical_input=_CANONICAL_INPUT,
        question="Which host?",
        unresolved_fields=["host"],
        handoff_id="h-1",
        handoff_version=1,
    )
    read = read_canonical_planning_outcome({"canonical_planning_outcome": outcome.model_dump()})
    assert read.kind == OutcomeReadKind.VALID
    assert read.outcome is not None
    assert read.outcome.status == "clarification_required"


def test_cross_state_clarification_rejects_evidence_plan() -> None:
    outcome = clarification_outcome(
        canonical_input=_CANONICAL_INPUT,
        question="Which host?",
        unresolved_fields=["host"],
        handoff_id="h-1",
        handoff_version=1,
    )
    reasons = validate_cross_state_consistency(
        {"evidence_plan": {"answer_mode": "clarification"}},
        outcome,
    )
    assert "clarification_with_evidence_plan_in_state" in reasons


def test_cross_state_planned_consistent_state() -> None:
    outcome = planned_outcome(
        canonical_input=_CANONICAL_INPUT,
        evidence_plan=_EVIDENCE_PLAN,
        resource_plan=_RESOURCE_PLAN,
    )
    reasons = validate_cross_state_consistency({"evidence_plan": _EVIDENCE_PLAN}, outcome)
    assert reasons == []


def test_cross_state_policy_blocked_rejects_committed_plan_in_state() -> None:
    outcome = policy_blocked_outcome(
        canonical_input=_CANONICAL_INPUT,
        policy_reason="unsafe_action_blocked",
    )
    reasons = validate_cross_state_consistency(
        {"evidence_plan": {"resource_plan": {"provenance": {"committed": True}}}},
        outcome,
    )
    assert "policy_blocked_with_committed_resource_plan_in_state" in reasons
