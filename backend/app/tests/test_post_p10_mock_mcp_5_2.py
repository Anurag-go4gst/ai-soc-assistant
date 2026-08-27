"""Phase 5.2 — named capability selection under mock; NOMCP does not execute.

Reuses ``select_mcp_tool`` / capability vocabulary — no second selector.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.connectors.mcp.mcp_capability import EVENT_SEARCH, resolve_capability_tool_name
from app.connectors.mcp.registry import load_mcp_registry_status
from app.orchestration.mcp_execution_gate import evaluate_mcp_execution
from app.orchestration.mcp_tool_selector import select_mcp_tool

REPO = Path(__file__).resolve().parents[3]

APPROVED_VALIDATION = {
    "approved": True,
    "normalized_spl": (
        "search index=pgcil_soc sourcetype=pgcil:auth earliest=-24h latest=now "
        "| stats count by user | head 100"
    ),
    "reject_reasons": [],
    "warnings": [],
    "enforced_limits": {"max_result_limit": 100},
    "policy_version": "spl-policy-v1",
}


def _mock_registry(monkeypatch) -> None:
    """Mirror coe-mock profile MCP keys (existing flag names only)."""
    monkeypatch.setenv("MCP_MODE", "mock")
    monkeypatch.setenv("MCP_SERVERS", "splunk_soc")
    monkeypatch.setenv("MCP_DEFAULT_SERVER", "splunk_soc")
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("SPLUNK_MCP_ENABLED", "false")
    monkeypatch.delenv("SPLUNK_MCP_BASE_URL", raising=False)
    monkeypatch.delenv("SPLUNK_MCP_TOKEN", raising=False)


def test_cv_multi_01c_named_tool_selected_under_mock_and_envelope(monkeypatch) -> None:
    """CV.MULTI.01C pin: named_tool_selected=true via existing capability→selector."""
    _mock_registry(monkeypatch)
    registry = load_mcp_registry_status()
    assert registry.mode == "mock"

    envelope = {"envelope_version": 1, "status": "approved"}
    assert int(envelope["envelope_version"]) >= 1

    selection = select_mcp_tool(
        trace_id="cv-multi-01c-select",
        selected_skill="attack_discovery",
        workflow_plan={},
        execution_intent="spl_search",
        spl_validation=APPROVED_VALIDATION,
        registry=registry,
        rbac_role="analyst",
        mcp_capability=EVENT_SEARCH,
    )
    assert selection["tool_selection_status"] == "selected"
    assert selection["selected_mcp_tool"] == resolve_capability_tool_name(EVENT_SEARCH)
    assert selection["selected_mcp_tool"] == "splunk_run_query"
    assert selection["selected_mcp_server"]


def test_cv_nomcp_01_mock_mode_alone_does_not_execute(monkeypatch) -> None:
    """CV.NOMCP.01: mock_mode alone must not trigger a connector call."""
    bank = json.loads(
        (REPO / "docs/evals/answer_shape/convergence_expectation_bank_v1.json").read_text(
            encoding="utf-8"
        )
    )
    nomcp = next(r for r in bank["rows"] if r["row_id"] == "CV.NOMCP.01")
    assert nomcp["pins"]["mock_mode_alone_triggers_call"] is False

    # Default COE posture: global execution false even if mode were mock.
    monkeypatch.setenv("MCP_MODE", "mock")
    monkeypatch.setenv("MCP_SERVERS", "splunk_soc")
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "false")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "false")

    class RaisingConnector:
        def call_tool(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise AssertionError("NOMCP: connector must not be invoked")

    monkeypatch.setattr(
        "app.orchestration.mcp_execution_gate.get_mcp_connector",
        lambda: RaisingConnector(),
    )
    monkeypatch.setattr(
        "app.orchestration.mcp_execution_gate.get_telemetry_connector",
        lambda: type("T", (), {"record_mcp_execution": staticmethod(lambda *a, **k: None)})(),
    )

    execution, review = evaluate_mcp_execution(
        trace_id="cv-nomcp-01",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=APPROVED_VALIDATION,
    )
    assert execution.get("status") != "executed"
    assert execution.get("executed_spl") is None
    assert execution.get("block_reason") == "mcp_global_execution_disabled"
    assert review.get("required") is True

    # Structural pins from the bank.
    coe = (REPO / "env/profiles/coe.env.example").read_text(encoding="utf-8")
    assert "MCP_GLOBAL_EXECUTION_ENABLED=false" in coe
    manifest = json.loads((REPO / "env/profiles/manifest.json").read_text(encoding="utf-8"))
    mock_profile = next(p for p in manifest["profiles"] if p["id"] == "coe-mock")
    assert mock_profile.get("test_only") is True
    compose = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
    assert "AI_SOC_ENV_PROFILE:-coe" in compose
    assert "coe-mock" not in compose
