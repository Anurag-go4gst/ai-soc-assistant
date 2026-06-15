from __future__ import annotations

from app.chat.intent_classifier import build_query_to_intent
from app.query_understanding.parser import understand_query
from app.routing.route_adjudication import adjudicate_route
from app.use_cases.registry import match_use_cases

FLAGSHIP_QUERY = (
    "Show me all critical alerts in the last 6 hours, cross-reference with MITRE ATT&CK, "
    "and check if any affected hosts have unpatched CVEs"
)


def test_flagship_query_matches_critical_notable_lab_use_case() -> None:
    matches = match_use_cases(FLAGSHIP_QUERY, limit=5)
    use_case_ids = [item.use_case_id for item in matches]
    assert "critical_notable_mitre_review" in use_case_ids
    assert use_case_ids[0] == "critical_notable_mitre_review"


def test_flagship_query_routes_attack_discovery_not_knowledge_recall() -> None:
    understanding = understand_query(FLAGSHIP_QUERY)
    query_to_intent = build_query_to_intent(
        query=FLAGSHIP_QUERY,
        query_understanding=understanding,
        routed_skill="attack_discovery",
    )
    intent = query_to_intent.intent_classification.model_dump()
    adjudication = adjudicate_route(
        deterministic_route="attack_discovery",
        llm_advisory=None,
        route_plan_shadow=None,
        evidence_plan={},
        intent_classification=intent,
        query_understanding=understanding,
        message=FLAGSHIP_QUERY,
        query_to_intent=query_to_intent.model_dump(),
    )
    assert adjudication.final_route == "attack_discovery"
