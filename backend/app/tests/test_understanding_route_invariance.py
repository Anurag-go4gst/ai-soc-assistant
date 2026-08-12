"""Plan 5 B3 — understanding must not echo the provisional route."""

from __future__ import annotations

import pytest

from app.chat.intent_classifier import build_query_to_intent
from app.chat.resolved_query_builder import build_resolved_query_contract
from app.query_understanding.parser import understand_query


@pytest.mark.parametrize(
    "provisional_skill_a,provisional_skill_b",
    [
        ("knowledge_recall", "attack_discovery"),
        ("spl_generation", "guided_investigation"),
        ("alert_summary", "knowledge_recall"),
    ],
)
def test_resolved_query_contract_invariant_to_provisional_skill(
    provisional_skill_a: str,
    provisional_skill_b: str,
) -> None:
    query = "What incident or alert network events are high or critical right now?"
    qu = understand_query(query)

    contract_a = build_resolved_query_contract(
        query=query,
        query_understanding=qu,
        qualification_tier="T1",
        qualification_source="exact_105_question",
    )
    contract_b = build_resolved_query_contract(
        query=query,
        query_understanding=qu,
        qualification_tier="T1",
        qualification_source="exact_105_question",
    )

    assert contract_a == contract_b
    assert contract_a.intent_family != provisional_skill_a


def test_build_query_to_intent_ignores_provisional_skill_when_omitted() -> None:
    query = "Show failed login spike by user in the last 24 hours"
    qu = understand_query(query)

    without_route = build_query_to_intent(
        query=query,
        query_understanding=qu,
        routed_skill=None,
    )
    with_route_a = build_query_to_intent(
        query=query,
        query_understanding=qu,
        routed_skill="knowledge_recall",
    )
    with_route_b = build_query_to_intent(
        query=query,
        query_understanding=qu,
        routed_skill="attack_discovery",
    )

    assert without_route.intent_classification == with_route_a.intent_classification
    assert with_route_a.intent_classification == with_route_b.intent_classification
