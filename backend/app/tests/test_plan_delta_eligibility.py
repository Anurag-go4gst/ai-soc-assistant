"""PlanDelta reasoning eligibility — timing owner is context_sufficiency routing."""

from __future__ import annotations

from app.config import settings
from app.graph.resource_planner_graph import (
    _rp_after_context_sufficiency,
    plan_delta_reasoning_eligible,
)


def _state(**updates: object) -> dict:
    payload: dict = {
        "approved_investigation_envelope": {
            "envelope_version": 2,
            "plan_delta_policy": {"automatic_bounded_read_only_delta_allowed": True},
            "allowed_read_only_capabilities": ["mcp:splunk_soc:splunk_run_query"],
        },
        "investigation_approval": {"status": "approved"},
        "investigation_run_status": {
            "status": "incomplete",
            "missing_evidence": ["network_flows"],
        },
        "execution": {"status": "executed"},
        "human_review": {"required": False},
        "source_evidence": [
            {
                "evidence_id": "ev_prior",
                "source_type": "splunk_mcp",
                "collection_status": "collected",
            }
        ],
    }
    payload.update(updates)
    return payload


def test_hil_waiting_blocks_plandelta(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_plan_delta_enabled", True)
    state = _state(execution={"status": "requires_human_review"})
    eligible, reason = plan_delta_reasoning_eligible(state)
    assert eligible is False
    assert reason == "current_read_not_terminal"
    assert _rp_after_context_sufficiency(state) == "decide_facts"


def test_execution_confirmation_review_blocks_plandelta(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_plan_delta_enabled", True)
    state = _state(
        execution={"status": "planned"},
        human_review={"required": True, "review_type": "spl_execution_confirmation"},
    )
    eligible, reason = plan_delta_reasoning_eligible(state)
    assert eligible is False
    assert reason in {"awaiting_tool_confirmation", "current_read_not_terminal"}


def test_pending_execution_blocks_plandelta(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_plan_delta_enabled", True)
    state = _state(execution={"status": "not_started"})
    eligible, reason = plan_delta_reasoning_eligible(state)
    assert eligible is False
    assert reason == "current_read_not_terminal"


def test_awaiting_plan_approval_blocks_plandelta(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_plan_delta_enabled", True)
    state = _state(investigation_approval={"status": "awaiting_approval"})
    eligible, reason = plan_delta_reasoning_eligible(state)
    assert eligible is False
    assert reason == "awaiting_plan_approval"


def test_post_terminal_read_with_material_gap_allows_plandelta(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_plan_delta_enabled", True)
    state = _state()
    eligible, reason = plan_delta_reasoning_eligible(state)
    assert eligible is True
    assert reason == "post_terminal_read_material_gap"
    assert _rp_after_context_sufficiency(state) == "plan_delta_reasoner"


def test_sufficient_run_does_not_run_plandelta(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_plan_delta_enabled", True)
    state = _state(investigation_run_status={"status": "sufficient", "missing_evidence": []})
    eligible, reason = plan_delta_reasoning_eligible(state)
    assert eligible is False
    assert reason == "no_material_gap"
    assert _rp_after_context_sufficiency(state) == "decide_facts"


def test_terminal_failure_may_allow_plandelta(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_plan_delta_enabled", True)
    state = _state(execution={"status": "failed", "block_reason": "tool_error"})
    eligible, reason = plan_delta_reasoning_eligible(state)
    assert eligible is True
    assert reason == "post_terminal_read_material_gap"


def test_executed_without_admitted_source_evidence_blocks_plandelta(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_plan_delta_enabled", True)
    state = _state(source_evidence=[])
    eligible, reason = plan_delta_reasoning_eligible(state)
    assert eligible is False
    assert reason == "source_evidence_not_admitted"


def test_executed_with_admitted_source_evidence_allows_plandelta(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_plan_delta_enabled", True)
    state = _state(
        source_evidence=[
            {
                "evidence_id": "ev_1",
                "source_type": "splunk_mcp",
                "collection_status": "collected",
            }
        ]
    )
    eligible, reason = plan_delta_reasoning_eligible(state)
    assert eligible is True
    assert reason == "post_terminal_read_material_gap"


def test_no_follow_up_capability_stops_honestly(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_plan_delta_enabled", True)
    envelope = {
        "envelope_version": 2,
        "plan_delta_policy": {"automatic_bounded_read_only_delta_allowed": True},
        "allowed_read_only_capabilities": [],
    }
    state = _state(approved_investigation_envelope=envelope)
    eligible, reason = plan_delta_reasoning_eligible(state)
    assert eligible is False
    assert reason == "no_follow_up_capability"
