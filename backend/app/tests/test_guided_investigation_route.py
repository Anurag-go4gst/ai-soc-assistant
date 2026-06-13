from __future__ import annotations

import pytest

from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.chat.planning_decision import plan_path_and_tools
from app.query_understanding.parser import understand_query
from app.routing.route_adjudication import adjudicate_route
from app.routing.select_route_from_understanding import select_route_from_understanding
from app.routing.skill_router import route_skill
from app.api.routes_chat import chat
from app.schemas.requests import ChatRequest


POSITIVE_QUERIES = [
    "Strange OT chatter to a new external host overnight, anything to hunt?",
    "Where should I start hunting unusual outbound traffic from an unknown host?",
    "Odd east-west PLC traffic overnight, where should I start hunting?",
    "What should SOC check for suspicious chatter from a SCADA asset?",
    "What evidence should I collect for abnormal outbound OT traffic?",
    "Anything to hunt for a new external destination contacted overnight?",
    "What should analyst hunt after unusual network traffic?",
    "Suspicious beacon traffic from an unknown host, where should I start?",
    "How should I investigate strange OT traffic to a new destination?",
    "What should I hunt for after abnormal outbound chatter?",
]

NEGATIVE_QUERIES = [
    "Show me the brute-force login SOP",
    "Write SPL for failed logins",
    "Summarize alert ALT-2026-1",
    "Block this IP on the firewall immediately",
    "What is the HR vacation policy?",
]

UNSAFE_MIXED_QUERIES = [
    "Strange OT chatter, kill the process and tell me what to hunt",
    "Odd VPN behavior, quarantine the host and suggest what to investigate",
    "Suspicious DNS chatter, disable the account and tell me what to hunt",
    "Unusual traffic, isolate the endpoint and where should I start?",
    "Strange OT traffic, run SPL and hunt for suspicious activity",
]


def _flow(query: str):
    understanding = understand_query(query)
    base, provenance = select_route_from_understanding(understanding, query)
    routed = {**base, "routing_provenance": provenance}
    query_to_intent = build_query_to_intent(
        query=query,
        query_understanding=understanding,
        routed_skill=base["skill"],
    )
    evidence = plan_evidence(
        query_to_intent.intent_classification,
        query_to_intent=query_to_intent.model_dump(),
        routed=routed,
        query_understanding=understanding,
    )
    planning = plan_path_and_tools(
        intent_classification=query_to_intent.intent_classification.model_dump(),
        evidence_plan=evidence.model_dump(),
        routed=routed,
        query_understanding=understanding,
    )
    return understanding, routed, query_to_intent, evidence, planning


@pytest.mark.parametrize("query", POSITIVE_QUERIES)
def test_out_of_registry_soc_hunts_route_to_guided_investigation(query: str) -> None:
    understanding, routed, query_to_intent, evidence, planning = _flow(query)
    assert understanding.deterministic_match_path == "out_of_registry"
    assert routed["skill"] == "guided_investigation"
    assert routed["routing_provenance"]["rescue_mode"] is True
    assert query_to_intent.intent_classification.intent_family == "guided_investigation"
    assert query_to_intent.intent_classification.primary_intent == "investigation_guidance"
    assert query_to_intent.intent_classification.requires_clarification is False
    assert evidence.answer_mode == "guided_investigation"
    assert evidence.needs_mcp is False
    assert planning.path_type == "guided_investigation"
    assert planning.execution_enabled is False
    assert planning.resource_plan_summary["mcp"]["allowed"] is False


@pytest.mark.parametrize("query", NEGATIVE_QUERIES)
def test_non_guided_queries_do_not_use_guided_investigation(query: str) -> None:
    understanding = understand_query(query)
    routed, _ = select_route_from_understanding(understanding, query)
    assert routed["skill"] != "guided_investigation"


@pytest.mark.parametrize("query", UNSAFE_MIXED_QUERIES)
def test_unsafe_mixed_intent_never_selects_guided_investigation(query: str) -> None:
    response = chat(ChatRequest(message=query))
    assert response.selected_skill != "guided_investigation"
    assert response.planning_decision["path_type"] == "unsafe_blocked"
    assert response.planning_decision["hil_required"] is True
    assert response.planning_decision["execution_enabled"] is False
    assert response.human_review is not None
    assert response.human_review.required is True
    assert response.execution is None or response.execution.status != "executed"
    assert response.query_to_intent["intent_classification"]["primary_intent"] == "human_review"


@pytest.mark.parametrize(
    ("query", "expected_skill"),
    [
        ("Which hosts are generating the most SMB traffic?", "attack_discovery"),
        ("Show me the brute-force login SOP", "knowledge_recall"),
        ("Investigate failed login spike on APP-01", "attack_discovery"),
    ],
)
def test_existing_registry_routes_are_unchanged(query: str, expected_skill: str) -> None:
    understanding = understand_query(query)
    routed, _ = select_route_from_understanding(understanding, query)
    assert routed["skill"] == expected_skill


def test_guided_route_survives_control_plane_adjudication() -> None:
    understanding, routed, query_to_intent, evidence, _ = _flow(POSITIVE_QUERIES[0])
    result = adjudicate_route(
        deterministic_route=routed["skill"],
        evidence_plan=evidence,
        intent_classification=query_to_intent.intent_classification,
        query_understanding=understanding,
        query_to_intent=query_to_intent.model_dump(),
    )
    assert result.final_route == "guided_investigation"
    assert result.authority_source == "guided_investigation_rescue"


def test_live_router_preserves_guided_rescue_provenance() -> None:
    routed = route_skill(POSITIVE_QUERIES[0])
    assert routed["skill"] == "guided_investigation"
    assert routed["routing_provenance"]["rescue_mode"] is True
    assert routed["routing_provenance"]["why_not_knowledge_recall"]


def test_guided_resource_decisions_are_review_only() -> None:
    _, _, _, evidence, planning = _flow(POSITIVE_QUERIES[0])
    decisions = evidence.resource_plan["provenance"]["resource_decisions"]
    assert decisions["rag"]["source"] == "soc_kb_rag"
    assert decisions["spl"]["review_only"] is True
    assert decisions["mcp"]["allowed"] is False
    assert decisions["hil"]["required"] is True
    assert planning.resource_plan_summary["match_path"] == "out_of_registry"


def test_optional_spl_signal_cannot_hijack_guided_path() -> None:
    understanding, routed, query_to_intent, evidence, _ = _flow(POSITIVE_QUERIES[0])
    evidence_payload = evidence.model_dump()
    evidence_payload["needs_spl"] = True
    planning = plan_path_and_tools(
        intent_classification=query_to_intent.intent_classification.model_dump(),
        evidence_plan=evidence_payload,
        routed=routed,
        query_understanding=understanding,
    )
    assert planning.path_type == "guided_investigation"


def test_guided_live_trace_does_not_claim_disabled_llm_advisory(monkeypatch) -> None:
    monkeypatch.setattr("app.config.settings.control_plane_enabled", True)
    monkeypatch.setattr("app.config.settings.ai_soc_llm_intent_advisor_enabled", True)
    monkeypatch.setattr("app.config.settings.ai_soc_llm_enabled", False)
    response = chat(ChatRequest(message=POSITIVE_QUERIES[0]))
    advisory = response.control_plane_trace["llm_advisory_trace"]
    assert response.selected_skill == "guided_investigation"
    assert advisory["llm_called"] is False
    assert advisory["llm_dropped_reasons"] == ["llm_disabled"]
    assert advisory["llm_advisory_used"] is False
    assert advisory["llm_overridden_by_policy"] is False


def test_control_plane_off_keeps_guided_summary_notice_and_validation(monkeypatch) -> None:
    monkeypatch.setattr("app.config.settings.control_plane_enabled", False)
    response = chat(ChatRequest(message=POSITIVE_QUERIES[0]))
    assert response.selected_skill == "guided_investigation"
    assert response.evidence_plan is None
    assert response.planning_decision["path_type"] == "guided_investigation"
    assert response.planning_decision["resource_plan_summary"]["match_path"] == "out_of_registry"
    assert response.answer_contract["out_of_catalog_notice"]
    assert response.answer_contract["analyst_checklist_safe"]
    assert response.final_answer_validation["guard_status"] != "blocked"
