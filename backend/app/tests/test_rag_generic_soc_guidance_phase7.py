from __future__ import annotations

from typing import Any

from app.api.routes_chat import chat
from app.config import settings
from app.schemas.requests import ChatRequest
from app.use_cases.content_enrichment import get_runtime_curated_enrichment


def _enable_phase7(monkeypatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_planner_path_selection_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_planner_mitre_branch_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_spl_template_governance_enabled", True)
    monkeypatch.setattr(settings, "soc_kb_retrieval_enabled", True)


def test_sop_playbook_question_goes_rag_only_and_skips_spl_mcp(monkeypatch) -> None:
    _enable_phase7(monkeypatch)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve_collected)

    response = chat(ChatRequest(message="Show SOP for failed login investigation"))

    assert response.evidence_plan["answer_mode"] == "rag_only"
    assert response.planning_decision["path_type"] == "rag_only"
    assert response.evidence_plan["spl_allowed"] is False
    assert response.evidence_plan["mcp_allowed"] is False
    assert response.candidate_spl is None
    assert response.spl_validation is None
    assert response.execution.status == "skipped"
    assert response.planning_decision["blocked_tools"][:2] == ["spl", "mcp"]


def test_generic_soc_question_uses_guidance_path_without_fake_use_case(monkeypatch) -> None:
    _enable_phase7(monkeypatch)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve_collected)

    response = chat(ChatRequest(message="What are general SOC triage steps for a suspicious alert?"))

    assert response.planning_decision["path_type"] == "generic_soc_guidance"
    assert response.selected_use_case is None
    assert response.planning_decision["use_case_id"] is None
    assert response.candidate_spl is None
    assert response.spl_validation is None
    assert response.execution.status == "skipped"
    assert not response.mitre_mappings


def test_kb_no_match_returns_safe_fallback_not_hallucinated_sop(monkeypatch) -> None:
    _enable_phase7(monkeypatch)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve_no_match)

    response = chat(ChatRequest(message="What is the runbook for printer toner inventory?"))

    assert "No governed KB/SOP match was found" in response.message
    assert response.context_sufficiency.status == "insufficient_evidence"
    assert "rag_no_match" in response.context_sufficiency.reasons
    assert response.analyst_response is None
    assert response.candidate_spl is None
    assert response.spl_validation is None
    assert response.execution.status == "skipped"


def test_mitre_only_without_alert_context_requests_context(monkeypatch) -> None:
    _enable_phase7(monkeypatch)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve_no_match)

    response = chat(ChatRequest(message="Map this to MITRE"))

    assert response.planning_decision["path_type"] == "mitre_context_required"
    assert response.human_review.required is True
    assert response.human_review.review_type == "intent_clarification"
    assert "alert context" in response.message.lower()
    assert response.candidate_spl is None
    assert response.spl_validation is None
    assert not response.mitre_mappings


def test_enrichment_only_pilot_does_not_become_runtime_active(monkeypatch) -> None:
    _enable_phase7(monkeypatch)

    assert get_runtime_curated_enrichment("email_phishing_header_review") is None


def test_pure_sop_question_does_not_select_spl_branch(monkeypatch) -> None:
    _enable_phase7(monkeypatch)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve_collected)

    response = chat(ChatRequest(message="What is the playbook for brute force?"))

    assert response.planning_decision["branches"] == ["rag"]
    assert "spl" in response.planning_decision["blocked_tools"]
    assert response.candidate_spl is None
    assert response.spl_validation is None


def _fake_retrieve_collected(**kwargs: Any) -> dict[str, Any]:
    return {
        "retrieval_status": "retrieved",
        "retrieved_entries": [
            {
                "entry_id": "kb-sop-auth-1",
                "doc_id": "coe-auth-sop-v1",
                "document_type": "sop",
                "title": "Failed login investigation SOP",
                "source_excerpt": "Review scope, source distribution, affected users, and escalation criteria.",
                "citation": "COE Sample Auth Investigation SOP v1.0 AUTH-001",
                "approval_status": "coe_reviewed",
                "validation_status": "runtime_eligible",
                "recommended_actions": ["review_scope", "check_privileged_accounts"],
            }
        ],
        "warnings": [],
    }


def _fake_retrieve_no_match(**kwargs: Any) -> dict[str, Any]:
    return {
        "retrieval_status": "no_match",
        "retrieved_entries": [],
        "warnings": ["no_approved_soc_kb_match"],
    }
