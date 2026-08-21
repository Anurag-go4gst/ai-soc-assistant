"""P3/P7 reasoning hops must be bounded by the turn wall-clock budget.

A reasoning endpoint that is unreachable, or merely very slow, must degrade to the
deterministic baseline inside the turn deadline instead of stalling ``/chat``. These
tests pin the bound itself, not model quality.
"""

from __future__ import annotations

import time

import pytest

from app.chat.contracts.investigation_envelope import ApprovedInvestigationEnvelope
from app.chat.guided_investigation_plan_llm import (
    INVESTIGATION_PLAN_ROLE,
    _hop_timeout_seconds,
    propose_investigation_plan_llm,
)
from app.chat.investigation_plan_builder import build_deterministic_investigation_plan
from app.chat.investigation_plan_delta_reasoner import (
    PLAN_DELTA_ROLE,
    _delta_hop_timeout_seconds,
    propose_plan_delta,
)
from app.llm.sidecar_clients import sidecar_timeout_seconds
from app.llm.turn_llm_budget import TurnLlmBudget


def _baseline():
    return build_deterministic_investigation_plan(
        query="investigate suspicious ssh logins",
        entities=None,
        resolved_query_contract={},
        capability_snapshot={},
    )


def _envelope() -> ApprovedInvestigationEnvelope:
    return ApprovedInvestigationEnvelope(
        envelope_version=2,
        objective="scope suspicious ssh logins",
        targets=["host-a"],
        entities={"src_ip": "203.0.113.45"},
        time_scope="last_7_days",
        allowed_read_only_capabilities=["splunk_search"],
    )


def test_role_timeouts_are_registered_for_both_reasoning_roles() -> None:
    assert sidecar_timeout_seconds(INVESTIGATION_PLAN_ROLE) == 120.0
    assert sidecar_timeout_seconds(PLAN_DELTA_ROLE) == 30.0


def test_planner_hop_timeout_is_capped_to_remaining_turn_budget() -> None:
    budget = TurnLlmBudget(deadline_seconds=20.0)
    capped = _hop_timeout_seconds(budget)
    assert capped is not None
    assert capped <= 20.0, "planner hop must not outlive the turn deadline"


def test_planner_hop_without_budget_keeps_role_timeout() -> None:
    assert _hop_timeout_seconds(None) == 120.0


def test_planner_skips_llm_when_turn_budget_exhausted() -> None:
    budget = TurnLlmBudget(deadline_seconds=0.01)
    time.sleep(0.02)
    result = propose_investigation_plan_llm(
        query="investigate suspicious ssh logins",
        baseline=_baseline(),
        turn_budget=budget,
    )
    assert result.attempted is False
    assert result.proposal is None
    assert "turn_budget_exhausted" in result.dropped_reasons


def test_plan_delta_hop_timeout_is_capped_to_remaining_turn_budget() -> None:
    budget = TurnLlmBudget(deadline_seconds=5.0)
    capped = _delta_hop_timeout_seconds(budget)
    assert capped is not None
    assert capped <= 5.0


def test_plan_delta_without_budget_keeps_role_timeout() -> None:
    assert _delta_hop_timeout_seconds(None) == 30.0


def test_plan_delta_skips_llm_when_turn_budget_exhausted() -> None:
    budget = TurnLlmBudget(deadline_seconds=0.01)
    time.sleep(0.02)
    result = propose_plan_delta(
        envelope=_envelope(),
        missing_evidence=["authentication_events"],
        turn_budget=budget,
    )
    assert result.proposal is None
    assert result.trace["attempted"] is False
    assert result.trace["skipped_reason"] == "turn_budget_exhausted"


@pytest.mark.parametrize("deadline", [1.0, 10.0, 60.0, 200.0])
def test_planner_hop_never_exceeds_role_ceiling_or_deadline(deadline: float) -> None:
    """A hop either fits inside both ceilings or is skipped — never unbounded."""
    capped = _hop_timeout_seconds(TurnLlmBudget(deadline_seconds=deadline))
    assert capped is None or capped <= min(120.0, deadline)
