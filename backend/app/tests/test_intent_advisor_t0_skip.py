from __future__ import annotations

import pytest

from app.chat.contracts.llm_intent_advisory import LLMIntentAdvisory
from app.chat.pipeline import graph_node_query_to_intent
from app.config import settings
from app.query_understanding.parser import understand_query
from app.schemas.requests import ChatRequest


def test_weak_exact_105_turn_does_not_skip_intent_sidecar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    monkeypatch.setattr(
        "app.chat.pipeline.generate_llm_intent_advisory",
        lambda *_, **__: LLMIntentAdvisory(llm_called=True, dropped_reasons=["test_advisory_called"]),
    )

    query = "Which users have excessive failed logins?"
    qu = understand_query(query)
    assert qu.deterministic_match_path in {"exact_105_question", "exact_105_plus_use_case_catalog"}

    state = graph_node_query_to_intent(
        {
            "request": ChatRequest(message=query),
            "effective_query": query,
            "query_understanding": qu,
            "routed": {"skill": "attack_discovery"},
        }
    )

    advisory = state.get("llm_intent_advisory") or {}
    assert advisory.get("dropped_reasons") == ["test_advisory_called"]
    assert advisory.get("llm_called") is True


def test_authority_ready_exact_105_turn_skips_intent_sidecar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    monkeypatch.setattr(
        "app.chat.pipeline._preplan_promotion_lifecycle_for_llm_skip",
        lambda *_: {"effective_promotion_status": "authority_ready"},
    )
    monkeypatch.setattr(
        "app.chat.pipeline.generate_llm_intent_advisory",
        lambda *_, **__: pytest.fail("authority-ready T0 must skip intent sidecar"),
    )

    query = "Which users have excessive failed logins?"
    qu = understand_query(query)

    state = graph_node_query_to_intent(
        {
            "request": ChatRequest(message=query),
            "effective_query": query,
            "query_understanding": qu,
            "routed": {"skill": "attack_discovery"},
        }
    )

    advisory = state.get("llm_intent_advisory") or {}
    assert advisory.get("dropped_reasons") == ["deterministic_exact_match_t0"]
    assert advisory.get("llm_called") is False


def test_high_confidence_semantic_105_turn_does_not_skip_without_promotion_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    monkeypatch.setattr(
        "app.chat.pipeline.generate_llm_intent_advisory",
        lambda *_, **__: LLMIntentAdvisory(llm_called=True, dropped_reasons=["test_advisory_called"]),
    )

    query = "List all DNS requests during the observation window"
    qu = understand_query(query)
    assert qu.deterministic_match_path == "semantic_105_question"
    assert qu.mapped_question_ref == "cisco.perim.010"
    assert qu.question_registry_match_score >= 0.95

    state = graph_node_query_to_intent(
        {
            "request": ChatRequest(message=query),
            "effective_query": query,
            "query_understanding": qu,
            "routed": {"skill": "spl_generation"},
        }
    )

    advisory = state.get("llm_intent_advisory") or {}
    assert advisory.get("dropped_reasons") == ["test_advisory_called"]
    assert advisory.get("llm_called") is True
