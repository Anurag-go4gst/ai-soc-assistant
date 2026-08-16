"""Plan 8 R1 — route adjudication consumes the final ResolvedQueryContract."""

from __future__ import annotations

from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.chat.intent_classifier import build_query_to_intent
from app.chat.resolved_query_builder import build_resolved_query_contract
from app.query_understanding.parser import understand_query
from app.routing.route_adjudication import adjudicate_route


def test_adjudication_accepts_final_rqc_without_changing_locked_family() -> None:
    query = "Hunt for CI/CD supply-chain compromise indicators across our environment"
    qu = understand_query(query)
    q2i = build_query_to_intent(query=query, query_understanding=qu)
    contract = build_resolved_query_contract(
        query=query,
        query_understanding=qu,
        qualification_tier="T4",
        qualification_source="out_of_registry",
        query_to_intent=q2i,
    )
    result = adjudicate_route(
        deterministic_route="guided_investigation",
        route_plan_shadow={},
        evidence_plan=None,
        intent_classification=q2i.intent_classification.model_dump(),
        query_understanding=qu,
        message=query,
        query_to_intent=q2i.model_dump(),
        resolved_query_contract=contract,
    )
    assert result.final_route
    assert isinstance(contract, ResolvedQueryContract)
    dumped = result.model_dump()
    assert dumped.get("final_route")
