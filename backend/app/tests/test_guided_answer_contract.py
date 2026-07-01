"""REV4 batch 2 P13b — guided hybrid AnswerContract evidence surfacing."""

from __future__ import annotations

import pytest

from app.chat.contracts.answer_contract import AnswerContract, build_answer_contract
from app.chat.guided_answer_contract import enhance_answer_contract_for_guided_hybrid
from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.schemas.requests import ChatRequest

SAMPLE_QUERY = (
    "How should I investigate unusual outbound traffic from an OT host overnight?"
)


def _base_contract() -> AnswerContract:
    return build_answer_contract(
        intent_classification={
            "intent_family": "guided_investigation",
            "answer_goal": ["analyst_action_guidance"],
        },
        evidence_plan={
            "answer_mode": "guided_investigation",
            "mcp_allowed": False,
            "spl_allowed": False,
            "discovery_allowed": True,
            "safe_spl_execution_allowed": True,
            "freeform_spl_execution_allowed": False,
            "requires_hil": True,
        },
        mitre_decision={},
        severity_decision=None,
        spl_validation=None,
        execution={"status": "skipped"},
        human_review={"required": True},
    )


def test_enhance_surfaces_planned_hops_without_claiming_collection() -> None:
    contract = _base_contract()
    handoff = {
        "evidence_planned": 2,
        "evidence_collected": 0,
        "blocked_resources": [{"resource_id": "mcp_tool:splunk_run_query", "reason_code": "freeform_query_blocked"}],
    }
    mcp_evidence = [
        {
            "tool": "splunk_get_metadata",
            "outcome": "planned",
            "delivered": ["fields"],
            "payload": {},
        },
        {
            "tool": "guided_safe_catalog",
            "outcome": "planned",
            "delivered": ["template_bound_query"],
            "payload": {"template_id": "dns_beaconing_candidate", "provenance": "guided_safe_catalog"},
        },
    ]
    enhanced = enhance_answer_contract_for_guided_hybrid(
        contract,
        guided_handoff=handoff,
        mcp_evidence=mcp_evidence,
        evidence_plan=handoff,
    )
    assert enhanced.guided_collection_posture is not None
    assert enhanced.guided_collection_posture.get("remediation_performed") is False
    assert enhanced.guided_collection_posture.get("mcp_allowed") is False
    assert enhanced.evidence_planned == 2
    assert enhanced.evidence_collected == 0
    assert len(enhanced.discovery_evidence_summary or []) == 1
    assert (enhanced.discovery_evidence_summary or [])[0]["planned_only"] is True
    assert len(enhanced.safe_catalog_evidence_summary or []) == 1
    assert (enhanced.safe_catalog_evidence_summary or [])[0]["planned_only"] is True
    assert "guided investigation controls" in (enhanced.safe_catalog_evidence_summary or [])[0]["label"]
    assert enhanced.blocked_resources
    assert enhanced.hil_status == "required"
    assert enhanced.human_review_required is True
    assert enhanced.spl_execution_eligible is False


def test_collected_hop_counts_toward_evidence_collected_only() -> None:
    contract = _base_contract()
    enhanced = enhance_answer_contract_for_guided_hybrid(
        contract,
        guided_handoff={"evidence_planned": 2, "evidence_collected": 1},
        mcp_evidence=[
            {"tool": "splunk_get_info", "outcome": "collected", "delivered": ["server_version"], "payload": {}},
            {"tool": "guided_safe_catalog", "outcome": "planned", "delivered": [], "payload": {"template_id": "x"}},
        ],
        evidence_plan={},
    )
    assert enhanced.evidence_collected == 1
    assert (enhanced.safe_catalog_evidence_summary or [])[0]["planned_only"] is True
    assert (enhanced.discovery_evidence_summary or [])[0]["planned_only"] is False


@pytest.fixture(autouse=True)
def _hybrid_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_guided_hybrid_investigation_enabled", True)
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)
    monkeypatch.setattr(settings, "telemetry_mode", "none")
    monkeypatch.setattr(settings, "ai_soc_telemetry_sink", "none")


def test_live_pipeline_surfaces_guided_answer_contract_fields() -> None:
    response = build_live_chat_response(ChatRequest(message=SAMPLE_QUERY))
    contract = response.answer_contract
    assert isinstance(contract, dict)
    assert contract.get("guided_collection_posture") is not None
    assert contract.get("evidence_planned") is not None
    assert contract.get("evidence_collected") is not None
    assert contract.get("hil_status") == "required"
    assert contract.get("spl_execution_eligible") is False
    assert contract["guided_collection_posture"].get("remediation_performed") is False


def test_flag_off_does_not_surface_guided_contract_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_guided_hybrid_investigation_enabled", False)
    response = build_live_chat_response(ChatRequest(message=SAMPLE_QUERY))
    contract = response.answer_contract
    assert isinstance(contract, dict)
    assert contract.get("guided_collection_posture") is None
    assert contract.get("evidence_planned") is None
    assert contract.get("evidence_collected") is None
