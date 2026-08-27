"""Phase 5.5 — mock MCP only after ApprovedInvestigationEnvelope."""

from __future__ import annotations

from typing import Any

from app.orchestration.mcp_execution_gate import evaluate_mcp_execution

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


class _RaisingConnector:
    def call_tool(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("connector must not run before ApprovedInvestigationEnvelope")


def _enable_mock(monkeypatch) -> None:
    monkeypatch.setenv("MCP_MODE", "mock")
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(
        "app.orchestration.mcp_execution_gate.settings.ai_soc_demo_or_lab_execution_mode",
        True,
    )
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
        lambda: type("T", (), {"record_mcp_execution": staticmethod(lambda *a, **k: None)})(),
    )
    monkeypatch.setattr(
        "app.orchestration.mcp_execution_gate.get_mcp_connector",
        lambda: _RaisingConnector(),
    )


def test_pre_approve_mock_invocation_blocked(monkeypatch) -> None:
    _enable_mock(monkeypatch)
    execution, review = evaluate_mcp_execution(
        trace_id="pre-env",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=VALIDATION_A,
        require_approved_investigation_envelope=True,
        approved_investigation_envelope=None,
    )
    assert execution.get("executed_spl") is None
    assert execution.get("block_reason") == "investigation_envelope_required"
    assert review.get("reason") == "investigation_envelope_required"
    assert execution.get("execution") == "blocked_pre_envelope"


def test_post_envelope_pending_confirmation_carries_version(monkeypatch) -> None:
    _enable_mock(monkeypatch)
    execution, _review = evaluate_mcp_execution(
        trace_id="post-env",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=VALIDATION_A,
        require_approved_investigation_envelope=True,
        approved_investigation_envelope={"envelope_version": 3},
    )
    pending = execution.get("pending_execution_confirmation")
    assert isinstance(pending, dict)
    grant = pending.get("call_grant")
    assert isinstance(grant, dict)
    assert grant.get("envelope_version") == 3
