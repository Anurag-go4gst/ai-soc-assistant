from __future__ import annotations

import pytest

from app.orchestration.execution_confirmation import (
    build_execution_confirmation_review,
    confirmation_required,
    resolve_execution_spl,
)
from app.orchestration.mcp_execution_gate import evaluate_mcp_execution

APPROVED_VALIDATION = {
    "approved": True,
    "normalized_spl": "search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | stats count by user | head 100",
    "reject_reasons": [],
    "warnings": [],
    "enforced_limits": {"max_result_limit": 100},
    "policy_version": "spl-policy-v1",
}


def test_build_execution_confirmation_review_includes_proposed_spl() -> None:
    review = build_execution_confirmation_review(
        normalized_spl=APPROVED_VALIDATION["normalized_spl"],
        selected_mcp_tool="splunk_run_query",
        selected_mcp_server="mock",
    )
    assert review["review_type"] == "spl_execution_confirmation"
    assert review["proposed_normalized_spl"] == APPROVED_VALIDATION["normalized_spl"]
    assert "confirm_execution" in review["allowed_actions"]


def test_confirmation_required_blocks_until_confirm(monkeypatch) -> None:
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.ai_soc_require_spl_execution_confirmation", True)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: FakeTelemetry())

    execution, review = evaluate_mcp_execution(
        trace_id="trace-confirm",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=APPROVED_VALIDATION,
    )

    assert execution["status"] == "requires_human_review"
    assert execution["executed_spl"] is None
    assert review["review_type"] == "spl_execution_confirmation"
    assert execution["pending_execution_confirmation"]["normalized_spl"] == APPROVED_VALIDATION["normalized_spl"]


def test_confirm_runs_safe_test_and_executes(monkeypatch) -> None:
    connector = CapturingConnector()
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.ai_soc_require_spl_execution_confirmation", True)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.ai_soc_demo_or_lab_execution_mode", True)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.ai_soc_allow_mock_execution_without_hil_in_demo", True)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: FakeTelemetry())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: connector)

    pending = {"normalized_spl": APPROVED_VALIDATION["normalized_spl"]}
    execution, review = evaluate_mcp_execution(
        trace_id="trace-run",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=APPROVED_VALIDATION,
        execution_review_action="confirm",
        pending_execution=pending,
    )

    assert execution["status"] == "executed"
    assert connector.arguments["search_query"] == APPROVED_VALIDATION["normalized_spl"]
    assert connector.arguments["max_results"] > 0
    assert review["required"] is False


def test_updated_spl_must_pass_validator(monkeypatch) -> None:
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.ai_soc_require_spl_execution_confirmation", True)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: FakeTelemetry())

    execution, review = evaluate_mcp_execution(
        trace_id="trace-bad-update",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=APPROVED_VALIDATION,
        execution_review_action="update_spl",
        analyst_provided_spl="search index=* | delete",
    )

    assert execution["status"] == "requires_human_review"
    assert review["review_type"] == "spl_revision"
    assert review["reason"] == "analyst_updated_spl_validation_failed"


def test_resolve_execution_spl_without_confirmation_flag(monkeypatch) -> None:
    monkeypatch.setattr("app.orchestration.execution_confirmation.settings.ai_soc_require_spl_execution_confirmation", False)
    validation, review = resolve_execution_spl(
        spl_validation=APPROVED_VALIDATION,
        execution_review_action=None,
        analyst_provided_spl=None,
        pending_execution=None,
    )
    assert review is None
    assert validation is not None
    assert validation["approved"] is True


def test_explicit_live_confirmation_requirement_overrides_disabled_flag(monkeypatch) -> None:
    monkeypatch.setattr("app.orchestration.execution_confirmation.settings.ai_soc_require_spl_execution_confirmation", False)
    validation, review = resolve_execution_spl(
        spl_validation=APPROVED_VALIDATION,
        execution_review_action=None,
        analyst_provided_spl=None,
        pending_execution=None,
        require_confirmation=True,
    )
    assert validation is None
    assert review is None


class FakeTelemetry:
    def __init__(self) -> None:
        self.mcp_events: list[dict] = []

    def record_mcp_execution(self, trace_id: str, **payload) -> None:
        self.mcp_events.append({"trace_id": trace_id, **payload})


class CapturingConnector:
    def __init__(self) -> None:
        self.arguments: dict = {}

    def call_tool(self, tool_name: str, arguments: dict, server_name: str | None = None) -> dict:
        self.arguments = dict(arguments)
        return {
            "status": "ok",
            "mock": True,
            "row_count": 1,
            "rows": [{"user": "svc_app", "count": 1}],
        }
