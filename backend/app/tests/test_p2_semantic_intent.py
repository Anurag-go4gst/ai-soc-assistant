from __future__ import annotations

from typing import Any

import pytest

from app.api.routes_chat import chat
from app.query_understanding.models import OutputTemplate, QueryEntities, QueryUnderstandingResult, RequestedOutputType
from app.query_understanding.semantic_intent import build_semantic_intent_envelope
from app.routing.route_authority_allowlist import COV_Q046_PILOT_COVERAGE_ID
from app.routing.route_authority_gate import FALLBACK_COVERAGE_ID_NOT_ALLOWLISTED
from app.schemas.requests import ChatRequest
from app.tests.test_p2_known_path_authority import _cov_q046_candidate_with_slots, _enable_pilot_authority
from app.tests.test_route_plan_stage3k_r2 import _patch_common_chat_dependencies


def _understanding(
    *,
    query: str = "Find top failed Okta logins.",
    output_type: RequestedOutputType = RequestedOutputType.INVESTIGATION,
    clarification_needed: bool = False,
) -> QueryUnderstandingResult:
    return QueryUnderstandingResult(
        raw_query=query,
        normalized_query=query.lower(),
        primary_intent="investigate",
        requested_output_type=output_type,
        output_template=OutputTemplate.INVESTIGATION_ANSWER,
        entities=QueryEntities(),
        confidence=0.85,
        clarification_needed=clarification_needed,
        clarification_question="Share the alert context." if clarification_needed else None,
    )


def _enable_semantic_llm_shadow(monkeypatch: pytest.MonkeyPatch, advisory: dict[str, Any]) -> None:
    monkeypatch.setattr(
        "app.api.routes_chat.route_skill",
        lambda query, trace_id: {
            "skill": "attack_discovery",
            "tool_plan": ["route_only", "attack_discovery"],
            "confidence": 0.91,
            "comparison": {"match": True, "skill_match": True, "tool_plan_match": True},
            "selected_by": "llm_assisted_semantic_normalized",
            "llm_shadow": {"skill": "attack_discovery"},
            "llm_semantic_advisory": advisory,
            "route_decision": {"disagreements": [{"field": "primary_intent"}]},
        },
    )


def test_allowlisted_known_path_includes_semantic_intent(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_pilot_authority(monkeypatch)
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")
    monkeypatch.setattr("app.api.routes_chat._route_plan_shadow_candidate", lambda query: _cov_q046_candidate_with_slots())

    response = chat(ChatRequest(message="Find top 10 users with failed Okta logins in the last 24 hours."))

    assert response.semantic_intent is not None
    assert response.semantic_intent["path_type"] == "known_registry"
    assert response.semantic_intent["selected_path_authority"] == "deterministic_registry"
    assert response.semantic_intent["primary_operation_candidate"] == "aggregate_and_rank"
    assert response.semantic_intent["coverage_id_candidate"] == COV_Q046_PILOT_COVERAGE_ID
    assert response.semantic_intent["mcp_needed"] is True
    assert response.semantic_intent["final_route_unchanged"] is True
    assert response.execution.executed_spl is None


def test_non_allowlisted_known_path_records_authority_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_pilot_authority(monkeypatch)
    monkeypatch.setattr("app.config.settings.route_authority_operation_coverage_allowlist", "")
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")
    monkeypatch.setattr("app.api.routes_chat._route_plan_shadow_candidate", lambda query: _cov_q046_candidate_with_slots())

    response = chat(ChatRequest(message="Find top 10 users with failed Okta logins in the last 24 hours."))

    assert response.semantic_intent is not None
    assert response.semantic_intent["path_type"] == "known_registry"
    assert response.semantic_intent["authority_decision"] == "shadow_only"
    assert f"authority_fallback:{FALLBACK_COVERAGE_ID_NOT_ALLOWLISTED}" in response.semantic_intent["warnings"]
    assert response.execution.executed_spl is None


def test_sop_query_is_knowledge_only_and_rag_not_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_common_chat_dependencies(monkeypatch, skill="knowledge_recall")

    response = chat(ChatRequest(message="What is the SOP for excessive failed login triage?"))

    assert response.semantic_intent is not None
    assert response.semantic_intent["path_type"] == "knowledge_only"
    assert response.semantic_intent["rag_needed"] is True
    assert response.semantic_intent["mcp_needed"] is False


def test_mitre_query_without_alert_context_is_clarification(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_common_chat_dependencies(monkeypatch, skill="knowledge_recall")

    response = chat(ChatRequest(message="Map this to MITRE ATT&CK"))

    assert response.semantic_intent is not None
    assert response.semantic_intent["path_type"] == "clarification"
    assert response.semantic_intent["mitre_candidate_needed"] is True
    assert response.human_review.required is True
    assert response.human_review.review_type == "intent_clarification"
    assert response.execution.executed_spl is None


def test_llm_semantic_shadow_is_advisory_and_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_semantic_llm_shadow(
        monkeypatch,
        {
            "llm_primary_intent_candidate": "investigate_failed_logins",
            "llm_selected_skill_candidate": "aggregate_and_rank",
            "llm_requested_output_type_candidate": "investigation",
            "llm_evidence_needs": [{"source_type": "authentication_logs"}],
            "warnings": ["llm_candidate_advisory_only"],
        },
    )

    response = chat(ChatRequest(message="Find failed login users."))

    assert response.semantic_intent is not None
    assert response.semantic_intent["llm_semantic_intent_called"] is True
    assert response.semantic_intent["llm_primary_operation_candidate"] == "aggregate_and_rank"
    assert response.semantic_intent["llm_legacy_intent_hint"] == "investigate_failed_logins"
    assert response.semantic_intent["selected_path_authority"] == "llm_advisory_normalized"
    assert response.semantic_intent["semantic_intent_disagreements"] == [{"field": "primary_intent"}]
    assert response.semantic_intent["final_route_unchanged"] is True
    assert response.execution.executed_spl is None


def test_known_compatible_ood_records_review_audit() -> None:
    envelope = build_semantic_intent_envelope(
        query_understanding=_understanding(),
        routed={"skill": "attack_discovery", "tool_plan": ["route_only", "attack_discovery"]},
        route_plan_shadow={},
        route_authority=None,
        primary_operation="aggregate_and_rank",
        coverage_id=None,
    )

    assert envelope["path_type"] == "known_compatible_ood"
    assert envelope["operation_provenance"] == "deterministic_known_compatible"
    assert envelope["audit_record"]["audit_required"] is True
    assert envelope["audit_record"]["route_status"] == "known_compatible_review"
    assert envelope["final_route_unchanged"] is True


def test_novel_ood_records_hil_audit() -> None:
    envelope = build_semantic_intent_envelope(
        query_understanding=_understanding(query="Create a new speculative threat hunt operation."),
        routed={"skill": "attack_discovery", "tool_plan": ["route_only", "attack_discovery"]},
        route_plan_shadow={},
        route_authority=None,
        primary_operation="invent_new_soc_operation",
        coverage_id=None,
    )

    assert envelope["path_type"] == "novel_ood"
    assert envelope["known_compatible"] is False
    assert envelope["audit_record"]["audit_required"] is True
    assert envelope["audit_record"]["promotion_candidate"] is True
    assert "novel_ood_requires_audit_hil" in envelope["warnings"]
