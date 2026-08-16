"""COE one-switch live MCP activation. No Cisco/Splunk network calls."""

from __future__ import annotations

from pathlib import Path

from app.connectors.mcp import get_mcp_connector
from app.connectors.mcp.discovery import classify_mcp_tool
from app.connectors.mcp.mock import MockMcpConnector
from app.connectors.mcp.registry import load_mcp_registry_status
from app.connectors.mcp.splunk_mcp import SplunkMcpConnector
from app.connectors.mcp.splunk_mcp_readiness import is_disallowed_tool
from app.orchestration.mcp_execution_gate import evaluate_mcp_execution
from app.orchestration.mcp_tool_selector import select_mcp_tool
from app.orchestration.splunk_call_authorization import build_splunk_call_grant

_REPO = Path(__file__).resolve().parents[3]
_COE_PROFILE = _REPO / "env" / "profiles" / "coe.env.example"
_DEV_PROFILE = _REPO / "env" / "profiles" / "development.env.example"
_PREFLIGHT = _REPO / "scripts" / "coe_preflight.sh"
_RUNBOOK = _REPO / "docs" / "coe" / "COE_PRODUCTION_READINESS_RUNBOOK.md"

APPROVED = (
    "search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now "
    "| stats count by user | head 100"
)
VALIDATION = {
    "approved": True,
    "normalized_spl": APPROVED,
    "reject_reasons": [],
    "warnings": [],
    "enforced_limits": {"max_result_limit": 100},
    "policy_version": "spl-policy-v1",
}


def _profile_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def _coe_registry_env(monkeypatch, *, global_execution: bool, url: str = "", token: str = "") -> None:
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true" if global_execution else "false")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "false")
    monkeypatch.setenv("MCP_SERVERS", "splunk_soc")
    monkeypatch.setenv("MCP_DEFAULT_SERVER", "splunk_soc")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TYPE", "splunk")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TRANSPORT", "streamable_http")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_URL", url)
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_AUTH_MODE", "bearer")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN", token)
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_EXECUTION_ENABLED", "true")
    monkeypatch.setenv(
        "MCP_SERVER_SPLUNK_SOC_TOOL_ALLOWLIST",
        "splunk_run_query,splunk_get_info,splunk_get_indexes,splunk_get_index_info,"
        "splunk_get_metadata,splunk_get_user_info,splunk_get_knowledge_objects",
    )
    from app.config import settings

    monkeypatch.setattr(settings, "mcp_mode", "registry")
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", global_execution)
    monkeypatch.setattr(settings, "mcp_server_mock_execution_enabled", False)
    monkeypatch.setattr(settings, "splunk_mcp_enabled", True)
    monkeypatch.setattr(settings, "splunk_mcp_base_url", url)
    monkeypatch.setattr(settings, "splunk_mcp_token", token)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.mcp_mode", "registry")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.splunk_mcp_enabled", True)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.splunk_mcp_base_url", url)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.splunk_mcp_token", token)


class _RaisingConnector:
    def call_tool(self, *args, **kwargs):
        raise AssertionError("MCP call must not happen")


class _FakeTelemetry:
    def __init__(self) -> None:
        self.mcp_events: list[dict] = []

    def record_mcp_execution(self, trace_id: str, **fields) -> None:
        self.mcp_events.append({"trace_id": trace_id, **fields})


def test_coe_profile_is_one_switch_live_ready() -> None:
    values = _profile_values(_COE_PROFILE)
    assert values["AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED"] == "true"
    assert values["AI_SOC_PIPELINE_DISPATCH_V2_ENABLED"] == "false"
    assert values["AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED"] == "true"
    assert values["AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED"] == "false"
    assert values["LANGGRAPH_ORCHESTRATION_ENABLED"] == "true"
    assert values["MCP_MODE"] == "registry"
    assert values["MCP_GLOBAL_EXECUTION_ENABLED"] == "false"
    assert values["MCP_SERVER_SPLUNK_SOC_EXECUTION_ENABLED"] == "true"
    assert values["MCP_SERVER_MOCK_EXECUTION_ENABLED"] == "false"
    assert values.get("SPLUNK_MCP_BASE_URL", "") == ""
    assert values.get("SPLUNK_MCP_TOKEN", "") == ""
    assert values.get("MCP_SERVER_SPLUNK_SOC_URL", "") == ""
    assert values.get("MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN", "") == ""
    assert "AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS" not in values


def test_development_profile_unchanged() -> None:
    values = _profile_values(_DEV_PROFILE)
    assert values.get("MCP_MODE") == "mock"
    assert values.get("MCP_GLOBAL_EXECUTION_ENABLED") == "true"
    assert values.get("MCP_SERVER_MOCK_EXECUTION_ENABLED") == "true"
    assert values.get("AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS") == "120"
    assert "MCP_SERVER_SPLUNK_SOC_EXECUTION_ENABLED" not in values


def test_registry_global_false_blocks_execution_even_when_per_server_prearmed(monkeypatch) -> None:
    _coe_registry_env(monkeypatch, global_execution=False, url="https://splunk-mcp.example.invalid/mcp", token="test-token")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: _RaisingConnector())

    status = load_mcp_registry_status()
    assert status.mode == "registry"
    assert status.global_execution_enabled is False
    assert status.servers[0].execution_enabled is False

    execution, review = evaluate_mcp_execution(
        trace_id="switch-global-off",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=VALIDATION,
    )
    assert execution["executed_spl"] is None
    assert execution["block_reason"] == "mcp_global_execution_disabled"
    assert review["required"] is True


def test_registry_never_selects_mock_connector(monkeypatch) -> None:
    monkeypatch.setattr("app.connectors.mcp.settings.mcp_mode", "registry")
    connector = get_mcp_connector()
    assert isinstance(connector, SplunkMcpConnector)
    assert not isinstance(connector, MockMcpConnector)
    assert connector.health().fallback is None


def test_global_true_missing_registry_configuration_fails_closed(monkeypatch) -> None:
    _coe_registry_env(monkeypatch, global_execution=True, url="", token="")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: _RaisingConnector())

    execution, review = evaluate_mcp_execution(
        trace_id="switch-missing-config",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=VALIDATION,
    )
    assert execution["executed_spl"] is None
    assert execution["block_reason"] in {
        "splunk_mcp_not_configured",
        "mcp_server_unavailable",
        "missing_endpoint_configuration",
        "missing_auth_configuration",
    }
    assert review["required"] is True


def test_global_true_still_requires_auth0_confirmation(monkeypatch) -> None:
    _coe_registry_env(
        monkeypatch,
        global_execution=True,
        url="https://splunk-mcp.example.invalid/mcp",
        token="test-token",
    )
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.ai_soc_require_spl_execution_confirmation", False)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: _RaisingConnector())

    execution, review = evaluate_mcp_execution(
        trace_id="switch-auth0",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=VALIDATION,
        rbac_role="analyst",
    )
    assert execution["executed_spl"] is None
    assert review["review_type"] == "spl_execution_confirmation"
    assert review["reason"] == "analyst_confirmation_required"
    grant = (execution.get("pending_execution_confirmation") or {}).get("call_grant") or {}
    assert grant.get("llm_granted") is False


def test_write_and_remediation_tools_blocked_with_global_true(monkeypatch) -> None:
    _coe_registry_env(
        monkeypatch,
        global_execution=True,
        url="https://splunk-mcp.example.invalid/mcp",
        token="test-token",
    )
    selection = select_mcp_tool(
        trace_id="switch-write",
        selected_skill="attack_discovery",
        workflow_plan={},
        execution_intent="spl_search",
        spl_validation=VALIDATION,
        user_requested_mcp_tool="phase10_remediate_host",
        rbac_role="soc_lead",
    )
    assert selection["tool_selection_status"] == "requires_human_review"
    assert is_disallowed_tool("phase10_remediate_host")
    assert is_disallowed_tool("contain_endpoint")
    assert classify_mcp_tool("splunk.admin", server_type="splunk").blocked is True
    blocked = SplunkMcpConnector().call_tool("phase10_remediate_host", {})
    assert blocked["status"] == "blocked"


def test_llm_cannot_authorize_execution(monkeypatch) -> None:
    grant = build_splunk_call_grant(
        trace_id="switch-llm",
        normalized_spl=APPROVED,
        selected_mcp_server="splunk_soc",
        selected_mcp_tool="splunk_run_query",
        identity="analyst",
        rbac_role="analyst",
        mcp_endpoint="https://splunk-mcp.example.invalid/mcp",
        max_result_limit=100,
    )
    assert grant["llm_granted"] is False
    _coe_registry_env(
        monkeypatch,
        global_execution=True,
        url="https://splunk-mcp.example.invalid/mcp",
        token="test-token",
    )
    selection = select_mcp_tool(
        trace_id="switch-llm-tool",
        selected_skill="attack_discovery",
        workflow_plan={},
        execution_intent="spl_search",
        spl_validation=VALIDATION,
        llm_tool_recommendation={"tool_name": "phase10_remediate_host", "tool_category": "spl_search"},
        user_requested_mcp_tool="phase10_remediate_host",
    )
    assert selection["tool_selection_status"] == "requires_human_review"


def test_preflight_and_runbook_describe_one_switch() -> None:
    preflight = _PREFLIGHT.read_text(encoding="utf-8")
    runbook = _RUNBOOK.read_text(encoding="utf-8")
    for text in (preflight, runbook):
        assert "LIVE_MCP_CONFIGURED" in text
        assert "MCP_GLOBAL_EXECUTION_ENABLED" in text
        assert "LIVE_MCP_EXECUTION" in text
        assert "AUTH0" in text
    assert "MCP_GLOBAL_EXECUTION_ENABLED=true" in runbook
    assert "PRODUCTION_GO_RECOMMENDATION = NO_GO" in runbook
