"""Track B: summary renderer + substantive card preservation."""

from __future__ import annotations

import pytest

from app.chat.analyst_response_builder import build_alert_summary_message
from app.chat.rag_answer_surfacing import (
    ensure_analyst_card_for_substantive_message,
    is_substantive_guidance_message,
)
from app.chat.answer_shape_router import build_shaped_guidance

SUMMARY_QUERY = (
    "Summarize for shift handoff: failed PLC admin login burst, one success, "
    "then relay logic export in 22 minutes."
)


def test_alert_summary_message_has_required_sections() -> None:
    body = build_alert_summary_message(user_query=SUMMARY_QUERY)
    lowered = body.lower()
    assert "situation" in lowered
    assert "confidence" in lowered
    assert "recommended actions" in lowered
    assert "unknowns" in lowered
    assert len(body) >= 200
    assert "failed plc admin login" in lowered


def test_substantive_shaped_guidance_rebuilds_card() -> None:
    shaped = build_shaped_guidance(
        "A vendor pushed a firmware update signed with an unexpected code-signing certificate "
        "to 40 RTUs overnight. How do we determine whether this is a legitimate vendor key "
        "rotation or a supply-chain compromise?",
        match_path=None,
    )
    assert is_substantive_guidance_message(shaped)
    card = ensure_analyst_card_for_substantive_message(
        shaped,
        None,
        selected_skill="guided_investigation",
    )
    assert card is not None
    assert card.direct_answer_summary
    blob = (card.direct_answer_summary or "").lower()
    assert "hypotheses" in blob or "vendor" in blob or "investigation" in blob


def test_alert_summary_live_pipeline_returns_structured_message(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.chat.pipeline import build_live_chat_response
    from app.config import settings
    from app.schemas.requests import ChatRequest

    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_t2_answer_shape_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_t2_rag_surfacing_enabled", True)
    response = build_live_chat_response(ChatRequest(message=SUMMARY_QUERY))
    assert response.analyst_response is not None
    blob = (response.message or "") + (response.analyst_response.direct_answer_summary or "")
    assert "situation" in blob.lower()
    assert "confidence" in blob.lower()
