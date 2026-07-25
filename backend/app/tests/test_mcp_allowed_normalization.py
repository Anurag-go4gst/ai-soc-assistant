from __future__ import annotations

from app.chat.pipeline import _mcp_allowed, _mcp_allowed_decision_from_plan, _mcp_evidence_loop_enabled
from app.chat.run_contract_builder import _resolve_mcp_allowed
from app.config import settings


def test_mcp_allowed_none_normalizes_to_blocked_gate_without_route_replace(monkeypatch) -> None:

    assert _mcp_allowed({"evidence_plan": {"needs_mcp": True, "mcp_allowed": None}}) is False
    assert _mcp_allowed({"evidence_plan": {"needs_mcp": True}}) is False
    assert _mcp_allowed({"evidence_plan": {"needs_mcp": True, "mcp_allowed": False}}) is False
    assert _mcp_allowed({"evidence_plan": {"needs_mcp": True, "mcp_allowed": True}}) is True


def test_mcp_allowed_none_blocks_evidence_loop(monkeypatch) -> None:

    assert _mcp_evidence_loop_enabled({}, {"answer_mode": "live_investigation", "mcp_allowed": None}) is False
    assert _mcp_evidence_loop_enabled({}, {"answer_mode": "live_investigation"}) is False
    assert _mcp_evidence_loop_enabled({}, {"answer_mode": "live_investigation", "mcp_allowed": False}) is False


def test_mcp_allowed_normalized_trace_records_source(monkeypatch) -> None:

    assert _mcp_allowed_decision_from_plan({"mcp_allowed": None}) == {
        "allowed": False,
        "source": "evidence_plan_null",
        "reason": "mcp_allowed_null_fail_closed",
    }
    assert _mcp_allowed_decision_from_plan({}) == {
        "allowed": False,
        "source": "evidence_plan_missing",
        "reason": "mcp_allowed_unset_fail_closed",
    }
    assert _mcp_allowed_decision_from_plan({"mcp_allowed": False}) == {
        "allowed": False,
        "source": "evidence_plan",
        "reason": "explicit_false",
    }


def test_run_contract_mcp_allowed_projection_fails_closed_for_none(monkeypatch) -> None:

    assert _resolve_mcp_allowed({}, {"needs_mcp": True, "mcp_allowed": None}) is False
    assert _resolve_mcp_allowed({}, {"needs_mcp": True}) is False
    assert _resolve_mcp_allowed({}, {"needs_mcp": True, "mcp_allowed": False}) is False
    assert _resolve_mcp_allowed({}, {"needs_mcp": True, "mcp_allowed": True}) is True


def test_run_contract_mcp_allowed_false_when_spl_validation_not_approved(monkeypatch) -> None:

    assert (
        _resolve_mcp_allowed(
            {"spl_validation": {"approved": False, "reject_reasons": ["missing_binding:index"]}},
            {"needs_mcp": True, "mcp_allowed": True},
        )
        is False
    )


def test_cp_off_run_contract_projection_only_reports_authorized_execution(monkeypatch) -> None:

    assert _resolve_mcp_allowed({}, {}, execution_authorized=False) is False
    assert _resolve_mcp_allowed({}, {}, execution_authorized=True) is True
