from __future__ import annotations

from app.config import settings
from app.connectors.mcp.mock import MockMcpConnector


def test_mock_saved_search_when_allowed(monkeypatch) -> None:
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", True)
    monkeypatch.setattr(settings, "mcp_server_mock_execution_enabled", True)
    monkeypatch.setattr(settings, "splunk_allow_run_saved_search", True)
    result = MockMcpConnector().call_tool(
        "splunk_run_saved_search",
        {"saved_search_name": "SOC - Failed login spike"},
    )
    assert result["status"] == "ok"
    assert result["rows"]


def test_mock_saved_search_blocked_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "splunk_allow_run_saved_search", False)
    result = MockMcpConnector().call_tool(
        "splunk_run_saved_search",
        {"saved_search_name": "SOC - Failed login spike"},
    )
    assert result["status"] == "blocked"
