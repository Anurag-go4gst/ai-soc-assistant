from __future__ import annotations

from typing import Any

import pytest

from app.chat.contracts.answer_contract import AnswerContract
from app.chat.intent_classifier import build_candidate_mappings, classify_intent
from app.chat.query_signals import extract_query_signals
from app.chat.rag_answer_surfacing import (
    apply_rag_answer_surfacing,
    build_rag_knowledge_message,
    is_rag_stub_message,
)
from app.config import settings
from app.schemas.responses import AnalystResponseEnvelope


PK003_QUERY = (
    "We confirmed unauthorized access to a substation HMI. Do we have to report this to "
    "CERT-In or under the CEA cyber security guidelines, and within what timeline?"
)

PI2_SOURCE_EVIDENCE: list[dict[str, Any]] = [
    {
        "source_type": "rag",
        "collection_status": "collected",
        "evidence_id": "ev-rag-cert",
        "preview_rows": [
            {
                "doc_title": "CERT-In OT Incident Reporting Playbook",
                "document_type": "sop",
                "source_excerpt": "Report OT incidents affecting grid operations to CERT-In when thresholds are met.",
                "citation": "SOC-SOP-CERT-001#reporting",
                "recommended_actions": [
                    "Confirm whether the event meets CERT-In / sector reporting threshold.",
                    "Collect scope, affected systems, timeline, and containment status.",
                    "Engage legal/compliance and CISO before external notification.",
                ],
            }
        ],
    }
]


@pytest.fixture(autouse=True)
def _reset_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t2_rag_surfacing_enabled", True)


def test_regulatory_signal_classifies_pk003_as_policy_knowledge() -> None:
    signals = extract_query_signals(PK003_QUERY)
    assert signals.get("regulatory_reporting") is True
    intent = classify_intent(
        query=PK003_QUERY,
        signals=signals,
        candidate_mappings=build_candidate_mappings(None),
    )
    assert intent.intent_family == "policy_knowledge"
    assert intent.primary_intent == "knowledge_recall"
    assert "policy_citation" in intent.answer_goal
    assert "procedural_steps" in intent.answer_goal


def test_regulatory_branch_requires_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t2_rag_surfacing_enabled", False)
    signals = extract_query_signals(PK003_QUERY)
    intent = classify_intent(
        query=PK003_QUERY,
        signals=signals,
        candidate_mappings=build_candidate_mappings(None),
    )
    assert intent.intent_family != "policy_knowledge"


def test_rag_surfacing_replaces_stub_message_when_playbook_hits_exist() -> None:
    stub = "Governed knowledge path selected. SPL and MCP are skipped for this request."
    assert is_rag_stub_message(stub) is True
    contract = AnswerContract(
        intent_family="sop_or_playbook",
        answer_mode="rag_only",
        render_sections={"policy_citation": False, "procedural_steps": False},
        spl_present=False,
        spl_status="not_required",
    )
    playbook, sop_guidance, _ = __import__(
        "app.chat.analyst_response_builder", fromlist=["_playbook_from_rag"]
    )._playbook_from_rag(PI2_SOURCE_EVIDENCE)
    expected = build_rag_knowledge_message(playbook, sop_guidance, regulatory=True)
    message, updated_contract, updated_response, _ = apply_rag_answer_surfacing(
        message=stub,
        answer_contract=contract,
        analyst_response=AnalystResponseEnvelope(direct_answer_summary=stub),
        source_evidence=PI2_SOURCE_EVIDENCE,
        evidence_plan={"answer_mode": "rag_only"},
        context_sufficiency={"status": "knowledge_only_answer"},
        user_query=PK003_QUERY,
        human_review={"required": False, "review_type": "execution_approval"},
    )
    assert "SPL and MCP are skipped" not in message
    assert "CERT-In OT Incident Reporting Playbook" in message
    assert "Confirm whether the event meets CERT-In" in message
    assert updated_contract is not None
    assert updated_contract.render_sections.get("policy_citation") is True
    assert updated_contract.render_sections.get("procedural_steps") is True
    assert updated_response is not None
    assert "CERT-In OT Incident Reporting Playbook" in (updated_response.direct_answer_summary or "")
    assert "Disclaimer" in message


def test_knowledge_turn_clears_misleading_execution_approval_when_not_required() -> None:
    _, _, _, human_review = apply_rag_answer_surfacing(
        message="Governed knowledge path selected. SPL and MCP are skipped for this request.",
        answer_contract=AnswerContract(
            intent_family="policy_knowledge",
            answer_mode="rag_only",
            render_sections={},
            spl_present=False,
            spl_status="not_required",
        ),
        analyst_response=AnalystResponseEnvelope(direct_answer_summary="stub"),
        source_evidence=PI2_SOURCE_EVIDENCE,
        evidence_plan={"answer_mode": "rag_only"},
        context_sufficiency={"status": "knowledge_only_answer"},
        user_query=PK003_QUERY,
        human_review={"required": False, "review_type": "execution_approval"},
    )
    assert human_review is not None
    assert human_review.get("required") is False
    assert human_review.get("review_type") == "none"
    assert human_review.get("reason") == "knowledge_only_no_execution"


def test_knowledge_turn_without_hits_clears_execution_approval() -> None:
    _, _, _, human_review = apply_rag_answer_surfacing(
        message="No governed KB/SOP match was found for this request.",
        answer_contract=AnswerContract(
            intent_family="policy_knowledge",
            answer_mode="rag_only",
            render_sections={},
            spl_present=False,
            spl_status="not_required",
        ),
        analyst_response=None,
        source_evidence=[],
        evidence_plan={"answer_mode": "rag_only"},
        context_sufficiency={"status": "knowledge_only_answer"},
        user_query=PK003_QUERY,
        human_review={"required": False, "review_type": "execution_approval"},
    )
    assert human_review is not None
    assert human_review.get("review_type") == "none"
    assert human_review.get("reason") == "knowledge_only_no_execution"


def test_regulatory_no_hits_rebuilds_card_after_gate_null() -> None:
    """Regulatory surfacing must rebuild a card when finalize gate nulled analyst_response."""
    stub = "No governed KB/SOP match was found for this request. I did not generate SPL, call MCP, or infer MITRE evidence."
    contract = AnswerContract(
        intent_family="policy_knowledge",
        answer_mode="rag_only",
        render_sections={},
        spl_present=False,
        spl_status="not_required",
    )
    message, updated_contract, updated_response, _ = apply_rag_answer_surfacing(
        message=stub,
        answer_contract=contract,
        analyst_response=None,
        source_evidence=[],
        evidence_plan={"answer_mode": "rag_only"},
        context_sufficiency={"status": "knowledge_only_answer"},
        user_query=PK003_QUERY,
        human_review={"required": False, "review_type": "execution_approval"},
    )
    assert is_rag_stub_message(stub)
    assert "Regulatory" in message or "CERT-In" in message
    assert updated_response is not None
    summary = updated_response.direct_answer_summary or ""
    assert "CERT-In" in summary or "reporting" in summary.lower()
