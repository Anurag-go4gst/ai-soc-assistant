"""Phase 5.4 — envelope_version bound into AUTH0 exact-call grants."""

from __future__ import annotations

from typing import Any

from app.orchestration.mcp_execution_gate import evaluate_mcp_execution
from app.orchestration.splunk_call_authorization import build_splunk_call_grant, grants_match

APPROVED_A = (
    "search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now "
    "| stats count by user | head 100"
)
VALIDATION_A = {
    "approved": True,
    "normalized_spl": APPROVED_A,
    "reject_reasons": [],
    "warnings": [],
    "enforced_limits": {"max_result_limit": 100},
    "policy_version": "spl-policy-v1",
}


def test_fingerprint_changes_with_envelope_version() -> None:
    base = build_splunk_call_grant(
        trace_id="t1",
        normalized_spl=APPROVED_A,
        selected_mcp_server="splunk_soc",
        selected_mcp_tool="splunk_run_query",
        rbac_role="analyst",
        envelope_version=1,
    )
    stale = build_splunk_call_grant(
        trace_id="t1",
        normalized_spl=APPROVED_A,
        selected_mcp_server="splunk_soc",
        selected_mcp_tool="splunk_run_query",
        rbac_role="analyst",
        envelope_version=2,
    )
    missing = build_splunk_call_grant(
        trace_id="t1",
        normalized_spl=APPROVED_A,
        selected_mcp_server="splunk_soc",
        selected_mcp_tool="splunk_run_query",
        rbac_role="analyst",
        envelope_version=None,
    )
    assert base["envelope_version"] == 1
    assert base["fingerprint"] != stale["fingerprint"]
    assert base["fingerprint"] != missing["fingerprint"]
    assert grants_match({"call_grant": base}, stale) is False
    assert grants_match({"call_grant": base}, missing) is False
    assert grants_match({"call_grant": base}, base) is True


def test_gate_threads_envelope_version_and_rejects_stale(monkeypatch) -> None:
    _enable_mock(monkeypatch)
    first, _ = evaluate_mcp_execution(
        trace_id="env-grant-1",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=VALIDATION_A,
        approved_investigation_envelope={"envelope_version": 1},
    )
    pending = first.get("pending_execution_confirmation")
    assert isinstance(pending, dict)
    grant_v1 = pending.get("call_grant")
    assert isinstance(grant_v1, dict)
    assert grant_v1.get("envelope_version") == 1

    blocked, blocked_review = evaluate_mcp_execution(
        trace_id="env-grant-1",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=VALIDATION_A,
        execution_review_action="confirm",
        pending_execution=pending,
        approved_investigation_envelope={"envelope_version": 2},
    )
    assert blocked.get("executed_spl") is None
    assert blocked.get("block_reason") == "exact_call_grant_invalidated"
    assert blocked_review.get("reason") == "exact_call_grant_invalidated"


def test_missing_envelope_grant_does_not_match_approved_envelope_grant() -> None:
    pre = build_splunk_call_grant(
        trace_id="t-pre",
        normalized_spl=APPROVED_A,
        selected_mcp_tool="splunk_run_query",
        envelope_version=None,
    )
    post = build_splunk_call_grant(
        trace_id="t-pre",
        normalized_spl=APPROVED_A,
        selected_mcp_tool="splunk_run_query",
        envelope_version=1,
    )
    assert grants_match({"call_grant": pre}, post) is False


def _enable_mock(monkeypatch) -> None:
    monkeypatch.setenv("MCP_MODE", "mock")
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.ai_soc_demo_or_lab_execution_mode", True)
    monkeypatch.setattr(
        "app.orchestration.mcp_execution_gate.settings.ai_soc_allow_mock_execution_without_hil_in_demo",
        True,
    )
    monkeypatch.setattr(
        "app.orchestration.mcp_execution_gate.settings.ai_soc_require_spl_execution_confirmation",
        True,
    )
    monkeypatch.setattr(
        "app.orchestration.mcp_execution_gate.get_telemetry_connector",
        lambda: _FakeTelemetry(),
    )
    monkeypatch.setattr(
        "app.orchestration.mcp_execution_gate.get_mcp_connector",
        lambda: _RaisingConnector(),
    )


class _FakeTelemetry:
    def record_mcp_execution(self, *args: Any, **kwargs: Any) -> None:
        return None


class _RaisingConnector:
    def call_tool(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("stale envelope must fail before connector call")
