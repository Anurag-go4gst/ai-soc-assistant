from __future__ import annotations

import pytest

from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.config import settings
from app.query_understanding.parser import understand_query
from app.routing.route_adjudication import adjudicate_route
from app.routing.route_authority_allowlist import COV_Q046_PILOT_COVERAGE_ID


def _adjudicate_for_query(
    query: str,
    *,
    deterministic_route: str = "attack_discovery",
    route_plan_shadow: dict | None = None,
) -> dict:
    qu = understand_query(query)
    q2i = build_query_to_intent(query=query, query_understanding=qu)
    intent = q2i.intent_classification.model_dump()
    evidence = plan_evidence(intent, query_to_intent=q2i.model_dump()).model_dump()
    result = adjudicate_route(
        deterministic_route=deterministic_route,
        route_plan_shadow=route_plan_shadow or {},
        evidence_plan=evidence,
        intent_classification=intent,
        query_understanding=qu,
        message=query,
        query_to_intent=q2i.model_dump(),
    )
    return result.model_dump()


def test_policy_escalation_failed_login_is_knowledge_recall_not_attack_discovery() -> None:
    result = _adjudicate_for_query(
        "What is the escalation policy for repeated failed login alerts?",
        deterministic_route="attack_discovery",
    )
    assert result["final_route"] == "knowledge_recall"
    assert result["authority_source"] in {"intent_over_exact_105", "evidence_plan_rag_only"}
    assert result["final_route"] != "attack_discovery"


def test_hybrid_failed_login_action_preserves_live_investigation_skill() -> None:
    result = _adjudicate_for_query(
        "Find accounts failing login in the last 24 hours, exclude service accounts, "
        "and tell me what analyst action I should take",
        deterministic_route="attack_discovery",
    )
    assert result["final_route"] == "attack_discovery"
    assert result["authority_source"] in {
        "evidence_plan_live_or_hybrid",
        "exact_105_registry",
        "deterministic_route_default",
    }


def test_exact_105_allowlisted_when_operation_authority_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "route_authority_operation_authoritative_enabled", True)
    monkeypatch.setattr(
        settings,
        "route_authority_operation_coverage_allowlist",
        COV_Q046_PILOT_COVERAGE_ID,
    )
    qu = understand_query("Which users have excessive failed logins?")
    q2i = build_query_to_intent(query="Which users have excessive failed logins?", query_understanding=qu)
    intent = q2i.intent_classification.model_dump()
    evidence = plan_evidence(intent, query_to_intent=q2i.model_dump()).model_dump()
    shadow = {
        "question_runtime_map": {
            "manifest_coverage_id": COV_Q046_PILOT_COVERAGE_ID,
            "coverage_id": COV_Q046_PILOT_COVERAGE_ID,
            "question_ref": "q0.q046",
        },
    }
    result = adjudicate_route(
        deterministic_route="attack_discovery",
        route_plan_shadow=shadow,
        evidence_plan=evidence,
        intent_classification=intent,
        query_understanding=qu,
        query_to_intent=q2i.model_dump(),
    )
    if q2i.candidate_mappings.get("match_path") in {
        "exact_105_question",
        "exact_105_plus_use_case_catalog",
    }:
        assert result.authority_source == "exact_105_registry"
        assert result.final_route == "attack_discovery"


def test_blocked_detection_coverage_cannot_be_exact_105_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "route_authority_operation_authoritative_enabled", True)
    monkeypatch.setattr(
        settings,
        "route_authority_operation_coverage_allowlist",
        COV_Q046_PILOT_COVERAGE_ID,
    )
    intent = {
        "intent_family": "live_investigation",
        "primary_intent": "attack_discovery",
        "secondary_intents": [],
        "query_type": "ask_for_live_results",
        "answer_goal": ["live_results"],
        "requested_output_type": "INVESTIGATION",
        "confidence": 0.86,
        "confidence_band": "high",
        "requires_clarification": False,
        "requires_hil": False,
        "action_mode": None,
        "reason": "test",
    }
    evidence = plan_evidence(intent).model_dump()
    shadow = {
        "question_runtime_map": {
            "manifest_coverage_id": "cov.q007.dga_detection_binding",
            "coverage_id": "cov.q007.dga_detection_binding",
        },
    }
    mappings = {
        "match_path": "exact_105_question",
        "use_case_ids": ["dns_beaconing_dga_behavior"],
        "legacy_skill_hint": "attack_discovery",
    }
    result = adjudicate_route(
        deterministic_route="attack_discovery",
        route_plan_shadow=shadow,
        evidence_plan=evidence,
        intent_classification=intent,
        query_to_intent={"candidate_mappings": mappings},
    )
    assert result.authority_source != "exact_105_registry"


def test_clarification_intent_routes_to_knowledge_recall_with_hil_metadata() -> None:
    result = _adjudicate_for_query("Map this to MITRE")
    assert result["final_route"] == "knowledge_recall"
    assert result["authority_source"] == "intent_clarification"
