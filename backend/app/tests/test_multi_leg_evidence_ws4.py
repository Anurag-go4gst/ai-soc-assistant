from __future__ import annotations

from app.chat.answer_shape_router import build_shaped_guidance
from app.chat.evidence_planner import plan_evidence
from app.chat.contracts.intent_classification import IntentClassification
from app.chat.multi_leg_evidence import compose_multi_leg_evidence
from app.config import settings
from app.query_understanding.models import (
    OutputTemplate,
    QueryEntities,
    QueryUnderstandingResult,
    RequestedOutputType,
)


def _understanding(query: str) -> QueryUnderstandingResult:
    return QueryUnderstandingResult(
        raw_query=query,
        normalized_query=query.lower(),
        primary_intent="investigate",
        requested_output_type=RequestedOutputType.INVESTIGATION,
        output_template=OutputTemplate.INVESTIGATION_ANSWER,
        entities=QueryEntities(),
        confidence=0.4,
        deterministic_match_path="out_of_registry",
        soc_investigation_shaped=True,
    )


def test_phish_to_jump_host_composes_both_legs() -> None:
    query = "Correlate a phishing link click by a corporate AD user with later RDP access to an OT jump host."
    composition = compose_multi_leg_evidence(query)
    assert composition is not None
    assert [leg["domain"] for leg in composition["evidence_legs"]] == ["phishing", "ot_jump_host"]
    assert composition["correlation"]["join_key"] == "user"


def test_timeline_plan_carries_legs_into_resource_plan_provenance() -> None:
    query = "Reconstruct the vendor VPN login, OT jump-host RDP session, and relay configuration change."
    plan = plan_evidence(
        IntentClassification(
            intent_family="guided_investigation",
            primary_intent="investigate",
            query_type="investigation_with_guidance",
            answer_goal=["analyst_action_guidance"],
            confidence=0.4,
            confidence_band="low",
            requires_clarification=False,
            requires_hil=True,
            reason="test_out_of_registry",
        ),
        routed={"skill": "guided_investigation"},
        query_understanding=_understanding(query),
    )
    assert [leg["domain"] for leg in plan.evidence_legs] == ["vpn_auth", "ot_jump_host", "relay_change"]
    assert plan.resource_plan is not None
    assert len(plan.resource_plan["provenance"]["evidence_legs"]) == 3
    assert plan.correlation["join_key"] == "user"


def test_guidance_surfaces_each_leg_and_causality_limit(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t2_answer_shape_enabled", True)
    query = "Correlate failed login authentication failures with a successful login from the same host."
    guidance = build_shaped_guidance(query, match_path="out_of_registry")
    assert "Leg 1 — auth_failure" in guidance
    assert "Leg 2 — auth_success" in guidance
    assert "not proof of causation" in guidance
