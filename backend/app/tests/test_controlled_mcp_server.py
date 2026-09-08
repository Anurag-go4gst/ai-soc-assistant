"""External controlled MCP server uses the live Splunk transport contract."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

from app.connectors.mcp.discovery_snapshot import build_snapshot_from_handshake, get_discovery_snapshot_store
from app.connectors.mcp.splunk_mcp import SplunkMcpConnector
from app.config import settings

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from tools.controlled_mcp_server.server import PROCESS_ROWS, ControlledMcpServer  # noqa: E402


@pytest.fixture()
def controlled_mcp():
    server = ControlledMcpServer(mode="full")
    server.start()
    yield server
    server.stop()


def _arm_live(monkeypatch: pytest.MonkeyPatch, server: ControlledMcpServer) -> None:
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "false")
    monkeypatch.setenv("MCP_SERVERS", "splunk_soc")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TYPE", "splunk")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_URL", server.base_url)
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN", server.token)
    monkeypatch.setattr(settings, "mcp_mode", "registry")
    monkeypatch.setattr(settings, "splunk_mcp_enabled", True)
    monkeypatch.setattr(settings, "splunk_mcp_base_url", server.base_url)
    monkeypatch.setattr(settings, "splunk_mcp_token", server.token)
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", True)


def test_handshake_lists_search_tool(monkeypatch: pytest.MonkeyPatch, controlled_mcp: ControlledMcpServer) -> None:
    _arm_live(monkeypatch, controlled_mcp)
    handshake = SplunkMcpConnector().handshake_initialize_and_list_tools()
    assert handshake.get("status") == "ok"
    assert "splunk_run_query" in (handshake.get("tools") or [])
    snapshot = build_snapshot_from_handshake(
        server_name="splunk_soc",
        handshake_result=handshake,
        source="operator_refresh",
    )
    assert snapshot.status == "ok"
    assert snapshot.tool_by_name("splunk_run_query") is not None
    get_discovery_snapshot_store().put(snapshot)


def test_first_search_is_process_only_second_adds_correlation(
    monkeypatch: pytest.MonkeyPatch, controlled_mcp: ControlledMcpServer
) -> None:
    _arm_live(monkeypatch, controlled_mcp)
    connector = SplunkMcpConnector()
    first = connector.call_tool("splunk_run_query", {"search_query": "search index=pgcil_soc sourcetype=pgcil:edr | head 100"})
    rows1 = first.get("rows") or []
    assert rows1
    assert rows1[0]["process"] == "powershell.exe"
    assert all("dest" not in row for row in rows1)
    second = connector.call_tool("splunk_run_query", {"search_query": "search index=pgcil_soc sourcetype=pgcil:sysmon | head 100"})
    rows2 = second.get("rows") or []
    families = {row.get("action") or row.get("dest") or row.get("process") for row in rows2}
    assert any(row.get("action") == "scheduled_task_created" for row in rows2)
    assert any(row.get("dest") == "198.51.100.88" for row in rows2)
    assert controlled_mcp.search_calls == 2
    assert "mock" not in first
    assert PROCESS_ROWS[0]["host"] == "WS-14"


def test_insufficient_mode_never_supplies_correlation(monkeypatch: pytest.MonkeyPatch) -> None:
    server = ControlledMcpServer(mode="insufficient")
    server.start()
    try:
        _arm_live(monkeypatch, server)
        connector = SplunkMcpConnector()
        first = connector.call_tool("splunk_run_query", {"search_query": "search index=pgcil_soc | head 10"})
        second = connector.call_tool("splunk_run_query", {"search_query": "search index=pgcil_soc | head 10"})
        assert all("dest" not in row for row in (first.get("rows") or []))
        assert all("dest" not in row for row in (second.get("rows") or []))
        assert all(row.get("action") != "scheduled_task_created" for row in (second.get("rows") or []))
    finally:
        server.stop()
