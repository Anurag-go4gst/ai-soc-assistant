"""P4 — MCP mock-execution E2E contract matrix (plan §490).

Drives `evaluate_mcp_execution` through 20 execution-contract rows
(`docs/evals/mcp_execution_contract_20_bank.json`) with mock execution enabled in
the test env ONLY. Production posture (global + per-server exec flags) stays off.

Asserts the expected gate decision per row plus the cross-cutting invariants:
candidate SPL is never executed, every executed SPL is the fully-resolved
normalized SPL, and empty/error outcomes are honest (not silently dropped).

Staging live read-only execution (operator schema sign-off) is out of scope here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.connectors.mcp.registry import McpRegistryStatus, McpServerStatus
from app.orchestration.mcp_execution_gate import evaluate_mcp_execution

BANK = Path(__file__).resolve().parents[3] / "docs/evals/mcp_execution_contract_20_bank.json"

NORMALIZED = (
    "search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now "
    "| stats count by user | head 100"
)
APPROVED = {
    "approved": True,
    "normalized_spl": NORMALIZED,
    "reject_reasons": [],
    "warnings": [],
    "enforced_limits": {"max_result_limit": 100},
    "policy_version": "spl-policy-v1",
}
FAILED = {**APPROVED, "approved": False, "normalized_spl": None, "reject_reasons": ["missing_result_limit"]}
SLOTTED = {**APPROVED, "normalized_spl": "search index=<auth_index> sourcetype=<auth_sourcetype> earliest=-15m latest=now | stats count | head 100"}
CANDIDATE_ONLY = {**APPROVED, "normalized_spl": None, "candidate_spl": "search index=* | delete"}


class _FakeTelemetry:
    def __init__(self) -> None:
        self.mcp_events: list[dict[str, Any]] = []

    def record_mcp_execution(self, trace_id: str, **fields: Any) -> None:
        self.mcp_events.append({"trace_id": trace_id, **fields})


class _Connector:
    """Returns a fixed payload (or raises) and captures the executed arguments."""

    def __init__(self, payload: dict[str, Any] | None = None, raises: bool = False) -> None:
        self.payload = payload or {"status": "ok", "row_count": 1, "rows": [{"user": "svc_app", "fail_count": 184}]}
        self.raises = raises
        self.arguments: dict[str, Any] | None = None

    def call_tool(self, tool_name: str, arguments: dict[str, Any], server_name: str | None = None) -> dict[str, Any]:
        self.arguments = arguments
        if self.raises:
            raise RuntimeError("connector boom")
        return self.payload


def _mock_registry() -> McpRegistryStatus:
    return McpRegistryStatus(
        mode="mock",
        default_server="splunk_soc",
        global_execution_enabled=True,
        servers=[
            McpServerStatus(
                name="splunk_soc", type="splunk", enabled=True, implemented=True, configured=True,
                available=True, transport="mock", url_configured=False, command_configured=False,
                auth_mode="none", auth_configured=True, execution_enabled=True,
                discovered_tools_count=1, discovered_tools_safe_names=["splunk_run_query"],
                discovered_tools=[{
                    "name": "splunk_run_query", "description": "", "capability": "spl_search",
                    "categories": ["execution"], "blocked": False, "blocked_reason": None,
                }],
                blocked_tools_count=0, blocked_tools_safe_names=[], search_execution_allowed=True,
            )
        ],
    )


def _executed_mode(monkeypatch, *, require_confirmation: bool = False) -> None:
    """Enable mock execution + skip the demo HIL so the mechanics run end-to-end."""
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.ai_soc_demo_or_lab_execution_mode", True)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.ai_soc_allow_mock_execution_without_hil_in_demo", True)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.ai_soc_require_spl_execution_confirmation", require_confirmation)


def _patch(monkeypatch, *, telemetry, connector=None, registry=True) -> None:
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: telemetry)
    if connector is not None:
        monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: connector)
    if registry:
        monkeypatch.setattr("app.orchestration.mcp_execution_gate.load_mcp_registry_status", _mock_registry)


def _run(scenario: str, monkeypatch) -> tuple[dict[str, Any], dict[str, Any], _Connector | None]:
    tel = _FakeTelemetry()
    base = dict(trace_id=f"trace-{scenario}", selected_skill="attack_discovery", workflow_plan={})

    if scenario == "normalized_ready_mock_executed":
        _executed_mode(monkeypatch)
        conn = _Connector()
        _patch(monkeypatch, telemetry=tel, connector=conn)
        return (*evaluate_mcp_execution(**base, spl_validation=APPROVED), conn)

    if scenario == "missing_source_slots":
        _executed_mode(monkeypatch)
        conn = _Connector()
        _patch(monkeypatch, telemetry=tel, connector=conn)
        return (*evaluate_mcp_execution(**base, spl_validation=SLOTTED), conn)

    if scenario == "failed_validation":
        _patch(monkeypatch, telemetry=tel, registry=False)
        return (*evaluate_mcp_execution(**base, spl_validation=FAILED), None)

    if scenario == "global_execution_disabled":
        monkeypatch.delenv("MCP_GLOBAL_EXECUTION_ENABLED", raising=False)
        monkeypatch.delenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", raising=False)
        # Real env-driven registry so the disable actually takes effect.
        _patch(monkeypatch, telemetry=tel, connector=_Connector(raises=True), registry=False)
        return (*evaluate_mcp_execution(**base, spl_validation=APPROVED), None)

    if scenario == "per_server_execution_disabled":
        monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
        monkeypatch.delenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", raising=False)
        _patch(monkeypatch, telemetry=tel, connector=_Connector(raises=True), registry=False)
        return (*evaluate_mcp_execution(**base, spl_validation=APPROVED), None)

    if scenario == "confirmation_required":
        _executed_mode(monkeypatch, require_confirmation=True)
        conn = _Connector(raises=True)
        _patch(monkeypatch, telemetry=tel, connector=conn)
        return (*evaluate_mcp_execution(**base, spl_validation=APPROVED), conn)

    if scenario == "confirm_execution":
        _executed_mode(monkeypatch, require_confirmation=True)
        conn = _Connector()
        _patch(monkeypatch, telemetry=tel, connector=conn)
        return (*evaluate_mcp_execution(**base, spl_validation=APPROVED, execution_review_action="confirm"), conn)

    if scenario == "update_spl_invalid":
        _executed_mode(monkeypatch, require_confirmation=True)
        conn = _Connector(raises=True)
        _patch(monkeypatch, telemetry=tel, connector=conn)
        return (*evaluate_mcp_execution(**base, spl_validation=APPROVED, execution_review_action="update_spl", analyst_provided_spl="search index=* | delete everything"), conn)

    if scenario == "reject_execution":
        _executed_mode(monkeypatch, require_confirmation=True)
        conn = _Connector(raises=True)
        _patch(monkeypatch, telemetry=tel, connector=conn)
        return (*evaluate_mcp_execution(**base, spl_validation=APPROVED, execution_review_action="reject"), conn)

    if scenario == "empty_result":
        _executed_mode(monkeypatch)
        conn = _Connector({"status": "ok", "row_count": 0, "rows": []})
        _patch(monkeypatch, telemetry=tel, connector=conn)
        return (*evaluate_mcp_execution(**base, spl_validation=APPROVED), conn)

    if scenario == "search_timeout":
        _executed_mode(monkeypatch)
        conn = _Connector({"status": "timeout", "error": "job exceeded poll bound"})
        _patch(monkeypatch, telemetry=tel, connector=conn)
        return (*evaluate_mcp_execution(**base, spl_validation=APPROVED), conn)

    if scenario == "permission_denied":
        _executed_mode(monkeypatch)
        conn = _Connector({"status": "denied", "error": "permission_denied"})
        _patch(monkeypatch, telemetry=tel, connector=conn)
        return (*evaluate_mcp_execution(**base, spl_validation=APPROVED), conn)

    if scenario == "malformed_result":
        _executed_mode(monkeypatch)
        conn = _Connector({"status": "schema_invalid", "error": "bad envelope"})
        _patch(monkeypatch, telemetry=tel, connector=conn)
        return (*evaluate_mcp_execution(**base, spl_validation=APPROVED), conn)

    if scenario == "row_truncation":
        _executed_mode(monkeypatch)
        conn = _Connector({"status": "ok", "row_count": 100, "truncated": True, "truncation_reason": "row_limit",
                           "rows": [{"row": i, "value": "safe"} for i in range(100)]})
        _patch(monkeypatch, telemetry=tel, connector=conn)
        return (*evaluate_mcp_execution(**base, spl_validation=APPROVED), conn)

    if scenario == "unsafe_tool_requested":
        _executed_mode(monkeypatch)
        conn = _Connector(raises=True)
        _patch(monkeypatch, telemetry=tel, connector=conn)
        return (*evaluate_mcp_execution(**base, spl_validation=APPROVED, requested_mcp_tool="saved_search_dispatch"), conn)

    if scenario == "viewer_rbac_blocked":
        _executed_mode(monkeypatch)
        conn = _Connector(raises=True)
        _patch(monkeypatch, telemetry=tel, connector=conn)
        return (*evaluate_mcp_execution(**base, spl_validation=APPROVED, requested_mcp_tool="splunk_run_query", rbac_role="viewer"), conn)

    if scenario == "connector_raises":
        _executed_mode(monkeypatch)
        conn = _Connector(raises=True)
        _patch(monkeypatch, telemetry=tel, connector=conn)
        return (*evaluate_mcp_execution(**base, spl_validation=APPROVED), conn)

    if scenario == "precondition_not_ready":
        _patch(monkeypatch, telemetry=tel, registry=False)
        precondition = {"route_status": "blocked"}
        return (*evaluate_mcp_execution(**base, spl_validation=APPROVED, precondition_evaluation=precondition), None)

    if scenario == "llm_recommendation_cannot_override":
        _executed_mode(monkeypatch)
        conn = _Connector()
        _patch(monkeypatch, telemetry=tel, connector=conn)
        rec = {"recommended_tool": "saved_search_dispatch", "confidence": 0.99}
        return (*evaluate_mcp_execution(**base, spl_validation=APPROVED, llm_tool_recommendation=rec), conn)

    if scenario == "candidate_spl_never_executed":
        _executed_mode(monkeypatch)
        conn = _Connector(raises=True)
        _patch(monkeypatch, telemetry=tel, connector=conn)
        return (*evaluate_mcp_execution(**base, spl_validation=CANDIDATE_ONLY), conn)

    raise AssertionError(f"unknown scenario {scenario}")


def _bank_rows() -> list[dict[str, Any]]:
    return json.loads(BANK.read_text())["rows"]


def test_bank_has_twenty_rows() -> None:
    assert len(_bank_rows()) == 20


@pytest.mark.parametrize("row", _bank_rows(), ids=lambda r: r["id"])
def test_execution_contract_row(row: dict[str, Any], monkeypatch) -> None:
    execution, review, conn = _run(row["scenario"], monkeypatch)

    assert execution["status"] == row["expected_status"], (row["id"], execution.get("status"), execution)

    # Cross-cutting invariant: candidate SPL is never the executed SPL.
    if row["expects_executed_spl"]:
        assert execution["executed_spl"] == NORMALIZED
        if conn is not None:
            assert conn.arguments and conn.arguments.get("search_query") == NORMALIZED
    else:
        assert execution.get("executed_spl") is None

    if row.get("expected_label"):
        assert execution.get("execution_status_label") == row["expected_label"]
    if "expected_result_count" in row:
        assert execution.get("result_count") == row["expected_result_count"]
    if row.get("expected_reason"):
        blob = json.dumps({"e": execution, "r": review})
        assert row["expected_reason"] in blob, (row["id"], review.get("reason"), execution.get("block_reason"))
    if row.get("expected_warning"):
        warnings = json.dumps(execution.get("results_envelope") or execution)
        assert row["expected_warning"] in warnings or row["expected_warning"] in json.dumps(execution)

    # Honest outcome: every non-executed row surfaces an analyst-visible review
    # (a typed review and/or a recorded block reason) — never a silent drop.
    if not row["expects_executed_spl"]:
        assert review.get("review_type") or execution.get("block_reason"), (row["id"], review, execution)
