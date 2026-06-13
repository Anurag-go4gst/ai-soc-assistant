from __future__ import annotations

from app.config import settings
from app.connectors.mcp.mock import MockMcpConnector


def test_mock_discovery_blocked_without_flag(monkeypatch) -> None:
    monkeypatch.setattr(settings, "mcp_discovery_enabled", False)
    connector = MockMcpConnector()
    result = connector.call_tool("splunk_get_indexes", {})
    assert result["status"] == "blocked"
    assert result["error"] == "mcp_discovery_disabled"


def test_mock_discovery_allowed_with_explicit_governance(monkeypatch) -> None:
    monkeypatch.setattr(settings, "mcp_discovery_enabled", False)
    connector = MockMcpConnector()
    result = connector.call_tool("splunk_get_indexes", {"_governance": {"discovery_allowed": True}})
    assert result["status"] == "ok"


def test_mock_search_blocked_without_execution_flags(monkeypatch) -> None:
    monkeypatch.setattr(settings, "mcp_discovery_enabled", True)
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", False)
    monkeypatch.setattr(settings, "mcp_server_mock_execution_enabled", False)
    connector = MockMcpConnector()
    result = connector.call_tool(
        "splunk_run_query",
        {
            "search_query": "search index=pgcil_soc sourcetype=pgcil:auth earliest=-1h latest=now | stats count | head 10",
        },
    )
    assert result["status"] == "blocked"
    assert result["error"] == "mcp_execution_disabled"
