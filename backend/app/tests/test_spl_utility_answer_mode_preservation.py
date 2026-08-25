"""Preserve spl_utility_authoring answer_mode against coarse canonical spl rule."""

from __future__ import annotations

import pytest

from app.chat.canonical_handoff_builder import build_canonical_planning_input
from app.chat.canonical_handoff_store import clear_all_handoffs_for_tests
from app.chat.contracts.intent_classification import IntentClassification
from app.chat.evidence_planner import plan_evidence
from app.chat.plan_evidence_from_canonical import plan_evidence_from_canonical
from app.chat.query_signals import extract_query_signals
from app.query_understanding.parser import understand_query


@pytest.fixture(autouse=True)
def _clear_handoffs() -> None:
    clear_all_handoffs_for_tests()


def test_explicit_spl_utility_authoring_not_upgraded_to_live_investigation() -> None:
    query = "give me a spl command to get all the firewall logs for last 30 days"
    signals = extract_query_signals(query)
    intent = IntentClassification(
        intent_family="spl_generation_only",
        primary_intent="ask_for_query_generation",
        query_type="ask_for_query_generation",
        answer_goal=["spl_artifact"],
        confidence=0.9,
        confidence_band="high",
        requires_clarification=False,
        reason="test_spl_utility_preservation",
    )
    pre = plan_evidence(
        intent,
        {"query_signals": signals, "intent_classification": intent.model_dump()},
        routed={"skill": "spl_generation"},
    )
    assert pre.answer_mode == "spl_utility_authoring"

    understanding = understand_query(query)
    canonical = build_canonical_planning_input(
        query=query,
        query_understanding=understanding,
        routed={"skill": "spl_generation", "reasons": ["test"]},
        intent_classification=intent.model_dump(),
        resolved_tier="T4",
        processing_lane="guided",
        handoff_id="cpi:spl-utility-preservation",
    )
    plan, _, _ = plan_evidence_from_canonical(
        canonical,
        intent_classification=intent.model_dump(),
        query_to_intent={"query_signals": signals, "intent_classification": intent.model_dump()},
        routed={"skill": "spl_generation"},
        user_query=query,
    )
    assert plan.answer_mode == "spl_utility_authoring"
    assert "universal_spl_utility_authoring" in plan.reasons
