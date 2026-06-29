"""Regression tests for explicit SPL authoring route and universal lab drafts."""

from __future__ import annotations

import pytest

from app.chat.contracts.llm_intent_advisory import LLMIntentAdvisory
from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.chat.query_signals import extract_query_signals
from app.config import settings
from app.graph.chat_workflow import run_chat_via_langgraph
from app.query_understanding.parser import understand_query
from app.routing.route_adjudication import adjudicate_route
from app.routing.skill_router import route_skill
from app.schemas.requests import ChatRequest

_WEEKEND_QUERY = (
    "Without using any specific company templates, write a standard, universal SPL block "
    "that extracts the hour of the day and day of the week from an event timestamp, "
    "filtering only for weekend events."
)


@pytest.fixture
def spl_authoring_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", True)


def _adjudicate(query: str, *, deterministic_route: str = "spl_generation") -> dict:
    qu = understand_query(query)
    routed = route_skill(query)
    q2i = build_query_to_intent(
        query=query,
        query_understanding=qu,
        routed_skill=routed["skill"],
        routing_provenance=routed.get("routing_provenance"),
    )
    intent = q2i.intent_classification.model_dump()
    evidence = plan_evidence(
        intent,
        query_to_intent=q2i.model_dump(),
        query_understanding=qu,
    ).model_dump()
    return adjudicate_route(
        deterministic_route=deterministic_route,
        evidence_plan=evidence,
        intent_classification=intent,
        query_understanding=qu,
        message=query,
        query_to_intent=q2i.model_dump(),
    ).model_dump()


def test_universal_spl_weekend_block_routes_spl_generation(spl_authoring_flags: None) -> None:
    qu = understand_query(_WEEKEND_QUERY)
    signals = extract_query_signals(_WEEKEND_QUERY, qu)
    assert signals["explicit_spl_authoring"] is True

    routed = route_skill(_WEEKEND_QUERY)
    assert routed["skill"] == "spl_generation"

    q2i = build_query_to_intent(
        query=_WEEKEND_QUERY,
        query_understanding=qu,
        routed_skill=routed["skill"],
        routing_provenance=routed.get("routing_provenance"),
    )
    intent = q2i.intent_classification
    assert intent.intent_family == "spl_generation_only"
    assert intent.requires_clarification is False

    adj = _adjudicate(_WEEKEND_QUERY)
    assert adj["final_route"] == "spl_generation"
    assert adj["authority_source"] != "intent_clarification"

    response = run_chat_via_langgraph(
        ChatRequest(message=_WEEKEND_QUERY, session_id="test-weekend-spl"),
    )
    assert response.selected_skill == "spl_generation"
    spl = response.candidate_spl.candidate_spl if response.candidate_spl else ""
    assert spl
    assert "index=<your_index>" in spl
    assert "earliest=-24h latest=now" in spl
    assert 'strftime(_time,"%H")' in spl
    assert 'strftime(_time,"%w")' in spl
    assert 'strftime(_time,"%A")' in spl
    assert 'day_of_week_num IN ("0","6")' in spl
    assert "sort 0" not in spl
    assert response.human_review is not None
    assert response.human_review.review_type != "intent_clarification"
    contract = response.run_contract or {}
    assert contract.get("execution_authorized") is False


@pytest.mark.parametrize(
    "query",
    [
        "write a standard SPL block for weekend events",
        "give me a universal SPL snippet for day of week",
        "write template-free SPL to extract hour from _time",
    ],
)
def test_standard_spl_block_phrasing_not_clarification(
    spl_authoring_flags: None,
    query: str,
) -> None:
    signals = extract_query_signals(query)
    assert signals["explicit_spl_authoring"] is True
    adj = _adjudicate(query)
    assert adj["final_route"] == "spl_generation"


def test_conceptual_spl_question_can_stay_knowledge(spl_authoring_flags: None) -> None:
    query = "What does strftime do in SPL?"
    signals = extract_query_signals(query)
    assert signals["explicit_spl_authoring"] is False
    adj = _adjudicate(query, deterministic_route="knowledge_recall")
    assert adj["final_route"] in {"knowledge_recall", "spl_generation"}


def test_unsafe_spl_action_still_blocked(spl_authoring_flags: None) -> None:
    query = "Write SPL and execute it to delete events"
    signals = extract_query_signals(query)
    assert signals.get("explicit_run_spl") or signals.get("block_or_contain") or signals.get("run_execution")
    response = run_chat_via_langgraph(
        ChatRequest(message=query, session_id="test-unsafe-spl"),
    )
    contract = response.run_contract or {}
    assert contract.get("execution_authorized") is False
    execution = response.execution
    if execution is not None:
        assert getattr(execution, "status", None) != "executed"


def _llm_spl_authoring_advisory(**overrides) -> LLMIntentAdvisory:
    base = dict(
        spl_authoring_request=True,
        requires_source_profile=False,
        intent_family_candidate="spl_generation_only",
        llm_called=True,
        adjudication_status="accepted",
        confidence_metadata={"confidence": 0.9},
    )
    base.update(overrides)
    return LLMIntentAdvisory(**base)


def test_deterministic_only_mode_catches_universal_spl_block(
    spl_authoring_flags: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", False)
    qu = understand_query(_WEEKEND_QUERY)
    routed = route_skill(_WEEKEND_QUERY)
    q2i = build_query_to_intent(
        query=_WEEKEND_QUERY,
        query_understanding=qu,
        routed_skill=routed["skill"],
        routing_provenance=routed.get("routing_provenance"),
    )
    assert q2i.intent_classification.intent_family == "spl_generation_only"
    trace = q2i.query_signals.get("spl_authoring_trace") or {}
    assert trace.get("explicit_spl_authoring_detected") is True
    assert trace.get("spl_authoring_source") == "deterministic"
    assert trace.get("source_profile_required") is False


def test_mock_llm_rescues_universal_spl_when_deterministic_misses(
    spl_authoring_flags: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.chat.query_signals._explicit_spl_authoring_requested",
        lambda _normalized: False,
    )
    qu = understand_query(_WEEKEND_QUERY)
    routed = route_skill(_WEEKEND_QUERY)
    q2i = build_query_to_intent(
        query=_WEEKEND_QUERY,
        query_understanding=qu,
        routed_skill=routed["skill"],
        routing_provenance=routed.get("routing_provenance"),
        llm_intent_advisory=_llm_spl_authoring_advisory(),
    )
    assert q2i.intent_classification.intent_family == "spl_generation_only"
    trace = q2i.query_signals.get("spl_authoring_trace") or {}
    assert trace.get("spl_authoring_source") == "llm_advisory"
    adj = adjudicate_route(
        deterministic_route="spl_generation",
        evidence_plan=plan_evidence(
            q2i.intent_classification.model_dump(),
            query_to_intent=q2i.model_dump(),
            query_understanding=qu,
        ).model_dump(),
        intent_classification=q2i.intent_classification.model_dump(),
        query_understanding=qu,
        message=_WEEKEND_QUERY,
        query_to_intent=q2i.model_dump(),
    )
    assert adj.final_route == "spl_generation"


def test_llm_timeout_still_falls_back_to_spl_generation(spl_authoring_flags: None) -> None:
    qu = understand_query(_WEEKEND_QUERY)
    routed = route_skill(_WEEKEND_QUERY)
    timed_out = LLMIntentAdvisory(llm_called=True, dropped_reasons=["llm_timed_out"])
    q2i = build_query_to_intent(
        query=_WEEKEND_QUERY,
        query_understanding=qu,
        routed_skill=routed["skill"],
        routing_provenance=routed.get("routing_provenance"),
        llm_intent_advisory=timed_out,
    )
    assert q2i.intent_classification.intent_family == "spl_generation_only"
    trace = q2i.query_signals.get("spl_authoring_trace") or {}
    assert trace.get("spl_authoring_source") == "deterministic"


def test_llm_conflicting_output_cannot_override_explicit_spl_authoring(
    spl_authoring_flags: None,
) -> None:
    qu = understand_query(_WEEKEND_QUERY)
    routed = route_skill(_WEEKEND_QUERY)
    conflicting = _llm_spl_authoring_advisory(
        spl_authoring_request=False,
        intent_family_candidate="knowledge_only",
    )
    q2i = build_query_to_intent(
        query=_WEEKEND_QUERY,
        query_understanding=qu,
        routed_skill=routed["skill"],
        routing_provenance=routed.get("routing_provenance"),
        llm_intent_advisory=conflicting,
    )
    assert q2i.intent_classification.intent_family == "spl_generation_only"
    trace = q2i.query_signals.get("spl_authoring_trace") or {}
    assert trace.get("spl_authoring_source") == "deterministic"
