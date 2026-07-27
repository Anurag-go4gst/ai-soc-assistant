from __future__ import annotations

from app.connectors.mcp.mcp_tool_plan_shadow import run_mcp_tool_plan_shadow


def test_shadow_skips_when_no_mcp_or_spl_interest(monkeypatch) -> None:
    assert run_mcp_tool_plan_shadow(query="hello", needs_mcp=False, needs_spl=False) is None


def test_shadow_returns_deterministic_plan_when_control_plane_on(monkeypatch) -> None:
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


def test_shadow_can_disable_llm_advisory_per_turn(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.connectors.mcp.mcp_tool_plan_shadow.mcp_tool_plan_llm_advisory_enabled",
        lambda: True,
    )

    def _fail_planner(*args, **kwargs):
        raise AssertionError("planner LLM should be disabled for this turn")

    monkeypatch.setattr("app.connectors.mcp.mcp_tool_plan_shadow.plan_tool_chronology", _fail_planner)

    out = run_mcp_tool_plan_shadow(
        query="List all DNS requests during the observation window",
        target_index=None,
        spl_approved=False,
        session_role="analyst",
        needs_spl=True,
        allow_llm_advisory=False,
    )
    assert out is not None
    assert out["planner"]["llm_called"] is False
    assert out["planner"]["skipped_reason"] == "llm_advisory_disabled_for_turn"


def test_experience_center_fixture_never_calls_planner_llm(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.connectors.mcp.mcp_tool_plan_shadow.mcp_tool_plan_llm_advisory_enabled",
        lambda: True,
    )

    def _fail_planner(*args, **kwargs):
        raise AssertionError("Experience Center fixture must not invoke planner LLM")

    monkeypatch.setattr("app.connectors.mcp.mcp_tool_plan_shadow.plan_tool_chronology", _fail_planner)

    out = run_mcp_tool_plan_shadow(
        query="Investigate failed login spike on APP-01",
        target_index="pgcil_soc",
        spl_approved=True,
        session_role="demo_analyst",
        needs_mcp=True,
        experience_center_fixture=True,
    )
    assert out is not None
    assert out["planner"]["llm_called"] is False
    assert out["planner"]["skipped_reason"] == "experience_center_fixture"


def test_shadow_surfaces_turn_budget_skip_reason(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.connectors.mcp.mcp_tool_plan_shadow.mcp_tool_plan_llm_advisory_enabled",
        lambda: True,
    )
    out = run_mcp_tool_plan_shadow(
        query="List DNS requests",
        needs_spl=True,
        allow_llm_advisory=False,
        llm_advisory_skip_reason="turn_budget_exhausted",
    )
    assert out is not None
    assert out["planner"]["llm_called"] is False
    assert out["planner"]["skipped_reason"] == "turn_budget_exhausted"
