"""Stage 3M-S2: MCP result adapter and gate/evidence envelope consumption."""

from __future__ import annotations

from typing import Any

from app.connectors.mcp.splunk_result_adapter import (
    MockConnectorResultAdapter,
    UnconfirmedRealMcpResultAdapter,
    adapt_mcp_search_payload,
    execution_preview_from_envelope,
    get_splunk_result_adapter,
)
from app.evidence.source_evidence import build_source_evidence
from app.orchestration.mcp_execution_gate import evaluate_mcp_execution

APPROVED_VALIDATION = {
    "approved": True,
    "normalized_spl": "search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | stats count by user | head 100",
    "reject_reasons": [],
    "warnings": [],
    "enforced_limits": {"max_result_limit": 100},
    "policy_version": "spl-policy-v1",
}


def test_mock_adapter_normalizes_connector_payload() -> None:
    envelope = MockConnectorResultAdapter().adapt_search_result(
        {"status": "ok", "rows": [{"user": "svc_app", "fail_count": 184}], "row_count": 1, "mock": True},
        trace_id="trace-1",
    )
    assert envelope.origin == "mock_connector"
    assert envelope.schema_confirmed is False
    assert envelope.schema_confirmed_reason == "mock_payload"
    assert envelope.row_count == 1


def test_real_adapter_marks_schema_unverified() -> None:
    envelope = UnconfirmedRealMcpResultAdapter().adapt_search_result(
        {"status": "ok", "rows": [{"host": "app"}], "row_count": 1},
    )
    assert envelope.origin == "real_mcp"
    assert envelope.schema_confirmed is False
    assert envelope.schema_confirmed_reason == "real_schema_unverified"
    assert "real_schema_unverified" in envelope.warnings


def test_get_adapter_by_mode() -> None:
    assert isinstance(get_splunk_result_adapter("mock"), MockConnectorResultAdapter)
    assert isinstance(get_splunk_result_adapter("splunk_mcp"), UnconfirmedRealMcpResultAdapter)


def test_execution_preview_from_envelope_caps_preview() -> None:
    from app.connectors.mcp.splunk_result_fixture import envelope_from_fixture_payload

    rows = [{"n": i} for i in range(10)]
    envelope = envelope_from_fixture_payload({"status": "ok", "rows": rows, "row_count": 10})
    count, preview = execution_preview_from_envelope(envelope, preview_cap=5)
    assert count == 5
    assert len(preview) == 5


def test_gate_execution_includes_envelope_dict(monkeypatch) -> None:
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())

    execution, review = evaluate_mcp_execution(
        trace_id="trace-s2",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=APPROVED_VALIDATION,
    )

    assert execution["status"] == "executed"
    assert review["required"] is False
    envelope = execution.get("splunk_result_envelope")
    assert isinstance(envelope, dict)
    assert envelope.get("schema_confirmed") is False
    assert envelope.get("origin") == "mock_connector"
    assert execution["results_preview"] == envelope["rows"][:5]


def test_source_evidence_uses_envelope_not_raw_preview() -> None:
    execution = {
        "status": "executed",
        "execution_intent": "spl_search",
        "selected_mcp_server": "splunk_soc",
        "selected_mcp_tool": "run_splunk_query",
        "executed_spl": APPROVED_VALIDATION["normalized_spl"],
        "result_count": 1,
        "results_preview": [{"user": "legacy_should_not_win"}],
        "splunk_result_envelope": {
            "status": "ok",
            "origin": "mock_connector",
            "schema_confirmed": False,
            "schema_confirmed_reason": "mock_payload",
            "row_count": 1,
            "total_row_count": 1,
            "truncated": False,
            "truncation_reason": None,
            "fields": ["user", "fail_count"],
            "rows": [{"user": "svc_app", "fail_count": 184}],
            "duration_ms": 3,
            "error_code": None,
            "error_message": None,
            "warnings": ["fixture_payload"],
            "provenance": "ai_soc_fixture_adapter_v1",
            "request_ref": "trace-s2",
        },
    }
    evidence = build_source_evidence(
        trace_id="trace-s2",
        query="failed logins",
        selected_skill="attack_discovery",
        spl_validation=APPROVED_VALIDATION,
        execution=execution,
    )
    splunk = next(item for item in evidence if item["source_type"] == "splunk_mcp")
    assert splunk["preview_rows"] == [{"user": "svc_app", "fail_count": 184}]
    assert "schema_unconfirmed:mock_payload" in splunk["warnings"]


class _FakeTelemetry:
    def record_mcp_execution(self, trace_id: str, **fields: Any) -> None:
        return None
