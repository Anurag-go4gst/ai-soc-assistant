from __future__ import annotations

import time
from unittest.mock import MagicMock

from app.config import settings
from app.connectors.mcp.discovery_snapshot import DiscoveredToolRecord, DiscoverySnapshot, get_discovery_snapshot_store
from app.connectors.mcp.registry import McpRegistryStatus, McpServerStatus
from app.orchestration.mcp_execution_gate import evaluate_mcp_execution

APPROVED = {
    "approved": True,
    "normalized_spl": "search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | stats count by user | head 100",
    "reject_reasons": [],
    "warnings": [],
    "enforced_limits": {"max_result_limit": 100},
    "policy_version": "spl-policy-v1",
}


def _registry(mode: str = "registry") -> McpRegistryStatus:
    return McpRegistryStatus(
        mode=mode,
        default_server="splunk_soc",
        global_execution_enabled=True,
        servers=[
            McpServerStatus(
                name="splunk_soc",
                type="splunk",
                enabled=True,
                implemented=True,
                configured=True,
                available=True,
                transport="streamable_http" if mode == "registry" else "mock",
                url_configured=True,
                command_configured=False,
                auth_mode="bearer",
                auth_configured=True,
                execution_enabled=True,
                discovered_tools_count=1,
                discovered_tools_safe_names=["splunk_run_query"],
                discovered_tools=[{
                    "name": "splunk_run_query",
                    "description": "",
                    "capability": "spl_search",
                    "categories": ["execution"],
                    "blocked": False,
                    "blocked_reason": None,
                }],
                blocked_tools_count=0,
                blocked_tools_safe_names=[],
                search_execution_allowed=True,
            )
        ],
    )


def test_registry_catalogue_auto_execute_skips_confirmation(monkeypatch) -> None:
    monkeypatch.setenv("AI_SOC_CATALOGUE_AUTO_EXECUTE_ENABLED", "true")
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("SPLUNK_MCP_ENABLED", "true")
    monkeypatch.setenv("SPLUNK_MCP_BASE_URL", "https://splunk-mcp.example.invalid/mcp")
    monkeypatch.setenv("SPLUNK_MCP_TOKEN", "test-token")
    settings.ai_soc_catalogue_auto_execute_enabled = True
    monkeypatch.setattr(settings, "splunk_mcp_enabled", True)
    monkeypatch.setattr(settings, "splunk_mcp_base_url", "https://splunk-mcp.example.invalid/mcp")
    monkeypatch.setattr(settings, "splunk_mcp_token", "test-token")
    monkeypatch.setattr(settings, "ai_soc_require_spl_execution_confirmation", True)

    fake_result = {"status": "ok", "rows": [{"count": 1}]}
    connector = MagicMock()
    connector.call_tool.return_value = fake_result
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: connector)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.load_mcp_registry_status", lambda: _registry("registry"))
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: MagicMock())
    get_discovery_snapshot_store().put(
        DiscoverySnapshot(
            server_name="splunk_soc",
            captured_at=time.time(),
            source="operator_refresh",
            status="ok",
            tools=(
                DiscoveredToolRecord(
                    name="splunk_run_query",
                    input_schema={"properties": {"search_query": {"type": "string"}}, "required": ["search_query"]},
                ),
            ),
        )
    )

    execution, review = evaluate_mcp_execution(
        trace_id="trace-catalogue",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=APPROVED,
        catalogue_match_path="exact_105_question",
        catalogue_question_ref="q0.q046",
        catalogue_use_case_id="auth_failed_login_spike",
    )

    assert review["required"] is False
    assert execution.get("status") == "executed"
    assert execution.get("auto_execute_reason") == "catalogue_known_template_binding"
