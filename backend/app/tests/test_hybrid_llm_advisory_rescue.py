"""LLM co-signs hybrid advisory only; never overrides command/unsafe spines."""

from __future__ import annotations

from app.chat.llm_intent_advisor import intent_advisor_consumable
from app.chat.query_signals import extract_query_signals
from app.routing.route_adjudication import adjudicate_route, hybrid_llm_advisory_rescue


def test_hybrid_rescue_promotes_knowledge_to_guided_when_llm_cosigns() -> None:
    signals = {
        "hybrid_advisory_process_aware_ot": True,
        "command_mode_active": False,
        "explicit_run_spl": False,
        "block_or_contain": False,
    }
    route, authority, reason = hybrid_llm_advisory_rescue(
        deterministic_route="knowledge_recall",
        signals=signals,
        llm_suggested_route="guided_investigation",
        match_path="out_of_registry",
    )
    assert route == "guided_investigation"
    assert authority == "hybrid_llm_advisory_rescue"
    assert "co-signed" in reason


def test_hybrid_rescue_blocked_by_command_mode() -> None:
    signals = extract_query_signals(
        "Here is SPL: search index=pgcil_soc earliest=-1h | stats count. Validate and optimize it."
    )
    assert signals["command_mode_active"] is True
    route, authority, blocked = hybrid_llm_advisory_rescue(
        deterministic_route="knowledge_recall",
        signals=signals,
        llm_suggested_route="guided_investigation",
        match_path="out_of_registry",
    )
    assert route == "knowledge_recall"
    assert authority is None
    assert blocked == "llm_hybrid_rescue_blocked_command_mode"


def test_hybrid_rescue_blocked_by_explicit_run_spl() -> None:
    signals = extract_query_signals("Run the SPL and give me results.")
    route, authority, blocked = hybrid_llm_advisory_rescue(
        deterministic_route="spl_generation",
        signals=signals,
        llm_suggested_route="guided_investigation",
        match_path="out_of_registry",
    )
    assert route == "spl_generation"
    assert authority is None
    assert blocked == "llm_hybrid_rescue_blocked_command_mode"


def test_hybrid_rescue_blocked_by_unsafe_enforcement() -> None:
    signals = {
        "block_or_contain": True,
        "containment_decision_support": False,
        "hybrid_advisory_source_health": True,
        "command_mode_active": False,
        "explicit_run_spl": False,
    }
    route, authority, blocked = hybrid_llm_advisory_rescue(
        deterministic_route="knowledge_recall",
        signals=signals,
        llm_suggested_route="guided_investigation",
        match_path="out_of_registry",
    )
    assert route == "knowledge_recall"
    assert authority is None
    assert blocked == "llm_hybrid_rescue_blocked_unsafe"


def test_hybrid_rescue_blocked_on_catalogue_match_path() -> None:
    route, authority, blocked = hybrid_llm_advisory_rescue(
        deterministic_route="knowledge_recall",
        signals={"hybrid_advisory_source_health": True},
        llm_suggested_route="guided_investigation",
        match_path="exact_105_question",
    )
    assert route == "knowledge_recall"
    assert authority is None
    assert blocked == "llm_hybrid_rescue_blocked_catalogue_path"


def _minimal_intent(**overrides: object) -> dict:
    base = {
        "intent_family": "knowledge_only",
        "primary_intent": "knowledge_recall",
        "query_type": "ask_for_explanation",
        "answer_goal": ["clarification"],
        "confidence": 0.4,
        "confidence_band": "low",
        "requires_clarification": False,
        "requires_hil": False,
        "action_mode": "recommend_only",
        "reason": "test",
    }
    base.update(overrides)
    return base


def test_adjudicate_route_applies_hybrid_llm_rescue() -> None:
    result = adjudicate_route(
        deterministic_route="knowledge_recall",
        llm_advisory={"skill": "guided_investigation"},
        evidence_plan=None,
        intent_classification=_minimal_intent(),
        query_to_intent={
            "query_signals": {
                "hybrid_advisory_source_health": True,
                "command_mode_active": False,
                "explicit_run_spl": False,
                "block_or_contain": False,
            },
            "candidate_mappings": {"match_path": "out_of_registry"},
        },
    )
    assert result.final_route == "guided_investigation"
    assert result.authority_source == "hybrid_llm_advisory_rescue"


def test_adjudicate_route_command_mode_ignores_llm_guided_suggestion() -> None:
    result = adjudicate_route(
        deterministic_route="spl_generation",
        llm_advisory={"skill": "guided_investigation"},
        evidence_plan=None,
        intent_classification=_minimal_intent(
            intent_family="spl_generation_only",
            primary_intent="spl_generation",
            query_type="ask_for_next_action",
            answer_goal=["spl_artifact"],
            confidence=0.9,
            confidence_band="high",
        ),
        query_to_intent={
            "query_signals": {
                "command_mode_active": True,
                "command_shaped_spl": True,
                "explicit_run_spl": False,
                "hybrid_advisory_process_aware_ot": False,
                "block_or_contain": False,
            },
            "candidate_mappings": {"match_path": "out_of_registry"},
        },
    )
    assert result.final_route == "spl_generation"
    assert result.authority_source != "hybrid_llm_advisory_rescue"


def test_intent_advisor_skips_command_mode_window() -> None:
    ok, reason = intent_advisor_consumable(
        match_path="out_of_registry",
        signals={"command_mode_active": True, "explicit_run_spl": False},
        query="validate this SPL",
    )
    assert ok is False
    assert reason == "intent_advisory_command_mode"


def test_intent_advisor_consumes_hybrid_window() -> None:
    ok, reason = intent_advisor_consumable(
        match_path="use_case_catalog",
        signals={"hybrid_advisory_source_health": True, "command_mode_active": False},
        query="Which OT log sources have stopped sending events to Splunk?",
    )
    assert ok is True
    assert reason is None
