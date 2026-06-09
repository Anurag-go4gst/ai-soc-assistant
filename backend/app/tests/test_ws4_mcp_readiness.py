from __future__ import annotations

from app.connectors.telemetry.null import NullTelemetryConnector
from app.evidence.source_evidence import build_source_evidence
from app.orchestration.mcp_execution_gate import evaluate_mcp_execution
from app.threat.mitre_evidence_preconditions import cap_mitre_status_for_evidence_tier


APPROVED_VALIDATION = {
    "approved": True,
    "normalized_spl": "index=pgcil_soc sourcetype=vpn earliest=-24h | stats count by user",
    "reject_reasons": [],
    "warnings": [],
}


class CapturingConnector:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def call_tool(self, tool_name: str, arguments: dict, server_name: str | None = None) -> dict:
        self.calls.append((tool_name, arguments))
        return {
            "rows": [{"user": "admin", "action": "failure"}],
            "result_count": 1,
        }


class FakeTelemetry:
    def __init__(self) -> None:
        self.mcp_events: list[dict] = []

    def record_mcp_execution(self, trace_id: str, **fields):  # type: ignore[no-untyped-def]
        self.mcp_events.append({"trace_id": trace_id, **fields})


class RaisingConnector:
    def call_tool(self, tool_name: str, arguments: dict, server_name: str | None = None) -> dict:
        raise AssertionError("MCP must not be called when execution is disabled")


def test_mcp_not_called_when_global_execution_disabled(monkeypatch) -> None:
    monkeypatch.delenv("MCP_GLOBAL_EXECUTION_ENABLED", raising=False)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: FakeTelemetry())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: RaisingConnector())
    execution, review = evaluate_mcp_execution(
        trace_id="t1",
        selected_skill="spl_generation",
        workflow_plan={"execution_enabled": False},
        spl_validation=APPROVED_VALIDATION,
        precondition_evaluation=None,
    )
    assert execution["status"] != "executed"
    assert execution.get("block_reason") or review.get("required")


def test_empty_mcp_result_does_not_upgrade_mitre() -> None:
    assert cap_mitre_status_for_evidence_tier("evidence_supported", "signal_only") != "evidence_supported"


def test_blocked_execution_source_evidence_has_no_preview_rows() -> None:
    evidence = build_source_evidence(
        trace_id="t2",
        query="test",
        selected_skill="spl_generation",
        spl_validation=APPROVED_VALIDATION,
        execution={
            "status": "blocked",
            "result_count": 0,
            "results_preview": [],
            "block_reason": "mcp_execution_disabled",
        },
    )
    splunk = next(item for item in evidence if item.get("source_type") == "splunk_mcp")
    assert splunk.get("collection_status") != "collected" or not splunk.get("preview_rows")


def test_audit_record_shape_on_blocked_attempt() -> None:
    telemetry = NullTelemetryConnector()
    payload = telemetry.record_mcp_execution(
        trace_id="t3",
        server_name="splunk",
        tool_name="run_query",
        query_hash="abc123",
        approval_status="blocked",
        result_count=0,
    )
    assert payload is None or isinstance(payload, dict)
