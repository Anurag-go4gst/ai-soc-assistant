from __future__ import annotations

from app.connectors.mcp.mcp_tool_plan_shadow import run_mcp_tool_plan_shadow


def test_shadow_skips_when_no_mcp_or_spl_interest(monkeypatch) -> None:
    monkeypatch.setattr("app.connectors.mcp.mcp_tool_plan_shadow.settings.control_plane_enabled", False)
    assert run_mcp_tool_plan_shadow(query="hello", needs_mcp=False, needs_spl=False) is None


def test_shadow_returns_deterministic_plan_when_control_plane_on(monkeypatch) -> None:
    monkeypatch.setattr("app.connectors.mcp.mcp_tool_plan_shadow.settings.control_plane_enabled", True)
    monkeypatch.setattr(
        "app.connectors.mcp.mcp_tool_plan_shadow.mcp_tool_plan_llm_advisory_enabled",
        lambda: False,
    )
    out = run_mcp_tool_plan_shadow(
        query="critical alerts",
        target_index="pgcil_soc",
        spl_approved=True,
        session_role="analyst",
        needs_spl=True,
    )
    assert out is not None
    assert out["shadow_only"] is True
    assert out["rbac_role"] == "analyst"
    assert out["approved_tools"][-1] == "splunk_run_query"
    assert out["planner"]["llm_called"] is False


def test_unscoped_shadow_matches_gate_default_analyst(monkeypatch) -> None:
    monkeypatch.setattr("app.connectors.mcp.mcp_tool_plan_shadow.settings.control_plane_enabled", True)
    monkeypatch.setattr(
        "app.connectors.mcp.mcp_tool_plan_shadow.mcp_tool_plan_llm_advisory_enabled",
        lambda: False,
    )
    out = run_mcp_tool_plan_shadow(
        query="critical alerts",
        target_index="pgcil_soc",
        spl_approved=True,
        session_role=None,
        needs_spl=True,
    )
    assert out is not None
    assert out["rbac_role"] == "analyst"
    assert out["approved_tools"][-1] == "splunk_run_query"


def test_viewer_shadow_drops_run_query(monkeypatch) -> None:
    monkeypatch.setattr("app.connectors.mcp.mcp_tool_plan_shadow.settings.control_plane_enabled", True)
    monkeypatch.setattr(
        "app.connectors.mcp.mcp_tool_plan_shadow.mcp_tool_plan_llm_advisory_enabled",
        lambda: False,
    )
    out = run_mcp_tool_plan_shadow(
        query="critical alerts",
        target_index="pgcil_soc",
        spl_approved=True,
        session_role="viewer",
        needs_mcp=True,
    )
    assert out is not None
    assert "splunk_run_query" not in out["approved_tools"]
    assert any("rbac_denied" in str(item.get("reason", "")) for item in out["dropped"])
