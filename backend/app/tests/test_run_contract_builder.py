"""Unit tests for RouteContract / RunContract pure builders."""

from __future__ import annotations

import pytest

from app.chat.intent_classifier import build_query_to_intent
from app.chat.evidence_planner import plan_evidence
from app.chat.planning_decision import plan_path_and_tools
from app.chat.run_contract_builder import (
    build_answer_preview,
    build_route_contract,
    build_run_contract,
)
from app.config import settings
from app.query_understanding.parser import understand_query
from app.routing.registry_route_authority import resolve_effective_routing_skill
from app.routing.route_adjudication import adjudicate_route
from app.routing.select_route_from_understanding import select_route_from_understanding
from app.spl.draft_preview import GENERIC_LIVE_DATA_FAMILY_ID, build_draft_preview

_SUBSTATION_QUERY = (
    "Show me all external connections or remote access sessions currently mapping "
    "to the substation networks."
)
_OT_GUIDANCE_QUERY = "How should SOC investigate repeated port 502 scans targeting OT PLCs?"
_VPN_QUERY = "Show me privileged VPN sessions from last night"


def _base_pipeline_state(query: str) -> dict:
    understanding = understand_query(query)
    route, _comparison = select_route_from_understanding(understanding, query)
    qi = build_query_to_intent(
        query=query,
        query_understanding=understanding,
        routed_skill=route["skill"],
    )
    intent = qi.intent_classification.model_dump(mode="python")
    evidence_plan = plan_evidence(
        intent,
        query_to_intent=qi.model_dump(mode="python"),
        routed=route,
        query_understanding=understanding,
    ).model_dump(mode="python")
    planning = plan_path_and_tools(
        intent_classification=intent,
        evidence_plan=evidence_plan,
        routed=route,
        query_understanding=understanding,
        llm_intent_advisory=None,
    )
    resolution = resolve_effective_routing_skill(
        selected_skill=route["skill"],
        route_authority=route.get("routing_provenance"),
        primary_operation=None,
    )
    adjudication = adjudicate_route(
        deterministic_route=route["skill"],
        evidence_plan=evidence_plan,
        intent_classification=intent,
        query_understanding=understanding,
        message=query,
        query_to_intent=qi.model_dump(mode="python"),
    )
    return {
        "routed": route,
        "query_to_intent": qi.model_dump(mode="python"),
        "intent_classification": intent,
        "evidence_plan": evidence_plan,
        "planning_decision": planning.model_dump(mode="python"),
        "routing_skill_resolution": resolution,
        "route_adjudication": adjudication.model_dump(mode="python"),
        "execution": {
            "status": "skipped",
            "block_reason": "mcp_not_allowed_by_evidence_plan",
        },
        "human_review": {"required": False},
    }


def _with_draft_preview(state: dict, query: str, *, live_data_request: bool) -> dict:
    preview = build_draft_preview(query, live_data_request=live_data_request)
    return {**state, "spl_draft_preview": preview}


@pytest.fixture(params=[True, False], ids=["cp_on", "cp_off"])
def control_plane_flag(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    return request.param


def test_substation_live_data_contract(control_plane_flag: bool) -> None:
    state = _base_pipeline_state(_SUBSTATION_QUERY)
    state = _with_draft_preview(state, _SUBSTATION_QUERY, live_data_request=True)

    route = build_route_contract(state)
    contract = build_run_contract(state, route=route)
    preview = build_answer_preview(contract)

    assert route.canonical_skill == "spl_generation"
    assert route.live_data_request is True
    assert route.guidance_request is False
    assert route.legacy_authoritative is False
    assert route.authority_holder == "canonical_run_contract"

    assert contract.execution_needed_for_answer is True
    assert contract.mcp_needed_for_live_answer is True
    assert contract.collected_evidence_count == 0
    assert contract.source_evidence_available is False
    assert contract.effective_hil_required is True
    assert contract.allow_live_result_language is False
    assert contract.allow_results_table is False
    assert contract.allow_severity_assessment is False
    assert contract.spl_execution_eligible is False
    assert contract.spl_candidate_present is True
    assert contract.spl_candidate_renderable is True
    assert state["spl_draft_preview"]["detection_family"] == "esp_it_to_ot_connection"
    assert state["spl_draft_preview"].get("template_match_strength") == "strong"
    assert "Review-only SPL draft" in preview


def test_ot_guidance_contract(control_plane_flag: bool) -> None:
    state = _base_pipeline_state(_OT_GUIDANCE_QUERY)

    route = build_route_contract(state)
    contract = build_run_contract(state, route=route)
    preview = build_answer_preview(contract)

    assert route.canonical_skill == "guided_investigation"
    assert route.guidance_request is True
    assert route.live_data_request is False
    assert contract.execution_needed_for_answer is False
    assert contract.mcp_needed_for_live_answer is False
    assert contract.collected_evidence_count == 0
    assert contract.allow_live_result_language is False
    assert "no live telemetry" in preview.lower()


def test_vpn_generic_live_data_contract(control_plane_flag: bool) -> None:
    state = _base_pipeline_state(_VPN_QUERY)
    state = _with_draft_preview(state, _VPN_QUERY, live_data_request=True)

    route = build_route_contract(state)
    contract = build_run_contract(state, route=route)

    assert route.canonical_skill == "spl_generation"
    assert route.live_data_request is True
    assert contract.execution_needed_for_answer is True
    assert contract.mcp_needed_for_live_answer is True
    assert contract.collected_evidence_count == 0
    assert contract.effective_hil_required is True
    assert state["spl_draft_preview"]["detection_family"] == GENERIC_LIVE_DATA_FAMILY_ID
    assert state["spl_draft_preview"]["detection_family"] != "esp_it_to_ot_connection"
    assert state["spl_draft_preview"].get("template_match_strength") == "none"
    assert contract.spl_candidate_present is True
    assert contract.spl_candidate_renderable is True


def test_collected_evidence_count_ignores_skipped_source_evidence_rows() -> None:
    state = _base_pipeline_state(_VPN_QUERY)
    state["source_evidence"] = [
        {
            "source_type": "splunk_mcp",
            "collection_status": "skipped",
        }
    ]
    state["soc_kb_retrieval"] = {"retrieval_status": "no_match"}
    route = build_route_contract(state)
    contract = build_run_contract(state, route=route)
    assert contract.collected_evidence_count == 0


def test_collected_evidence_count_from_rag_retrieval() -> None:
    state = _base_pipeline_state(_OT_GUIDANCE_QUERY)
    state["soc_kb_retrieval"] = {"retrieval_status": "retrieved", "retrieved_entries": [{"id": "1"}]}
    route = build_route_contract(state)
    contract = build_run_contract(state, route=route)
    assert contract.collected_evidence_count == 1
    assert contract.source_evidence_available is True


def test_cp_off_uses_routing_resolution_not_adjudication(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _base_pipeline_state(_SUBSTATION_QUERY)
    state["route_adjudication"] = {
        **state["route_adjudication"],
        "final_route": "knowledge_recall",
        "authority_source": "intent_clarification",
    }
    state["routing_skill_resolution"] = {
        "effective_skill": "spl_generation",
        "legacy_intent_authority": True,
        "skill_resolution": "legacy_selected_skill",
    }
    route = build_route_contract(state)
    assert route.canonical_skill == "spl_generation"


def test_cp_on_prefers_adjudication_final_route(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _base_pipeline_state(_SUBSTATION_QUERY)
    state["route_adjudication"] = {
        **state["route_adjudication"],
        "final_route": "spl_generation",
        "authority_source": "unmapped_live_data_request",
    }
    state["routing_skill_resolution"] = {
        "effective_skill": "knowledge_recall",
        "legacy_intent_authority": True,
        "skill_resolution": "legacy_selected_skill",
    }
    route = build_route_contract(state)
    assert route.canonical_skill == "spl_generation"
    assert route.adjudication_authority_source == "unmapped_live_data_request"
