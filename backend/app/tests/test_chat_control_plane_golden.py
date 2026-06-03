from __future__ import annotations

import pytest

from app.api.routes_chat import chat
from app.schemas.requests import ChatRequest


@pytest.fixture(autouse=True)
def _enable_control_plane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.control_plane_enabled", True)


def _chat(query: str):
    response = chat(ChatRequest(message=query))
    assert response.query_to_intent is not None
    assert response.evidence_plan is not None
    assert response.route_adjudication is not None
    assert response.control_plane_trace is not None
    assert response.response_mode is not None
    assert response.synthesis_mode is not None
    return response


def test_policy_escalation_failed_login_rag_only_no_spl_mcp_or_visible_mitre() -> None:
    response = _chat("What is the escalation policy for repeated failed login alerts?")
    intent = response.query_to_intent["intent_classification"]
    assert intent["intent_family"] == "policy_knowledge"
    assert response.evidence_plan["answer_mode"] == "rag_only"
    assert response.route_adjudication["final_route"] == "knowledge_recall"
    assert response.candidate_spl is None
    assert response.spl_validation is None
    assert response.execution is not None
    assert response.execution.execution_intent == "none"
    assert response.mitre_mappings == []
    assert response.mitre_decision is not None
    assert response.mitre_decision["answer_visible"] is False


def test_hybrid_failed_login_action_fails_closed_on_missing_slots_and_hil() -> None:
    response = _chat(
        "Find accounts failing login in the last 24 hours, exclude service accounts, "
        "and tell me what analyst action I should take"
    )
    assert response.evidence_plan["answer_mode"] == "hybrid"
    assert response.evidence_plan["needs_spl"] is True
    assert response.evidence_plan["needs_mcp"] is True
    assert response.spl_validation is not None
    assert response.spl_validation.approved is False
    assert "user_constraints_not_encoded" in response.spl_validation.reject_reasons
    assert response.execution is not None
    assert response.execution.status == "requires_human_review"
    assert response.human_review is not None
    assert response.human_review.required is True
    assert response.mitre_mappings == []


def test_mitre_mapping_without_alert_context_requires_clarification() -> None:
    response = _chat("Map 148 failed logins across 12 accounts from external IPs to MITRE")
    assert response.evidence_plan["answer_mode"] == "clarification"
    assert response.route_adjudication["authority_source"] == "intent_clarification"
    assert response.human_review is not None
    assert response.human_review.required is True
    assert response.human_review.review_type == "intent_clarification"
    assert response.candidate_spl is None
    assert response.mitre_mappings == []


def test_generate_spl_top_failed_login_users_rejects_missing_slot_binding_no_mcp() -> None:
    response = _chat("Generate SPL for the top failed-login users in the last 24 hours")
    assert response.evidence_plan["needs_spl"] is True
    assert response.evidence_plan["mcp_allowed"] is False
    assert response.candidate_spl is not None
    assert response.spl_validation is not None
    assert response.spl_validation.approved is False
    assert "user_constraints_not_encoded" in response.spl_validation.reject_reasons
    assert response.execution is not None
    assert response.execution.block_reason == "mcp_not_allowed_by_evidence_plan"


def test_dga_investigation_steps_are_knowledge_rag_only() -> None:
    response = _chat("Explain investigation steps for DGA detection")
    intent = response.query_to_intent["intent_classification"]
    assert intent["intent_family"] == "knowledge_only"
    assert response.evidence_plan["answer_mode"] == "rag_only"
    assert response.candidate_spl is None
    assert response.execution is not None
    assert response.execution.execution_intent == "none"


def test_top_failed_login_users_exclude_service_accounts_rejects_slots_before_mcp() -> None:
    response = _chat(
        "Show top users with failed login count in the last 24 hours and exclude service accounts"
    )
    assert response.evidence_plan["answer_mode"] == "live_investigation"
    assert response.spl_validation is not None
    assert response.spl_validation.approved is False
    assert "missing_binding:exclude_service_accounts" in response.spl_validation.reject_reasons
    assert "missing_binding:last_24h" in response.spl_validation.reject_reasons
    assert response.execution is not None
    assert response.execution.status == "requires_human_review"
    assert response.execution.block_reason == "spl_validation_failed"


def test_when_failed_login_alerts_escalated_is_policy_rag_only_no_visible_mitre() -> None:
    response = _chat("When should repeated failed login alerts be escalated?")
    intent = response.query_to_intent["intent_classification"]
    assert intent["intent_family"] in {"policy_knowledge", "sop_or_playbook"}
    assert response.evidence_plan["answer_mode"] == "rag_only"
    assert response.route_adjudication["final_route"] == "knowledge_recall"
    assert response.candidate_spl is None
    assert response.execution is not None
    assert response.execution.execution_intent == "none"
    assert response.mitre_mappings == []
    assert response.mitre_decision is not None
    assert response.mitre_decision["answer_visible"] is False
