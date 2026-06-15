from __future__ import annotations

from app.connectors.mcp.mcp_rbac import (
    effective_allowed_tools,
    is_tool_allowed_for_role,
    resolve_mcp_rbac_role,
    session_role_for_mcp_gate,
)


def test_resolve_session_role_demo_analyst() -> None:
    assert resolve_mcp_rbac_role("demo_analyst") == "analyst"


def test_viewer_cannot_run_query() -> None:
    assert "splunk_run_query" not in effective_allowed_tools("viewer")
    assert not is_tool_allowed_for_role("splunk_run_query", "viewer")


def test_analyst_can_run_query() -> None:
    assert is_tool_allowed_for_role("splunk_run_query", "analyst")


def test_never_allowed_blocks_saia_even_for_soc_lead() -> None:
    assert not is_tool_allowed_for_role("saia_generate_spl", "soc_lead")


def test_soc_lead_inherits_viewer_tools() -> None:
    viewer_tools = effective_allowed_tools("viewer")
    lead_tools = effective_allowed_tools("soc_lead")
    assert viewer_tools.issubset(lead_tools)


def test_none_role_fails_closed_to_viewer() -> None:
    assert resolve_mcp_rbac_role(None) == "viewer"
    assert not is_tool_allowed_for_role("splunk_run_query", None)


def test_run_query_alias_normalizes_for_rbac() -> None:
    assert is_tool_allowed_for_role("run_splunk_query", "analyst")
    assert not is_tool_allowed_for_role("run_splunk_query", "viewer")


def test_unscoped_gate_defaults_to_demo_analyst() -> None:
    assert session_role_for_mcp_gate(None) == "demo_analyst"
    assert is_tool_allowed_for_role("splunk_run_query", session_role_for_mcp_gate(None))
