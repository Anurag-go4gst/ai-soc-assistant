"""Three independently observable MCP readiness states -- confirmed, resolved
this round: discovery state is process-memory only, so an operator must be
able to see MCP_CONFIGURED / MCP_DISCOVERY_VERIFIED / MCP_GLOBAL_EXECUTION_ENABLED
as distinct facts, especially right after a backend restart."""

from __future__ import annotations

import time

import pytest

from app.connectors.mcp.discovery_snapshot import DiscoverySnapshot, get_discovery_snapshot_store
from app.debug.readiness import build_debug_readiness


@pytest.fixture(autouse=True)
def _clear_discovery_store():
    get_discovery_snapshot_store().clear()
    yield
    get_discovery_snapshot_store().clear()


def test_fresh_process_shows_discovery_unverified(monkeypatch) -> None:
    # Simulates a just-restarted backend: MCP_GLOBAL_EXECUTION_ENABLED may
    # already be true from .env, but no handshake has run this process
    # lifetime -- must be visibly distinct from "configured" and
    # "execution enabled".
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_SERVERS", "splunk_soc")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TYPE", "splunk")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TRANSPORT", "streamable_http")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_URL", "https://splunk-mcp.example.invalid/mcp")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_AUTH_MODE", "bearer")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN", "test-token")
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")

    readiness = build_debug_readiness()
    entry = next(s for s in readiness["mcp_discovery"] if s["server_name"] == "splunk_soc")
    assert entry["mcp_configured"] is True
    assert entry["mcp_global_execution_enabled"] is True
    assert entry["mcp_discovery_verified"] is False
    assert entry["mcp_discovery_status"] == "unverified"


def test_after_refresh_discovery_verified_becomes_true(monkeypatch) -> None:
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_SERVERS", "splunk_soc")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TYPE", "splunk")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TRANSPORT", "streamable_http")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_URL", "https://splunk-mcp.example.invalid/mcp")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_AUTH_MODE", "bearer")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN", "test-token")

    get_discovery_snapshot_store().put(
        DiscoverySnapshot(server_name="splunk_soc", captured_at=time.time(), source="operator_refresh", status="ok", tools=())
    )
    readiness = build_debug_readiness()
    entry = next(s for s in readiness["mcp_discovery"] if s["server_name"] == "splunk_soc")
    assert entry["mcp_discovery_verified"] is True
    assert entry["mcp_discovery_status"] == "ok"


def test_simulated_restart_clears_discovery_verified_again(monkeypatch) -> None:
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_SERVERS", "splunk_soc")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TYPE", "splunk")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TRANSPORT", "streamable_http")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_URL", "https://splunk-mcp.example.invalid/mcp")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_AUTH_MODE", "bearer")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN", "test-token")

    store = get_discovery_snapshot_store()
    store.put(DiscoverySnapshot(server_name="splunk_soc", captured_at=time.time(), source="operator_refresh", status="ok", tools=()))
    assert build_debug_readiness()["mcp_discovery"][0]["mcp_discovery_verified"] is True

    store.clear()  # process-memory store reinitializes empty on real restart
    entry = build_debug_readiness()["mcp_discovery"][0]
    assert entry["mcp_discovery_verified"] is False
    assert entry["mcp_discovery_status"] == "unverified"


def test_mock_mode_reports_configured_without_needing_discovery(monkeypatch) -> None:
    monkeypatch.delenv("MCP_MODE", raising=False)
    readiness = build_debug_readiness()
    entry = readiness["mcp_discovery"][0]
    assert entry["server_name"] == "mock"
    assert entry["mcp_configured"] is True
