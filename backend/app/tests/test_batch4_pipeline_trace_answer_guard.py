"""Batch 4 — pipeline trace visibility and guarded final-answer validation."""

from __future__ import annotations

import json

import pytest

from app.api.routes_chat import chat
from app.chat.final_answer_validator import validate_final_answer
from app.schemas.requests import ChatRequest
from app.schemas.responses import AnalystResponseEnvelope
from app.threat.mitre_decision import resolve_mitre_decision
from app.threat.mitre_registry_schema import MitreRegistryMetadata
from app.use_cases.content_enrichment import enrichment_spl_governance, get_content_enrichment

UNSAFE_PHRASES = (
    "account compromised",
    "confirmed c2",
    "c2 confirmed",
    "confirmed ransomware",
    "malware confirmed",
    "spl was executed",
    "executed spl",
)


@pytest.fixture(autouse=True)
def _enable_control_plane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.control_plane_enabled", True)
    monkeypatch.setattr("app.config.settings.ai_soc_live_chat_ec_parity_enabled", False)
    monkeypatch.setattr("app.config.settings.langgraph_orchestration_enabled", False)
    monkeypatch.setattr("app.config.settings.telemetry_mode", "none")
    monkeypatch.setattr("app.config.settings.ai_soc_telemetry_sink", "none")
    monkeypatch.setattr(
        "app.config.settings.database_url",
        "postgresql://ai_soc:change-me@postgres:5432/ai_soc_assistant",
    )


def _chat(query: str):
    return chat(ChatRequest(message=query))


def _node_names(response) -> set[str]:
    trace = response.node_trace or []
    return {str(item.get("node_name")) for item in trace if isinstance(item, dict)}


def test_response_includes_additive_visibility_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.mcp_global_execution_enabled", False)
    response = _chat(
        "For alert ALT-2024-0891 (failed logins followed by a successful login from the same user "
        "in the last hour), what's the severity, MITRE mapping with status, and a governed SPL "
        "I can review—but not execute"
    )
    payload = json.loads(response.model_dump_json())
    assert payload.get("mitre_evidence_status")
    assert payload.get("spl_template_status") == "active"
    assert payload.get("node_trace")
    assert payload.get("answer_guard_status") in {"disabled", "passed", "skipped"}
    assert payload.get("final_answer_safety_status") in {"passed", "blocked", "skipped"}
    assert payload.get("selected_skill")
    assert payload.get("analyst_response") is not None


def test_node_trace_covers_key_stages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.mcp_global_execution_enabled", False)
    response = _chat(
        "For alert ALT-2024-0891 (failed logins followed by a successful login from the same user "
        "in the last hour), what's the severity, MITRE mapping with status, and a governed SPL "
        "I can review—but not execute"
    )
    names = _node_names(response)
    for expected in (
        "spl_template_status",
        "spl_validation",
        "execution_hil_decision",
        "mitre_evidence_status",
        "answer_guard",
        "final_answer_validation",
    ):
        assert expected in names
    assert (response.control_plane_trace or {}).get("node_trace")


def test_failed_login_does_not_claim_account_compromise(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.mcp_global_execution_enabled", False)
    response = _chat(
        "Map 148 failed login attempts across 12 accounts from external IPs to MITRE. "
        "There is no successful login, no endpoint telemetry, and no evidence of credential dumping."
    )
    analyst_json = (response.analyst_response.model_dump_json() if response.analyst_response else "").lower()
    for phrase in UNSAFE_PHRASES:
        assert phrase not in analyst_json
    assert response.final_answer_safety_status == "passed"


def test_success_after_failure_keeps_t1078_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.mcp_global_execution_enabled", False)
    response = _chat(
        "For alert ALT-2024-0891 (failed logins followed by a successful login from the same user "
        "in the last hour), what's the severity, MITRE mapping with status, and a governed SPL "
        "I can review—but not execute"
    )
    statuses = response.mitre_evidence_status or {}
    assert statuses.get("T1110.001") == "evidence_supported"
    assert statuses.get("T1078") == "candidate"
    combined = (
        f"{response.analyst_response.direct_answer_summary or ''} "
        f"{response.analyst_response.severity_safety_note or ''}"
    ).lower()
    assert "account compromised" not in combined


def test_powershell_does_not_claim_malware_without_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.mcp_global_execution_enabled", False)
    response = _chat(
        "For alert ALT-PS-001 investigate PowerShell suspicious command on WORKSTATION-12 "
        "with encoded base64 command line"
    )
    assert response.spl_template_status == "planned"
    analyst_json = (response.analyst_response.model_dump_json() if response.analyst_response else "").lower()
    assert "malware confirmed" not in analyst_json


def test_beaconing_does_not_claim_confirmed_c2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.mcp_global_execution_enabled", False)
    response = _chat(
        "For alert ALT-DNS-001 investigate beaconing pattern candidate with periodic DNS "
        "queries every 300 seconds from HOST-22"
    )
    assert response.spl_template_status == "planned"
    analyst_json = (response.analyst_response.model_dump_json() if response.analyst_response else "").lower()
    assert "c2 confirmed" not in analyst_json
    assert "confirmed c2" not in analyst_json


def test_ransomware_planned_path_shows_planned_template_not_active() -> None:
    governance = enrichment_spl_governance("endpoint_ransomware_impact_review")
    assert governance is not None
    assert governance["spl_template_status"] == "planned"
    decision = resolve_mitre_decision(
        use_case_id="endpoint_ransomware_impact_review",
        registry_metadata=MitreRegistryMetadata(
            mitre_candidate=list(get_content_enrichment("endpoint_ransomware_impact_review")["mitre_candidates"]),
            mitre_requires_evidence=True,
            mitre_requires_alert_context=False,
            mapping_rationale="batch4",
        ),
        intent_classification={
            "intent_family": "mitre_mapping",
            "answer_goal": ["mitre_mapping"],
            "requires_clarification": False,
        },
        evidence_plan={"answer_mode": "live_investigation"},
        source_refs=["ev-1"],
        alert_context_present=True,
        negative_evidence={"present_evidence": ["file_rename_volume"]},
    )
    for _tid, status in (decision.evidence_statuses or {}).items():
        assert status != "evidence_supported"


def test_execution_wording_review_gated_not_executed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.mcp_global_execution_enabled", False)
    response = _chat(
        "For alert ALT-2024-0891 (failed logins followed by a successful login from the same user "
        "in the last hour), what's the severity, MITRE mapping with status, and a governed SPL "
        "I can review—but not execute"
    )
    assert response.analyst_response is not None
    label = (response.analyst_response.execution_status_label or "").lower()
    summary = (response.analyst_response.direct_answer_summary or "").lower()
    assert "executed" not in summary or "not executed" in label or "review" in label


def test_final_validator_blocks_unsafe_account_compromise_claim() -> None:
    analyst = AnalystResponseEnvelope(
        direct_answer_summary="The account compromised after repeated failures.",
        mitre_mappings=[{"Technique": "T1110.001", "Status": "Candidate"}],
    )
    result = validate_final_answer(
        analyst_response=analyst,
        answer_contract={
            "mitre_answer_visible": True,
            "answer_goal": ["mitre_mapping"],
            "execution_status_label": "review_only_not_executed",
        },
        evidence_plan={"answer_mode": "live_investigation"},
        mitre_decision={"evidence_statuses": {"T1110.001": "evidence_supported"}},
    )
    assert result.guard_status == "blocked"
    assert "final.unsafe_account_compromise_claim" in (result.failed_checks or [])


def test_legacy_response_fields_remain_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.mcp_global_execution_enabled", False)
    response = _chat("What is MITRE T1110?")
    payload = json.loads(response.model_dump_json())
    for key in (
        "trace_id",
        "message",
        "selected_skill",
        "workflow_plan",
        "mitre_decision",
        "control_plane_trace",
        "answer_guard",
    ):
        assert key in payload
