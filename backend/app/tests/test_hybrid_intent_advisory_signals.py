"""Hybrid advisory shapes vs command-mode ownership (plan 2026-07-04_1730)."""

from __future__ import annotations

import pytest

from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.chat.planning_decision import plan_path_and_tools
from app.chat.query_signals import extract_query_signals
from app.query_understanding.parser import understand_query
from app.routing.route_adjudication import adjudicate_route
from app.routing.select_route_from_understanding import select_route_from_understanding

# Q9-style — containment decision-support (existing contract)
_Q9_CONTAINMENT = (
    "Ransomware just hit our corporate IT domain controller. Should we isolate the OT "
    "network from IT right now, and what exact steps should the SOC take to protect the "
    "SCADA environment without tripping the grid?"
)

# Q11-style — source health (phrased to stay out_of_registry, not near-105 q0.q095)
_Q11_SOURCE_HEALTH = (
    "For our substation OT collectors only, which log sources have a coverage gap "
    "or ingestion gap and stopped sending events into Splunk this week?"
)

# Q12-style — process-aware OT (AGC / frequency / setpoint)
_Q12_PROCESS_AWARE = (
    "We saw AGC setpoint commands that could push frequency outside 49.9-50.1 Hz. "
    "First list the Splunk indexes or metadata that can prove whether AGC logs exist, "
    "then prepare a review-only hunt for injected vs legitimate dispatch. "
    "Do not run the SPL until I approve."
)

# Affirmative command run (danger-plan spine)
_RUN_SPL = "Run the SPL and give me results."

# Command-shaped paste (validate/optimize; not hybrid advisory)
_COMMAND_PASTE = (
    "Here is SPL: search index=pgcil_soc sourcetype=pgcil:ot_agc earliest=-2h "
    "| stats count by command_src setpoint. Validate and optimize it, list missing "
    "source profile metadata, and if it passes, ask me before running."
)


@pytest.fixture(autouse=True)
def _t2_shape_on(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "ai_soc_t2_answer_shape_enabled", True)


def test_q9_containment_decision_support_routes_guided() -> None:
    signals = extract_query_signals(_Q9_CONTAINMENT)
    assert signals["containment_decision_support"] is True
    assert signals["command_mode_active"] is False
    understanding = understand_query(_Q9_CONTAINMENT)
    route, _ = select_route_from_understanding(understanding, _Q9_CONTAINMENT)
    assert route["skill"] == "guided_investigation"


def test_q11_source_health_not_generic_spl() -> None:
    signals = extract_query_signals(_Q11_SOURCE_HEALTH)
    assert signals["hybrid_advisory_source_health"] is True
    assert signals["command_mode_active"] is False
    understanding = understand_query(_Q11_SOURCE_HEALTH)
    route, prov = select_route_from_understanding(understanding, _Q11_SOURCE_HEALTH)
    assert route["skill"] == "guided_investigation"
    assert route["skill"] != "spl_generation"
    assert prov.get("authority_source") == "guided_investigation_rescue"
    assert prov.get("rescue_reason") in {
        "hybrid_advisory_shape_floor",
        "out_of_registry_t2_answer_shape_floor",
    }
    assert route["skill"] == "guided_investigation"


def test_q12_process_aware_ot_not_generic_spl_and_not_false_run() -> None:
    signals = extract_query_signals(_Q12_PROCESS_AWARE)
    assert signals["explicit_run_spl"] is False
    assert signals["hybrid_advisory_process_aware_ot"] is True
    assert signals["command_mode_active"] is False
    understanding = understand_query(_Q12_PROCESS_AWARE)
    route, _ = select_route_from_understanding(understanding, _Q12_PROCESS_AWARE)
    assert route["skill"] == "guided_investigation"
    assert route["skill"] != "spl_generation"

    qi = build_query_to_intent(
        query=_Q12_PROCESS_AWARE,
        query_understanding=understanding,
        routed_skill=route["skill"],
    )
    assert qi.intent_classification.intent_family == "guided_investigation"


def test_affirmative_run_spl_still_command_mode() -> None:
    signals = extract_query_signals(_RUN_SPL)
    assert signals["explicit_run_spl"] is True
    assert signals["command_mode_active"] is True
    assert signals["hybrid_advisory_process_aware_ot"] is False
    assert signals["hybrid_advisory_source_health"] is False
    understanding = understand_query(_RUN_SPL)
    route, prov = select_route_from_understanding(understanding, _RUN_SPL)
    assert route["skill"] == "spl_generation"
    assert route["skill"] == "spl_generation"
    assert prov.get("authority_source") == "out_of_registry_command_mode_spine"


def test_command_paste_suppresses_hybrid_advisory_despite_setpoint_token() -> None:
    signals = extract_query_signals(_COMMAND_PASTE)
    assert signals["command_mode_active"] is True
    assert signals["command_shaped_spl"] is True
    assert signals["hybrid_advisory_process_aware_ot"] is False
    understanding = understand_query(_COMMAND_PASTE)
    route, prov = select_route_from_understanding(understanding, _COMMAND_PASTE)
    assert route["skill"] == "spl_generation"
    assert route["skill"] != "guided_investigation"
    assert prov.get("authority_source") == "out_of_registry_command_mode_spine"


def test_hybrid_advisory_evidence_plan_is_analyst_visible() -> None:
    understanding = understand_query(_Q12_PROCESS_AWARE)
    route, _ = select_route_from_understanding(understanding, _Q12_PROCESS_AWARE)
    qi = build_query_to_intent(
        query=_Q12_PROCESS_AWARE,
        query_understanding=understanding,
        routed_skill=route["skill"],
    )
    evidence = plan_evidence(
        qi.intent_classification.model_dump(),
        query_to_intent=qi.model_dump(),
        query_understanding=understanding,
        routed=route,
        user_query=_Q12_PROCESS_AWARE,
    )
    assert route["skill"] == "guided_investigation"
    assert evidence.answer_mode == "guided_investigation"
    assert evidence.discovery_allowed is True
    assert evidence.spl_review_allowed is True
    assert evidence.safe_spl_execution_allowed is False
    assert evidence.freeform_spl_execution_allowed is False
    assert evidence.requires_hil is True
    assert "hybrid_advisory_evidence_plan" in evidence.reasons

    adjudication = adjudicate_route(
        deterministic_route=route["skill"],
        evidence_plan=evidence.model_dump(),
        intent_classification=qi.intent_classification,
        query_understanding=understanding,
        query_to_intent=qi.model_dump(),
    )
    planning = plan_path_and_tools(
        intent_classification=qi.intent_classification.model_dump(),
        evidence_plan=evidence.model_dump(),
        routed={"skill": adjudication.final_route},
        query_understanding=understanding,
        selected_use_case=None,
        llm_intent_advisory=None,
    )
    assert adjudication.final_route == "guided_investigation"
    assert planning.execution_enabled is False
    assert planning.path_type == "guided_investigation"
