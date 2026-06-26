from __future__ import annotations

import pytest

from app.config import settings
from app.spl.mcp_loop_discovery import execute_loop_discovery_hop


def test_discovery_hop_planned_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "mcp_discovery_enabled", False)
    hop = execute_loop_discovery_hop("splunk_get_indexes", rbac_role="analyst")
    assert hop["outcome"] == "planned"
    assert "accessible_indexes" in hop["delivered"]


def test_discovery_hop_planned_when_global_execution_off(monkeypatch: pytest.MonkeyPatch) -> None:
    # Discovery flag on but the global MCP gate closed → planned-only (never a
    # live/registry call).
    monkeypatch.setattr(settings, "mcp_discovery_enabled", True)
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", False)
    hop = execute_loop_discovery_hop("splunk_get_indexes", rbac_role="analyst")
    assert hop["outcome"] == "planned"
    assert hop["payload"]["reason"] == "mcp_global_execution_disabled"


def test_discovery_hop_collected_with_mock_connector(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "mcp_discovery_enabled", True)
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", True)
    hop = execute_loop_discovery_hop("splunk_get_indexes", rbac_role="analyst", trace_id="trace-1")
    assert hop["outcome"] == "collected"
    assert hop["payload"]["preview_rows"]
