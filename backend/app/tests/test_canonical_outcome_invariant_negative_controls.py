"""Post-gate and pre-gate negative controls for canonical outcome invariant."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.chat.canonical_outcome_gate import enforce_canonical_outcome_invariant
from app.chat.canonical_outcome_read import OutcomeReadKind, read_canonical_planning_outcome
from app.chat.contracts.canonical_planning_outcome import (
    clarification_outcome,
    planned_outcome,
    policy_blocked_outcome,
)
from app.config import settings
from app.graph.resource_planner_graph import _rp_dispatch_route
from app.tests.support.canonical_flow import run_canonical_flow

_CANONICAL_INPUT = {"routing": {"processing_lane": "guided", "resolved_tier": "T4"}}
_EP = {"answer_mode": "live_investigation", "resource_plan": {"provenance": {"committed": True}}}
_RP = {"provenance": {"committed": True, "resource_plan_id": "rp-neg"}, "steps": []}


@pytest.fixture(autouse=True)
def _canonical_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    monkeypatch.setattr(settings, "telemetry_mode", "none")


@pytest.mark.parametrize(
    "corrupt_state",
    [
        {"canonical_planning_outcome": {"status": "planned"}},
        {"canonical_planning_outcome": "not-a-dict"},
        {
            "canonical_planning_outcome": policy_blocked_outcome(
                canonical_input=_CANONICAL_INPUT,
                policy_reason="unsafe_action_blocked",
            ).model_dump(),
            "evidence_plan": {"answer_mode": "workflow_spl"},
        },
        {
            "canonical_planning_outcome": clarification_outcome(
                canonical_input=_CANONICAL_INPUT,
                question="Which host?",
                unresolved_fields=["host"],
                handoff_id="h-neg",
                handoff_version=1,
            ).model_dump(),
            "evidence_plan": {"answer_mode": "clarification"},
        },
    ],
    ids=["malformed_planned", "malformed_type", "policy_with_ep", "clarification_with_ep"],
)
def test_pre_gate_corrupt_states_fail_closed_after_gate(corrupt_state: dict) -> None:
    state = enforce_canonical_outcome_invariant(
        {
            **corrupt_state,
            "trace_id": "neg-pre",
            "session_id": "sess",
        }
    )
    read = read_canonical_planning_outcome(state)
    assert read.kind == OutcomeReadKind.VALID
    assert read.outcome is not None
    assert read.outcome.status in {"planning_failed", "policy_blocked", "resolution_failed"}
    if read.outcome.status == "planning_failed":
        assert "evidence_plan" not in state
    route = _rp_dispatch_route(state)
    assert route == "non_planned_finalize"


def test_post_gate_missing_outcome_still_non_planned_route() -> None:
    state = enforce_canonical_outcome_invariant({"trace_id": "neg-miss", "session_id": "sess"})
    assert _rp_dispatch_route(state) == "non_planned_finalize"


def test_post_gate_stale_ep_without_outcome_normalized() -> None:
    state = enforce_canonical_outcome_invariant(
        {
            "evidence_plan": {"answer_mode": "workflow_spl", "needs_spl": True},
            "trace_id": "neg-stale",
            "session_id": "sess",
        }
    )
    assert "evidence_plan" not in state
    assert _rp_dispatch_route(state) == "non_planned_finalize"


def test_valid_planned_still_dispatchable() -> None:
    outcome = planned_outcome(
        canonical_input=_CANONICAL_INPUT,
        evidence_plan=_EP,
        resource_plan=_RP,
    )
    state = enforce_canonical_outcome_invariant(
        {
            "canonical_planning_outcome": outcome.model_dump(),
            "evidence_plan": _EP,
            "trace_id": "neg-ok",
            "session_id": "sess",
        }
    )
    read = read_canonical_planning_outcome(state)
    assert read.outcome is not None and read.outcome.status == "planned"
    route = _rp_dispatch_route(state)
    assert route in {"workflow_spl", "composed_dispatch", "rag_only"}


def test_policy_live_query_not_clarification() -> None:
    result = run_canonical_flow("Block IP 10.0.0.5 immediately", trace_id="neg-policy")
    read = read_canonical_planning_outcome(result.state)
    assert read.outcome is not None
    assert read.outcome.status == "policy_blocked"
    assert read.outcome.status != "clarification_required"
