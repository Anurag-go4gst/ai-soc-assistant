from __future__ import annotations

from typing import Any

from app.connectors.mcp.registry import McpRegistryStatus, McpServerStatus
from app.orchestration.mcp_execution_gate import evaluate_mcp_execution
from app.orchestration.mcp_execution_gate import _gate_review
from app.orchestration.mcp_tool_selector import select_mcp_tool


APPROVED_VALIDATION = {
    "approved": True,
    "normalized_spl": "search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | stats count by user | head 100",
    "reject_reasons": [],
    "warnings": [],
    "enforced_limits": {"max_result_limit": 100},
    "policy_version": "spl-policy-v1",
}

FAILED_VALIDATION = {
    "approved": False,
    "normalized_spl": None,
    "reject_reasons": ["missing_result_limit"],
    "warnings": [],
    "enforced_limits": {"max_result_limit": 100},
    "policy_version": "spl-policy-v1",
}


def test_validation_failure_creates_human_review(monkeypatch) -> None:
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: FakeTelemetry())

    execution, review = evaluate_mcp_execution(
        trace_id="trace-failed",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=FAILED_VALIDATION,
    )

    assert execution["executed_spl"] is None
    assert execution["results_preview"] == []
    assert execution["status"] == "requires_human_review"
    assert review["required"] is True
    assert review["review_type"] == "spl_revision"
    assert review["reason"] == "spl_validation_failed"


def test_global_execution_disabled_blocks_before_mcp_call(monkeypatch) -> None:
    telemetry = FakeTelemetry()
    monkeypatch.delenv("MCP_GLOBAL_EXECUTION_ENABLED", raising=False)
    monkeypatch.delenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", raising=False)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: telemetry)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: RaisingConnector())

    execution, review = evaluate_mcp_execution(
        trace_id="trace-disabled",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=APPROVED_VALIDATION,
    )

    assert execution["executed_spl"] is None
    assert execution["block_reason"] == "mcp_global_execution_disabled"
    assert review["review_type"] == "execution_approval"
    assert telemetry.mcp_events[-1]["event_type"] == "mcp_execution_requires_human_review"


def test_per_server_execution_disabled_blocks(monkeypatch) -> None:
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.delenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", raising=False)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: FakeTelemetry())

    execution, review = evaluate_mcp_execution(
        trace_id="trace-server-disabled",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=APPROVED_VALIDATION,
    )

    assert execution["executed_spl"] is None
    assert execution["block_reason"] == "mcp_server_execution_disabled"
    assert review["reason"] == "mcp_server_execution_disabled"


def test_mock_execution_uses_only_normalized_spl(monkeypatch) -> None:
    telemetry = FakeTelemetry()
    connector = CapturingConnector()
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")
    # Demo/lab mode so mock success runs without the HIL gate; this test asserts
    # the execution mechanics, not the HIL contract (covered separately).
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.ai_soc_demo_or_lab_execution_mode", True)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.ai_soc_allow_mock_execution_without_hil_in_demo", True)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: telemetry)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: connector)

    execution, review = evaluate_mcp_execution(
        trace_id="trace-exec",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation={**APPROVED_VALIDATION, "candidate_spl": "search index=* | delete"},
    )

    assert connector.arguments == {"query": APPROVED_VALIDATION["normalized_spl"]}
    assert execution["status"] == "executed"
    assert execution["executed_spl"] == APPROVED_VALIDATION["normalized_spl"]
    assert execution["result_count"] == 1
    assert len(execution["results_preview"]) == 1
    assert execution["evidence_source"] == "mock"
    assert execution["execution_status_label"] == "mock_executed"
    assert review["required"] is False


def test_result_preview_is_capped(monkeypatch) -> None:
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: FakeTelemetry())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: ManyRowsConnector())

    execution, _review = evaluate_mcp_execution(
        trace_id="trace-capped",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=APPROVED_VALIDATION,
    )

    assert execution["status"] == "executed"
    assert execution["result_count"] == 5
    assert len(execution["results_preview"]) == 5


def test_requested_safe_tool_can_be_selected(monkeypatch) -> None:
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")

    selection = select_mcp_tool(
        trace_id="trace-select",
        selected_skill="attack_discovery",
        workflow_plan={},
        execution_intent="spl_search",
        spl_validation=APPROVED_VALIDATION,
        user_requested_mcp_tool="run_splunk_query",
    )

    assert selection["tool_selection_status"] == "selected"
    assert selection["selected_mcp_tool"] == "splunk_run_query"


def test_requested_canonical_tool_matches_legacy_discovery_alias(monkeypatch) -> None:
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_SERVERS", "splunk_soc")
    monkeypatch.setenv("MCP_DEFAULT_SERVER", "splunk_soc")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TYPE", "splunk")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_URL", "https://splunk-mcp.example.invalid/mcp")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_AUTH_MODE", "none")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TOOL_ALLOWLIST", "run_splunk_query")

    selection = select_mcp_tool(
        trace_id="trace-canonical-select",
        selected_skill="attack_discovery",
        workflow_plan={},
        execution_intent="spl_search",
        spl_validation=APPROVED_VALIDATION,
        user_requested_mcp_tool="splunk_run_query",
    )

    assert selection["tool_selection_status"] == "selected"
    assert selection["selected_mcp_tool"] == "run_splunk_query"


def test_requested_unsafe_tool_creates_human_review(monkeypatch) -> None:
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")

    selection = select_mcp_tool(
        trace_id="trace-blocked-tool",
        selected_skill="attack_discovery",
        workflow_plan={},
        execution_intent="spl_search",
        spl_validation=APPROVED_VALIDATION,
        user_requested_mcp_tool="saia_generate_spl",
    )

    assert selection["tool_selection_status"] == "requires_human_review"
    assert selection["human_review"]["review_type"] == "tool_selection_review"
    assert selection["blocked_reason"] == "requested_tool_intent_mismatch"


def test_no_discovered_tools_creates_human_review(monkeypatch) -> None:
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_SERVERS", "splunk_soc")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TYPE", "splunk")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_URL", "https://splunk-mcp.example.invalid/mcp")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_AUTH_MODE", "none")
    monkeypatch.delenv("MCP_SERVER_SPLUNK_SOC_TOOL_ALLOWLIST", raising=False)

    selection = select_mcp_tool(
        trace_id="trace-no-tools",
        selected_skill="attack_discovery",
        workflow_plan={},
        execution_intent="spl_search",
        spl_validation=APPROVED_VALIDATION,
    )

    assert selection["tool_selection_status"] == "requires_human_review"
    assert selection["blocked_reason"] == "no_discovered_tools"


def test_llm_recommendation_cannot_override_policy(monkeypatch) -> None:
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")

    selection = select_mcp_tool(
        trace_id="trace-llm-advisory",
        selected_skill="attack_discovery",
        workflow_plan={},
        execution_intent="spl_search",
        spl_validation=APPROVED_VALIDATION,
        user_requested_mcp_tool="saia_generate_spl",
        llm_tool_recommendation={"tool_name": "saia_generate_spl", "tool_category": "spl_search"},
    )

    assert selection["tool_selection_status"] == "requires_human_review"
    assert selection["blocked_reason"] == "requested_tool_intent_mismatch"


def test_real_adapter_unavailable_returns_human_review(monkeypatch) -> None:
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVERS", "splunk_soc")
    monkeypatch.setenv("MCP_DEFAULT_SERVER", "splunk_soc")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TYPE", "splunk")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_URL", "https://splunk-mcp.example.invalid/mcp")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_AUTH_MODE", "none")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TOOL_ALLOWLIST", "run_splunk_query")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: FakeTelemetry())

    execution, review = evaluate_mcp_execution(
        trace_id="trace-real",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=APPROVED_VALIDATION,
    )

    assert execution["executed_spl"] is None
    assert execution["block_reason"] == "real_mcp_adapter_not_implemented"
    assert review["review_type"] == "admin_action_required"


def test_saved_search_is_blocked_at_execution_gate() -> None:
    registry = McpRegistryStatus(
        mode="mock",
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
                transport="mock",
                url_configured=False,
                command_configured=False,
                auth_mode="none",
                auth_configured=True,
                execution_enabled=True,
                discovered_tools_count=1,
                discovered_tools_safe_names=["splunk_run_saved_search"],
                discovered_tools=[
                    {
                        "name": "splunk_run_saved_search",
                        "description": "",
                        "capability": "spl_search",
                        "categories": ["saved_search_execution", "execution"],
                        "blocked": False,
                        "blocked_reason": None,
                    }
                ],
                blocked_tools_count=0,
                blocked_tools_safe_names=[],
                search_execution_allowed=False,
            )
        ],
    )

    review = _gate_review(
        selected_skill="attack_discovery",
        spl_validation=APPROVED_VALIDATION,
        selected_mcp_server="splunk_soc",
        selected_mcp_tool="splunk_run_saved_search",
        registry=registry,
    )

    assert review["required"] is True
    assert review["reason"] == "saved_search_execution_disabled"


class FakeTelemetry:
    def __init__(self) -> None:
        self.mcp_events: list[dict[str, Any]] = []

    def record_mcp_execution(self, trace_id: str, **fields: Any) -> None:
        self.mcp_events.append({"trace_id": trace_id, **fields})


class RaisingConnector:
    def call_tool(self, tool_name: str, arguments: dict[str, Any], server_name: str | None = None) -> dict[str, Any]:
        raise AssertionError("MCP call must not happen")


class CapturingConnector:
    def __init__(self) -> None:
        self.arguments: dict[str, Any] | None = None

    def call_tool(self, tool_name: str, arguments: dict[str, Any], server_name: str | None = None) -> dict[str, Any]:
        self.arguments = arguments
        return {"status": "ok", "row_count": 1, "rows": [{"user": "svc_app", "fail_count": 184}]}


class ManyRowsConnector:
    def call_tool(self, tool_name: str, arguments: dict[str, Any], server_name: str | None = None) -> dict[str, Any]:
        return {"status": "ok", "row_count": 20, "rows": [{"row": index, "value": "safe"} for index in range(20)]}
