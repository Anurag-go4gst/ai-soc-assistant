from __future__ import annotations

import time

from app.chat.intent_classifier import build_query_to_intent
from app.chat.llm_intent_advisor import generate_llm_intent_advisory
from app.config import settings
from app.query_understanding.parser import understand_query


def test_llm_intent_advisor_skipped_by_default(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", False)
    advisory = generate_llm_intent_advisory("Which users have excessive failed logins?")

    assert advisory.llm_called is False
    assert advisory.dropped_reasons == ["llm_intent_advisor_disabled"]


def test_llm_intent_advisor_invalid_json_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "mock")

    advisory = generate_llm_intent_advisory(
        "Which users have excessive failed logins?",
        llm_raw_output_provider=lambda: "not json",
    )

    assert advisory.llm_called is True
    assert advisory.adjudication_status == "skipped"
    assert "json_extraction_failed" in advisory.dropped_reasons


def test_llm_intent_advisor_adjudication_corrects_registry_conflict(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "mock")
    query = "Which users have excessive failed logins?"
    qu = understand_query(query)
    advisory = generate_llm_intent_advisory(
        query,
        query_understanding=qu,
        llm_raw_output_provider=lambda: """
        {
          "intent_family_candidate": "live_investigation",
          "path_type_candidate": "spl_review",
          "question_ref_candidate": "q0.q999",
          "use_case_id_candidate": "unknown_use_case",
          "paraphrase_detected": true,
          "confidence_metadata": {"confidence": 0.91}
        }
        """,
    )
    result = build_query_to_intent(
        query=query,
        query_understanding=qu,
        routed_skill="attack_discovery",
        llm_intent_advisory=advisory,
    )

    assert result.llm_intent_advisory is not None
    assert result.llm_intent_assist_status == "corrected"
    assert result.llm_intent_advisory.adjudication_reason == "deterministic_question_ref_wins"
    assert result.llm_intent_advisory.question_ref_candidate == qu.mapped_question_ref


def test_llm_intent_advisor_timeout_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "mock")

    def slow_provider() -> str:
        time.sleep(2)
        return "{}"

    advisory = generate_llm_intent_advisory("query", llm_raw_output_provider=slow_provider, timeout_seconds=1.5)

    assert advisory.llm_called is True
    assert "llm_timed_out" in advisory.dropped_reasons

