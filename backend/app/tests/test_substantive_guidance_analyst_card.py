"""Regression: shaped knowledge/regulatory guidance must survive RAG-miss card nulling."""

from __future__ import annotations

from typing import Any

import pytest

from app.api.routes_chat import chat
from app.chat.answer_shape_router import build_shaped_guidance
from app.chat.pipeline import build_live_chat_response
from app.chat.rag_answer_surfacing import (
    _RAG_STUB_PHRASES,
    is_rag_stub_message,
    is_substantive_guidance_message,
)
from app.config import settings
from app.schemas.requests import ChatRequest

CERT_IN_QUERY = (
    "What is our CERT-In 6-hour reporting obligation for a suspected OT security incident?"
)
FIRMWARE_QUERY = (
    "A vendor pushed a firmware update signed with an unexpected code-signing certificate "
    "to 40 RTUs overnight. How do we determine whether this is a legitimate vendor key "
    "rotation or a supply-chain compromise?"
)
KB_NO_MATCH_QUERY = "What is the runbook for printer toner inventory?"


def _fake_retrieve_no_match(**kwargs: Any) -> dict[str, Any]:
    return {
        "retrieval_status": "no_match",
        "retrieved_entries": [],
        "warnings": ["no_approved_soc_kb_match"],
    }


def _enable_phase7(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_planner_path_selection_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_planner_mitre_branch_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_spl_template_governance_enabled", True)
    monkeypatch.setattr(settings, "soc_kb_retrieval_enabled", True)


@pytest.fixture(autouse=True)
def _enable_t2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t2_answer_shape_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_t2_rag_surfacing_enabled", True)
    _enable_phase7(monkeypatch)


def test_cert_in_shaped_body_is_not_classified_as_rag_stub() -> None:
    shaped = build_shaped_guidance(CERT_IN_QUERY, match_path=None)
    assert len(shaped) >= 80
    assert is_substantive_guidance_message(shaped) is True
    assert is_rag_stub_message(shaped) is False
    for phrase in _RAG_STUB_PHRASES:
        assert phrase not in shaped.lower(), f"false-positive stub phrase: {phrase!r}"


def test_cert_in_regulatory_keeps_analyst_card_on_rag_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve_no_match)

    response = chat(ChatRequest(message=CERT_IN_QUERY))

    assert response.planning_decision.get("path_type") == "rag_only"
    assert is_substantive_guidance_message(response.message)
    assert "Regulatory" in (response.message or "") or "CERT-In" in (response.message or "")
    assert response.analyst_response is not None
    blob = (response.message or "") + (response.analyst_response.direct_answer_summary or "")
    assert "CERT-In" in blob or "reporting" in blob.lower()


def test_kb_no_match_stub_still_nulls_analyst_card(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve_no_match)

    response = chat(ChatRequest(message=KB_NO_MATCH_QUERY))

    assert "No governed KB/SOP match was found" in (response.message or "")
    assert is_rag_stub_message(response.message)
    assert is_substantive_guidance_message(response.message) is False
    assert response.analyst_response is None


@pytest.mark.parametrize(
    "message",
    [
        # Routing-only stub with punctuation-joiner variants (regex must catch all).
        "Routing complete. SPL is not required for this knowledge-only reporting question here.",
        "Routing complete — SPL is not required for this knowledge-only reporting question here.",
        "Routing complete: SPL is not required for this knowledge-only reporting question here.",
        # Generic deflection that clears the 80-char floor but carries no guidance.
        "I was unable to find a specific governed answer for your request right now; please retry.",
        "Generic SOC guidance path selected — no specific shaped guidance is available for this turn.",
    ],
)
def test_non_substantive_messages_are_nulled(message: str) -> None:
    assert len(message) >= 80  # would clear the length floor on its own
    assert is_substantive_guidance_message(message) is False


def test_firmware_supply_chain_still_has_analyst_card(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve_no_match)

    response = build_live_chat_response(ChatRequest(message=FIRMWARE_QUERY))

    assert response.analyst_response is not None
    blob = (response.message or "") + (response.analyst_response.direct_answer_summary or "")
    assert "supply-chain" in blob.lower() or "firmware" in blob.lower() or "code-signing" in blob.lower()
