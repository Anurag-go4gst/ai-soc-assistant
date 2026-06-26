"""Intent-advisor scheduling, signal floor, and deadline trace regressions."""

from __future__ import annotations

import json
import time

import pytest

from app.chat.contracts.llm_intent_advisory import LLMIntentAdvisory
from app.chat.intent_classifier import build_query_to_intent
from app.chat.pipeline import graph_node_query_to_intent
from app.chat.query_signals import extract_query_signals
from app.config import settings
from app.llm.intent_advisor_scheduler import (
    intent_advisor_hop_blocked,
    should_prioritize_intent_advisor,
)
from app.llm.turn_llm_budget import TurnLlmBudget, hop_reserve_seconds
from app.query_understanding.parser import understand_query
from app.routing.select_route_from_understanding import select_route_from_understanding
from app.schemas.requests import ChatRequest


WINDOWS_LOG_QUERY = (
    "Search wineventlog for Event ID 4624 for user jsmith in the last 24 hours"
)


def test_windows_log_query_signals_and_spl_intent_when_llm_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", False)

    signals = extract_query_signals(WINDOWS_LOG_QUERY)
    assert signals["explicit_log_search"] is True
    assert signals["spl_generation"] is True
    assert signals["live_data_request"] is True

    understanding = understand_query(WINDOWS_LOG_QUERY)
    route, _ = select_route_from_understanding(understanding, WINDOWS_LOG_QUERY)
    assert route["skill"] == "spl_generation"

    qi = build_query_to_intent(
        query=WINDOWS_LOG_QUERY,
        query_understanding=understanding,
        routed_skill=route["skill"],
    )
    assert qi.intent_classification.intent_family == "spl_generation_only"
    assert qi.intent_classification.primary_intent == "spl_generation"


def test_ambiguous_t2_signal_prioritizes_intent_advisor_for_multi_source_firewall_query() -> None:
    query = "Look across syslog and cisco_asa for permits from IT VLAN to OT DMZ on port 445."
    signals = extract_query_signals(query)

    assert signals["ambiguous_t2_query"] is True
    assert signals["meaningful_t2_entities"] is True
    assert should_prioritize_intent_advisor(
        query,
        None,
        {"match_path": "out_of_registry"},
        signals,
    ) is True


def test_meaningful_t2_entities_prioritize_intent_advisor_without_search_log_phrase() -> None:
    query = "Event ID 4624 for user jsmith from substation subnets over the last 7 days."
    signals = extract_query_signals(query)

    assert signals["meaningful_t2_entities"] is True
    assert should_prioritize_intent_advisor(
        query,
        None,
        {"match_path": "out_of_registry"},
        signals,
    ) is True


def test_t2_scheduler_does_not_prioritize_guidance_or_containment() -> None:
    guidance = "How should SOC investigate Event ID 4624 for user jsmith?"
    guidance_signals = extract_query_signals(guidance)
    assert should_prioritize_intent_advisor(
        guidance,
        None,
        {"match_path": "out_of_registry"},
        guidance_signals,
    ) is False

    containment = "Block user jsmith after Event ID 4624 from substation subnets."
    containment_signals = extract_query_signals(containment)
    assert should_prioritize_intent_advisor(
        containment,
        None,
        {"match_path": "out_of_registry"},
        containment_signals,
    ) is False


def test_mock_intent_advisory_entity_slots_for_windows_query(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")

    advisory_payload = {
        "intent_family_candidate": "spl_generation_only",
        "entity_slots_candidate": {
            "user": "jsmith",
            "event_id": "4624",
            "index": "wineventlog",
        },
        "entity_slot_confidence": {"user": 0.9, "event_id": 0.88, "index": 0.85},
    }

    def _fake_advisory(*_args, **_kwargs):
        return LLMIntentAdvisory(
            llm_called=True,
            provider_label="test-local",
            intent_family_candidate="spl_generation_only",
            entity_slots_candidate=advisory_payload["entity_slots_candidate"],
            entity_slot_confidence=advisory_payload["entity_slot_confidence"],
            adjudication_status="accepted",
        )

    monkeypatch.setattr("app.chat.pipeline.generate_llm_intent_advisory", _fake_advisory)
    # Pin provider-configured to False so the scheduling-trace assertion is
    # deterministic regardless of ambient LLM config / test ordering.
    monkeypatch.setattr("app.chat.pipeline.intent_advisor_provider_configured", lambda: False)

    understanding = understand_query(WINDOWS_LOG_QUERY)
    route, _ = select_route_from_understanding(understanding, WINDOWS_LOG_QUERY)

    state = graph_node_query_to_intent(
        {
            "request": ChatRequest(message=WINDOWS_LOG_QUERY),
            "effective_query": WINDOWS_LOG_QUERY,
            "query_understanding": understanding,
            "routed": {"skill": route["skill"]},
            "llm_turn_budget": TurnLlmBudget(deadline_seconds=75.0),
        }
    )

    advisory = state["llm_intent_advisory"]
    assert advisory.llm_called is True
    assert advisory.entity_slots_candidate.get("user") == "jsmith"
    assert advisory.scheduling_trace.get("intent_advisor_provider_configured") is False

    qi = build_query_to_intent(
        query=WINDOWS_LOG_QUERY,
        query_understanding=understanding,
        routed_skill=route["skill"],
        llm_intent_advisory=advisory,
    )
    assert qi.intent_classification.intent_family == "spl_generation_only"


def test_tight_budget_prioritizes_intent_over_full_sidecar_reserve(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.ai_soc_llm_intent_advisor_reserve_seconds", 12.0)
    monkeypatch.setattr("app.config.settings.ai_soc_llm_timeout_seconds", 120)

    budget = TurnLlmBudget(deadline_seconds=40.0)
    budget.started_at = time.monotonic() - 27.5
    assert budget.remaining_seconds() >= 12.0
    assert intent_advisor_hop_blocked(budget) is None
    from app.llm.sidecar_clients import sidecar_timeout_seconds
    from app.config import settings as cfg

    full_intent_socket = min(
        sidecar_timeout_seconds("intent_shadow_classifier"),
        float(cfg.ai_soc_llm_timeout_seconds),
    )
    assert full_intent_socket >= 30.0
    assert not budget.can_start_call(reserve_seconds=full_intent_socket)
    assert hop_reserve_seconds("intent_shadow_classifier") == 12.0

    budget.started_at = time.monotonic() - 39.2
    assert intent_advisor_hop_blocked(budget) == "insufficient_deadline_reserve"
    assert budget.narration_hop_blocked() == "insufficient_deadline_reserve"


def test_scheduling_trace_fields_when_intent_skipped_for_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")

    budget = TurnLlmBudget(deadline_seconds=10.0)
    budget.started_at = time.monotonic() - 9.5

    state = graph_node_query_to_intent(
        {
            "request": ChatRequest(message=WINDOWS_LOG_QUERY),
            "effective_query": WINDOWS_LOG_QUERY,
            "query_understanding": understand_query(WINDOWS_LOG_QUERY),
            "routed": {"skill": "spl_generation"},
            "llm_turn_budget": budget,
        }
    )

    advisory = state["llm_intent_advisory"]
    trace = advisory.scheduling_trace
    assert advisory.dropped_reasons == ["insufficient_deadline_reserve"]
    assert trace["intent_advisor_required_reserve_ms"] == 12000
    assert trace["downstream_budget_reserved_ms"] > 0
    assert trace["fallback_reason_if_intent_skipped"] == "insufficient_deadline_reserve"
    assert trace["route_selected_after_intent_skip"] == "spl_generation"
    assert trace["intent_advisor_deadline_remaining_ms"] is not None
    assert trace["intent_advisor_elapsed_before_call_ms"] is not None


def test_after_hours_logon_guidance_stays_procedural_not_spl() -> None:
    query = "How should SOC investigate after-hours logons?"
    signals = extract_query_signals(query)
    assert signals["guidance_request"] is True
    assert signals["explicit_log_search"] is False

    understanding = understand_query(query)
    route, _ = select_route_from_understanding(understanding, query)
    assert route["skill"] != "spl_generation"

    qi = build_query_to_intent(query=query, query_understanding=understanding, routed_skill=route["skill"])
    assert qi.intent_classification.intent_family != "spl_generation_only"
    assert qi.intent_classification.primary_intent != "spl_generation"
