from __future__ import annotations

from app.config import settings
from app.connectors.mcp.live_readiness import evaluate_splunk_mcp_live_readiness


def test_default_posture_blocks_live_mcp_without_execution() -> None:
    report = evaluate_splunk_mcp_live_readiness()

    assert settings.mcp_global_execution_enabled is False
    assert report["ready_for_live_splunk_mcp"] is False
    assert report["mcp_called"] is False
    assert report["execution_authorized"] is False


def test_go_live_checklist_covers_required_gates() -> None:
    report = evaluate_splunk_mcp_live_readiness()
    steps = "\n".join(report["go_live_steps"]).lower()

    required_phrases = (
        "credentials",
        "allowlist",
        "mcp_global_execution_enabled",
        "governance regression",
        "hil",
    )
    for phrase in required_phrases:
        assert phrase in steps or phrase.replace("_", " ") in steps


def test_readiness_report_lists_operator_rollback_controls() -> None:
    report = evaluate_splunk_mcp_live_readiness()
    blockers = set(report["blockers"])

    assert "mcp_global_execution_enabled_required" in blockers
    assert "coe_contract_approval_required" in blockers
