"""Regression tests for pytest suite order pollution (#109).

connection_store.apply_to_settings() writes MCP_* env vars and settings singleton
fields directly. Tests that trigger it must restore that state or later tests see
stale MCP_GLOBAL_EXECUTION_ENABLED and fail mock-mode assertions.
"""

from __future__ import annotations

import os

from app.config import settings
from app.connectors.mcp.connection_store import save_connection
from app.connectors.mcp.registry import load_mcp_registry_status


def _assert_default_mock_mcp_posture() -> None:
    status = load_mcp_registry_status()
    assert status.mode == "mock"
    assert status.global_execution_enabled is False
    assert settings.mcp_global_execution_enabled is False
    assert os.environ.get("MCP_GLOBAL_EXECUTION_ENABLED", "false").lower() != "true"


def test_connection_store_apply_sets_execution_enabled_during_test(
    monkeypatch,
    tmp_path,
    isolated_connection_store_apply,
) -> None:
    """Minimal polluting setup from #109; fixture teardown must follow this test."""
    store_path = tmp_path / "mcp_connection.json"
    monkeypatch.setattr(settings, "ai_soc_mcp_connection_store_path", str(store_path))
    for key in list(os.environ):
        if key == "MCP_MODE" or key.startswith("MCP_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(settings, "mcp_mode", "mock")
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", False)

    save_connection(
        enabled=True,
        deployment_mode="coe",
        discovery_policy="dynamic",
        transport="streamable_http",
        auth_method="bearer",
        url="https://splunk-mcp.example.invalid/mcp",
        bearer_token="pollution-token",
        timeout_seconds=10,
        saia_tools_enabled=False,
        splunk_ai_assistant_mode="auto",
        allow_saved_search=False,
        execution_enabled=True,
        updated_by="pytest-isolation-regression",
    )

    assert settings.mcp_global_execution_enabled is True
    assert os.environ.get("MCP_GLOBAL_EXECUTION_ENABLED") == "true"


def test_connection_store_apply_restores_default_mock_posture_after_teardown() -> None:
    """Runs after isolated_connection_store_apply teardown from the test above."""
    _assert_default_mock_mcp_posture()
