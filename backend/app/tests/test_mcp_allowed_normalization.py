from __future__ import annotations

from app.chat.pipeline import _mcp_allowed
from app.chat.run_contract_builder import _resolve_mcp_allowed
from app.config import settings


def test_mcp_allowed_none_normalizes_to_blocked_gate_without_route_replace(monkeypatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)

    assert _mcp_allowed({"evidence_plan": {"needs_mcp": True, "mcp_allowed": None}}) is False
    assert _mcp_allowed({"evidence_plan": {"needs_mcp": True}}) is False
    assert _mcp_allowed({"evidence_plan": {"needs_mcp": True, "mcp_allowed": False}}) is False
    assert _mcp_allowed({"evidence_plan": {"needs_mcp": True, "mcp_allowed": True}}) is True


def test_run_contract_mcp_allowed_projection_fails_closed_for_none(monkeypatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)

    assert _resolve_mcp_allowed({}, {"needs_mcp": True, "mcp_allowed": None}) is False
    assert _resolve_mcp_allowed({}, {"needs_mcp": True}) is False
    assert _resolve_mcp_allowed({}, {"needs_mcp": True, "mcp_allowed": False}) is False
    assert _resolve_mcp_allowed({}, {"needs_mcp": True, "mcp_allowed": True}) is True


def test_cp_off_run_contract_projection_only_reports_authorized_execution(monkeypatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", False)

    assert _resolve_mcp_allowed({}, {}, execution_authorized=False) is False
    assert _resolve_mcp_allowed({}, {}, execution_authorized=True) is True
