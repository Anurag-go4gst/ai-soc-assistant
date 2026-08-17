"""Batch 1 — HIL hardening contract for mock MCP execution.

A valid SPL and a successful mock run never imply autonomous execution. These
tests are the authority on the human-review contract and the always-present
execution-status labels (`evidence_source`, `execution_status_label`).
"""

from __future__ import annotations

import time
from typing import Any

from app.connectors.mcp.discovery_snapshot import DiscoveredToolRecord, DiscoverySnapshot, get_discovery_snapshot_store
from app.orchestration.mcp_execution_gate import evaluate_mcp_execution

APPROVED_VALIDATION = {
    "approved": True,
    "normalized_spl": (
        "search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now "
        "| stats count by user | head 100"
    ),
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


class _FakeTelemetry:
    def __init__(self) -> None:
        self.mcp_events: list[dict[str, Any]] = []

    def record_mcp_execution(self, trace_id: str, **fields: Any) -> None:
        self.mcp_events.append({"trace_id": trace_id, **fields})


class _MockConnector:
    def call_tool(self, tool_name: str, arguments: dict[str, Any], server_name: str | None = None) -> dict[str, Any]:
        return {"status": "ok", "row_count": 1, "rows": [{"user": "svc_app", "fail_count": 184}]}


def _enable_mock_execution(monkeypatch) -> _FakeTelemetry:
    """Wire the gate so a valid SPL reaches the mock-success path."""
    telemetry = _FakeTelemetry()
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: telemetry)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: _MockConnector())
    return telemetry


def _set_flags(monkeypatch, *, require_hil: bool, demo_mode: bool, allow_in_demo: bool) -> None:
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.ai_soc_require_hil_for_mock_execution", require_hil)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.ai_soc_demo_or_lab_execution_mode", demo_mode)
    monkeypatch.setattr(
        "app.orchestration.mcp_execution_gate.settings.ai_soc_allow_mock_execution_without_hil_in_demo",
        allow_in_demo,
    )


def test_valid_spl_mock_non_demo_requires_human_review(monkeypatch) -> None:
    telemetry = _enable_mock_execution(monkeypatch)
    # Default-equivalent posture: HIL required, not a demo deployment.
    _set_flags(monkeypatch, require_hil=True, demo_mode=False, allow_in_demo=True)

    execution, review = evaluate_mcp_execution(
        trace_id="trace-hil-nondemo",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=APPROVED_VALIDATION,
    )

    # Mock still runs (evidence is generated) but must not be treated as autonomous.
    assert execution["status"] == "executed"
    assert execution["evidence_source"] == "mock"
    assert execution["execution_status_label"] == "review_required"
    assert review["required"] is True
    assert review["review_type"] == "mock_evidence_review"
    assert review["reason"] == "mock_execution_requires_analyst_review"
    assert any(e["event_type"] == "mcp_execution_requires_human_review" for e in telemetry.mcp_events)


def test_valid_spl_mock_demo_mode_executes_labelled(monkeypatch) -> None:
    _enable_mock_execution(monkeypatch)
    _set_flags(monkeypatch, require_hil=True, demo_mode=True, allow_in_demo=True)

    execution, review = evaluate_mcp_execution(
        trace_id="trace-hil-demo",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=APPROVED_VALIDATION,
    )

    assert execution["status"] == "executed"
    assert execution["evidence_source"] == "mock"
    assert execution["execution_status_label"] == "mock_executed"
    assert review["required"] is False


def test_demo_mode_without_allowance_still_requires_hil(monkeypatch) -> None:
    # Demo mode alone does NOT relax HIL; the allowance flag must also be set.
    _enable_mock_execution(monkeypatch)
    _set_flags(monkeypatch, require_hil=True, demo_mode=True, allow_in_demo=False)

    execution, review = evaluate_mcp_execution(
        trace_id="trace-hil-demo-noallow",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=APPROVED_VALIDATION,
    )

    assert execution["execution_status_label"] == "review_required"
    assert review["required"] is True


def test_invalid_spl_returns_spl_revision_unavailable(monkeypatch) -> None:
    _enable_mock_execution(monkeypatch)

    execution, review = evaluate_mcp_execution(
        trace_id="trace-hil-invalid",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=FAILED_VALIDATION,
    )

    assert execution["executed_spl"] is None
    assert execution["evidence_source"] == "unavailable"
    assert execution["execution_status_label"] == "not_executed"
    assert review["required"] is True
    assert review["review_type"] == "spl_revision"


def test_real_mcp_mode_returns_admin_action_required(monkeypatch) -> None:
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
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    get_discovery_snapshot_store().put(
        DiscoverySnapshot(
            server_name="splunk_soc",
            captured_at=time.time(),
            source="operator_refresh",
            status="ok",
            tools=(
                DiscoveredToolRecord(
                    name="run_splunk_query",
                    input_schema={"properties": {"search_query": {"type": "string"}}, "required": ["search_query"]},
                ),
            ),
        )
    )

    execution, review = evaluate_mcp_execution(
        trace_id="trace-hil-real",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=APPROVED_VALIDATION,
    )

    assert execution["executed_spl"] is None
    assert execution["evidence_source"] == "unavailable"
    assert execution["execution_status_label"] == "not_executed"
    # Step 3: live adapter is implemented; registry mode without URL/token fails
    # closed on configuration (operator supplies credentials at go-live).
    assert execution["block_reason"] == "splunk_mcp_not_configured"
    assert review["review_type"] == "connector_configuration"
