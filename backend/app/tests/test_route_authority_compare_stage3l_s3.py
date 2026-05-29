"""Stage 3L-S3 Steps 1–2: route_authority_compare shadow envelope."""

from __future__ import annotations

from app.api.routes_chat import chat
from app.api.routes_scenarios import run_demo_scenario_fixture
from app.routing.route_authority_compare import (
    AUTHORITY_HOLDER_LEGACY_SELECTED_SKILL,
    build_route_authority_compare,
)
from app.schemas.requests import ChatRequest
from app.tests.test_route_plan_stage3k_r2 import _patch_common_chat_dependencies, _valid_route_plan_candidate


def test_build_route_authority_compare_unifies_layers() -> None:
    shadow = {
        "primary_skill": "aggregate_and_rank",
        "disagreements": [{"field": "primary_skill", "source": "q1f"}],
        "intent_operation_bridge": {
            "bridge_status": "compatible",
            "compatible": True,
            "disagreements": [],
        },
    }
    payload = build_route_authority_compare(
        selected_skill="attack_discovery",
        route_plan_shadow=shadow,
        routing_comparison={"match": True, "skill_match": True, "tool_plan_match": True},
    )

    assert payload["selected_skill"] == "attack_discovery"
    assert payload["route_plan_primary_skill_observed"] == "aggregate_and_rank"
    assert payload["intent_operation_bridge_status"] == "compatible"
    assert payload["authority_holder"] == AUTHORITY_HOLDER_LEGACY_SELECTED_SKILL
    assert payload["operation_authoritative_enabled"] is False
    assert len(payload["route_plan_shadow_disagreements"]) == 1
    assert payload["intent_bridge_disagreements"] == []


def test_chat_includes_route_authority_compare_without_changing_selected_skill(monkeypatch) -> None:
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")

    response = chat(ChatRequest(message="Top source IPs by failed login count in the last hour."))

    assert response.selected_skill == "attack_discovery"
    compare = response.route_plan_shadow.route_authority_compare
    assert compare is not None
    assert compare["selected_skill"] == "attack_discovery"
    assert compare["operation_authoritative_enabled"] is False
    assert compare["legacy_skill_router_match"] is True


def test_route_authority_compare_with_mock_candidate(monkeypatch) -> None:
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")
    monkeypatch.setattr("app.api.routes_chat._route_plan_shadow_candidate", lambda query: _valid_route_plan_candidate())

    response = chat(ChatRequest(message="Find the top 10 users with failed Okta login attempts in the last 24 hours."))

    compare = response.route_plan_shadow.route_authority_compare
    assert compare["route_plan_primary_skill_observed"] == "aggregate_and_rank"
    assert compare["intent_operation_bridge_status"] == "compatible"


def test_compare_disabled_when_flag_off(monkeypatch) -> None:
    monkeypatch.setattr("app.config.settings.route_authority_compare_enabled", False)
    _patch_common_chat_dependencies(monkeypatch, skill="knowledge_recall")

    response = chat(ChatRequest(message="Which SOP covers brute force authentication?"))

    assert response.route_plan_shadow.route_authority_compare is None


def test_lineage_includes_route_authority_compare_stage(monkeypatch) -> None:
    _patch_common_chat_dependencies(monkeypatch, skill="knowledge_recall")

    response = chat(ChatRequest(message="Which SOP covers brute force authentication?"))

    assert "route_authority_compare" in [s.stage_id for s in response.investigation_lineage.stages]


def test_experience_center_unchanged() -> None:
    response = run_demo_scenario_fixture("failed_login_spike_app01")

    assert response.route_plan_shadow is None
