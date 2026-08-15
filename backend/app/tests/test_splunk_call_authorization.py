"""Plan 8 AUTH0 — exact-call Splunk authorization."""

from __future__ import annotations

from typing import Any

from app.orchestration.mcp_execution_gate import evaluate_mcp_execution
from app.orchestration.splunk_call_authorization import build_splunk_call_grant, grants_match


APPROVED_A = (
    "search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now "
    "| stats count by user | head 100"
)
APPROVED_B = (
    "search index=pgcil_soc sourcetype=pgcil:auth earliest=-24h latest=now "
    "| stats count by src | head 50"
)
APPROVED_SOURCE = (
    "search index=other_soc sourcetype=pgcil:auth earliest=-15m latest=now "
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
VALIDATION_B = {**VALIDATION_A, "normalized_spl": APPROVED_B, "enforced_limits": {"max_result_limit": 50}}
VALIDATION_SOURCE = {**VALIDATION_A, "normalized_spl": APPROVED_SOURCE}


def test_fingerprint_changes_when_normalized_spl_changes() -> None:
    a = build_splunk_call_grant(trace_id="t1", normalized_spl=APPROVED_A, selected_mcp_tool="splunk_run_query")
    b = build_splunk_call_grant(trace_id="t1", normalized_spl=APPROVED_B, selected_mcp_tool="splunk_run_query")
    assert a["fingerprint"] != b["fingerprint"]
    assert a["llm_granted"] is False


def test_fingerprint_changes_for_time_source_tool_identity_limits_timeout_hil() -> None:
    original = build_splunk_call_grant(
        trace_id="t1",
        normalized_spl=APPROVED_A,
        selected_mcp_server="splunk_soc",
        selected_mcp_tool="splunk_run_query",
    )
    assert original["fingerprint"] != build_splunk_call_grant(
        trace_id="t1",
        normalized_spl=APPROVED_A,
        selected_mcp_server="splunk_soc",
        selected_mcp_tool="splunk_run_query",
        earliest="-24h",
    )["fingerprint"]
    assert original["fingerprint"] != build_splunk_call_grant(
        trace_id="t1",
        normalized_spl=APPROVED_A,
        selected_mcp_server="splunk_soc",
        selected_mcp_tool="splunk_run_query",
        indexes=["other_soc"],
    )["fingerprint"]
    assert original["fingerprint"] != build_splunk_call_grant(
        trace_id="t1",
        normalized_spl=APPROVED_A,
        selected_mcp_server="splunk_soc",
        selected_mcp_tool="splunk_run_saved_search",
    )["fingerprint"]
    assert original["fingerprint"] != build_splunk_call_grant(
        trace_id="t1",
        normalized_spl=APPROVED_A,
        selected_mcp_server="splunk_soc",
        selected_mcp_tool="splunk_run_query",
        identity="soc_lead",
        rbac_role="soc_lead",
    )["fingerprint"]
    assert original["fingerprint"] != build_splunk_call_grant(
        trace_id="t1",
        normalized_spl=APPROVED_A,
        selected_mcp_server="splunk_soc",
        selected_mcp_tool="splunk_run_query",
        max_result_limit=10,
    )["fingerprint"]
    assert original["fingerprint"] != build_splunk_call_grant(
        trace_id="t1",
        normalized_spl=APPROVED_A,
        selected_mcp_server="splunk_soc",
        selected_mcp_tool="splunk_run_query",
        timeout_ms=1,
    )["fingerprint"]
    assert original["fingerprint"] != build_splunk_call_grant(
        trace_id="t1",
        normalized_spl=APPROVED_A,
        selected_mcp_server="splunk_soc",
        selected_mcp_tool="splunk_run_query",
        hil_required=False,
    )["fingerprint"]


def test_expired_or_consumed_or_llm_grant_is_rejected() -> None:
    current = build_splunk_call_grant(trace_id="t1", normalized_spl=APPROVED_A, now=1_000.0)
    expired = build_splunk_call_grant(trace_id="t1", normalized_spl=APPROVED_A, now=1.0, ttl_seconds=1)
    assert grants_match({"call_grant": expired}, current, now=1_000.0) is False
    consumed = {**current, "consumed": True}
    assert grants_match({"call_grant": consumed, "consumed": True}, current) is False
    llm = {**current, "llm_granted": True}
    assert grants_match({"call_grant": llm}, current) is False


def test_pending_grant_accepts_same_call_and_rejects_mutated_spl(monkeypatch) -> None:
    first = _pending_confirmation(monkeypatch, VALIDATION_A, trace_id="auth0-same")
    pending = first.get("pending_execution_confirmation")
    assert pending and pending.get("call_grant")

    accepted, review = _confirm(monkeypatch, VALIDATION_A, pending, trace_id="auth0-same")
    assert accepted.get("executed_spl") == APPROVED_A
    assert review.get("required") is False
    assert accepted.get("call_grant_consumed") is True

    mutated, mutated_review = _confirm(monkeypatch, VALIDATION_B, pending, trace_id="auth0-same")
    assert mutated.get("executed_spl") is None
    assert mutated.get("block_reason") == "exact_call_grant_invalidated"
    assert mutated_review.get("reason") == "exact_call_grant_invalidated"


def test_pending_grant_rejects_source_identity_tool_limit_timeout_expiry_consumed(monkeypatch) -> None:
    first = _pending_confirmation(monkeypatch, VALIDATION_A, trace_id="auth0-mut", rbac_role="analyst")
    pending = dict(first["pending_execution_confirmation"])

    source, source_review = _confirm(monkeypatch, VALIDATION_SOURCE, pending, trace_id="auth0-mut", rbac_role="analyst")
    assert source.get("block_reason") == "exact_call_grant_invalidated"
    assert source_review["reason"] == "exact_call_grant_invalidated"

    identity, identity_review = _confirm(monkeypatch, VALIDATION_A, pending, trace_id="auth0-mut", rbac_role="soc_lead")
    assert identity.get("block_reason") == "exact_call_grant_invalidated"
    assert identity_review["reason"] == "exact_call_grant_invalidated"

    tool_pending = dict(pending)
    tool_pending["call_grant"] = build_splunk_call_grant(
        trace_id="auth0-mut",
        identity="analyst",
        rbac_role="analyst",
        selected_mcp_server=str(pending.get("selected_mcp_server") or "splunk_soc"),
        selected_mcp_tool="splunk_run_saved_search",
        normalized_spl=APPROVED_A,
        hil_required=True,
        now=pending["call_grant"]["issued_at"],
    )
    tool, tool_review = _confirm(monkeypatch, VALIDATION_A, tool_pending, trace_id="auth0-mut", rbac_role="analyst")
    assert tool.get("block_reason") == "exact_call_grant_invalidated"
    assert tool_review["reason"] == "exact_call_grant_invalidated"

    limit_pending = dict(pending)
    limit_pending["call_grant"] = build_splunk_call_grant(
        trace_id="auth0-mut",
        identity="analyst",
        rbac_role="analyst",
        selected_mcp_server=str(pending.get("selected_mcp_server") or "splunk_soc"),
        selected_mcp_tool=str(pending.get("selected_mcp_tool") or "splunk_run_query"),
        normalized_spl=APPROVED_A,
        hil_required=True,
        max_result_limit=10,
        timeout_ms=pending["call_grant"]["timeout_ms"],
        now=pending["call_grant"]["issued_at"],
    )
    limit, limit_review = _confirm(monkeypatch, VALIDATION_A, limit_pending, trace_id="auth0-mut", rbac_role="analyst")
    assert limit.get("block_reason") == "exact_call_grant_invalidated"
    assert limit_review["reason"] == "exact_call_grant_invalidated"

    monkeypatch.setattr("app.orchestration.splunk_call_authorization.settings.mcp_search_job_timeout_ms", 1)
    timeout, timeout_review = _confirm(monkeypatch, VALIDATION_A, pending, trace_id="auth0-mut", rbac_role="analyst")
    assert timeout.get("block_reason") == "exact_call_grant_invalidated"
    assert timeout_review["reason"] == "exact_call_grant_invalidated"
    monkeypatch.setattr(
        "app.orchestration.splunk_call_authorization.settings.mcp_search_job_timeout_ms",
        pending["call_grant"]["timeout_ms"],
    )

    expired_pending = dict(pending)
    expired_pending["call_grant"] = {**pending["call_grant"], "expires_at": 1}
    expired, expired_review = _confirm(monkeypatch, VALIDATION_A, expired_pending, trace_id="auth0-mut", rbac_role="analyst")
    assert expired.get("block_reason") == "exact_call_grant_invalidated"
    assert expired_review["reason"] == "exact_call_grant_invalidated"

    consumed_pending = dict(pending)
    consumed_pending["consumed"] = True
    consumed, consumed_review = _confirm(monkeypatch, VALIDATION_A, consumed_pending, trace_id="auth0-mut", rbac_role="analyst")
    assert consumed.get("block_reason") == "exact_call_grant_invalidated"
    assert consumed_review["reason"] == "exact_call_grant_invalidated"


def test_unapproved_normalized_spl_still_cannot_execute(monkeypatch) -> None:
    _enable_mock_execution(monkeypatch, require_confirmation=True)
    blocked, _review = evaluate_mcp_execution(
        trace_id="auth0-null",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation={"approved": False, "normalized_spl": None, "reject_reasons": ["unvalidated"]},
    )
    assert blocked.get("executed_spl") is None
    assert blocked.get("status") in {"requires_human_review", "skipped", "blocked"}


def _enable_mock_execution(monkeypatch, *, require_confirmation: bool = True) -> None:
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.ai_soc_demo_or_lab_execution_mode", True)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.ai_soc_allow_mock_execution_without_hil_in_demo", True)
    monkeypatch.setattr(
        "app.orchestration.mcp_execution_gate.settings.ai_soc_require_spl_execution_confirmation",
        require_confirmation,
    )
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: _CapturingConnector())


def _pending_confirmation(monkeypatch, validation: dict[str, Any], *, trace_id: str, rbac_role: str | None = None) -> dict[str, Any]:
    _enable_mock_execution(monkeypatch, require_confirmation=True)
    execution, _review = evaluate_mcp_execution(
        trace_id=trace_id,
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=validation,
        rbac_role=rbac_role,
    )
    return execution


def _confirm(
    monkeypatch,
    validation: dict[str, Any],
    pending: dict[str, Any],
    *,
    trace_id: str,
    rbac_role: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _enable_mock_execution(monkeypatch, require_confirmation=True)
    return evaluate_mcp_execution(
        trace_id=trace_id,
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=validation,
        execution_review_action="confirm",
        pending_execution=pending,
        rbac_role=rbac_role,
    )


class _FakeTelemetry:
    def record_mcp_execution(self, *args, **kwargs) -> None:
        return None


class _CapturingConnector:
    def __init__(self) -> None:
        self.arguments: dict[str, Any] | None = None

    def call_tool(self, tool_name: str, arguments: dict[str, Any], server_name: str | None = None) -> dict[str, Any]:
        self.arguments = arguments
        return {"status": "ok", "row_count": 1, "rows": [{"user": "svc_app", "fail_count": 184}]}
