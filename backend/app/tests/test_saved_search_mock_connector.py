from __future__ import annotations

from typing import Any

import pytest

from app.config import settings
from app.connectors.mcp.connection_store import apply_to_settings, save_connection
from app.connectors.mcp.mock import MockMcpConnector
from app.coverage.catalogue_execution_map import CatalogueExecutionBinding, CatalogueExecutionMap
from app.orchestration.mcp_execution_gate import evaluate_mcp_execution
from app.orchestration.saved_search_allowlist import saved_search_name_allowed


APPROVED_SAVED_SEARCH = {"saved_search_name": "SOC - Failed login spike"}


def test_mock_saved_search_when_allowed(monkeypatch) -> None:
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", True)
    monkeypatch.setattr(settings, "mcp_server_mock_execution_enabled", True)
    monkeypatch.setattr(settings, "splunk_allow_run_saved_search", True)
    monkeypatch.setattr(settings, "splunk_allowed_saved_searches", "SOC - Failed login spike")
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


def test_saved_search_not_allowlisted_blocks_before_connector(monkeypatch) -> None:
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(settings, "splunk_allow_run_saved_search", True)
    monkeypatch.setattr(settings, "splunk_allowed_saved_searches", "")
    monkeypatch.setattr(
        "app.orchestration.saved_search_allowlist.load_catalogue_execution_map",
        lambda **_: CatalogueExecutionMap(map_version="test", entries=[]),
    )
    monkeypatch.setattr(
        "app.orchestration.mcp_execution_gate.get_mcp_connector",
        lambda: _RaisingConnector(),
    )
    monkeypatch.setattr(
        "app.orchestration.mcp_execution_gate.get_telemetry_connector",
        lambda: _FakeTelemetry(),
    )

    execution, review = evaluate_mcp_execution(
        trace_id="trace-saved-deny",
        selected_skill="spl_generation",
        workflow_plan={},
        spl_validation=APPROVED_SAVED_SEARCH,
        execution_intent="saved_search_execution",
        requested_mcp_tool="splunk_run_saved_search",
    )

    assert execution["status"] == "requires_human_review"
    assert review["reason"] == "saved_search_not_allowlisted"
    assert review["review_type"] == "saved_search_allowlist"


def test_allowlisted_saved_search_proceeds_after_confirm(monkeypatch) -> None:
    connector = _CapturingConnector()
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(settings, "splunk_allow_run_saved_search", True)
    monkeypatch.setattr(settings, "splunk_allowed_saved_searches", "SOC - Failed login spike")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: connector)
    monkeypatch.setattr("app.orchestration.mcp_tool_selector.settings.splunk_allow_run_saved_search", True)
    monkeypatch.setattr("app.connectors.mcp.mock.settings.splunk_allow_run_saved_search", True)
    monkeypatch.setattr(
        "app.orchestration.mcp_execution_gate.get_telemetry_connector",
        lambda: _FakeTelemetry(),
    )

    execution, review = evaluate_mcp_execution(
        trace_id="trace-saved-allow",
        selected_skill="spl_generation",
        workflow_plan={},
        spl_validation=APPROVED_SAVED_SEARCH,
        execution_intent="saved_search_execution",
        requested_mcp_tool="splunk_run_saved_search",
        execution_review_action="confirm",
        pending_execution={"saved_search_name": "SOC - Failed login spike", "saved_search_app": "search"},
    )

    assert execution["status"] == "executed"
    assert connector.called is True
    assert review["required"] is False


def test_empty_env_and_catalogue_deny_unlisted_name(monkeypatch) -> None:
    monkeypatch.setattr(settings, "splunk_allowed_saved_searches", "")
    monkeypatch.setattr(
        "app.orchestration.saved_search_allowlist.load_catalogue_execution_map",
        lambda **_: CatalogueExecutionMap(map_version="test", entries=[]),
    )
    assert saved_search_name_allowed("SOC - Failed login spike") is False


def test_catalogue_bound_name_allowed_with_empty_env(monkeypatch) -> None:
    monkeypatch.setattr(settings, "splunk_allowed_saved_searches", "")
    monkeypatch.setattr(
        "app.orchestration.saved_search_allowlist.load_catalogue_execution_map",
        lambda **_: CatalogueExecutionMap(
            map_version="test",
            entries=[
                CatalogueExecutionBinding(
                    question_ref="q.test",
                    execution_mode="saved_search",
                    saved_search_name="COE - Brute force watch",
                    coe_verified=True,
                )
            ],
        ),
    )
    assert saved_search_name_allowed("COE - Brute force watch") is True


def test_connection_store_round_trips_allowed_saved_searches(
    monkeypatch, tmp_path, isolated_connection_store_apply
) -> None:
    store_path = tmp_path / "connections.json"
    monkeypatch.setattr("app.connectors.mcp.connection_store._store_path", lambda: store_path)
    monkeypatch.setattr(settings, "splunk_allowed_saved_searches", "")

    save_connection(
        enabled=True,
        deployment_mode="coe",
        discovery_policy="dynamic",
        transport="streamable_http",
        auth_method="bearer",
        url="https://splunk.example.invalid/mcp",
        bearer_token="token",
        timeout_seconds=10,
        saia_tools_enabled=False,
        splunk_ai_assistant_mode="auto",
        allow_saved_search=True,
        allowed_saved_searches="SOC - Failed login spike,COE - Brute force watch",
        execution_enabled=False,
        updated_by="tester",
    )
    apply_to_settings()

    assert settings.splunk_allowed_saved_searches == "SOC - Failed login spike,COE - Brute force watch"
    assert saved_search_name_allowed("SOC - Failed login spike") is True


class _FakeTelemetry:
    def record_mcp_execution(self, trace_id: str, **fields: Any) -> None:
        return None


class _RaisingConnector:
    def call_tool(self, tool_name: str, arguments: dict[str, Any], server_name: str | None = None) -> dict[str, Any]:
        raise AssertionError("MCP call must not happen")


class _CapturingConnector:
    def __init__(self) -> None:
        self.called = False

    def call_tool(self, tool_name: str, arguments: dict[str, Any], server_name: str | None = None) -> dict[str, Any]:
        self.called = True
        return {"status": "ok", "row_count": 1, "rows": [{"user": "svc_app"}]}
