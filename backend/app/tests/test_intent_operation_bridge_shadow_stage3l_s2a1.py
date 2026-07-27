"""Stage 3L-S2A-FOLLOWUP: intent bridge on route_plan_shadow and lineage only."""

from __future__ import annotations

from typing import Any

from app.api.routes_chat import chat
from app.api.routes_scenarios import run_demo_scenario_fixture
from app.routing.intent_operation_bridge_shadow import (
    BRIDGE_STATUS_COMPATIBLE,
    BRIDGE_STATUS_INCOMPATIBLE,
    BRIDGE_STATUS_MODIFIER_ONLY,
    BRIDGE_STATUS_NOT_EVALUATED,
    apply_intent_operation_bridge_to_shadow,
    bridge_status_from_result,
)
from app.routing.intent_to_operation_bridge import (
    IntentOperationBridgeResult,
    evaluate_intent_operation_bridge,
)
from app.schemas.requests import ChatRequest
from app.tests.support.chat_visible import assert_governed_spl_review_posture
from app.tests.test_p2_known_path_authority import _CANONICAL_OKTA_FAILED_LOGIN_SKILL
from app.tests.test_route_plan_stage3k_r2 import _patch_common_chat_dependencies, _valid_route_plan_candidate


def test_bridge_status_mapping_unit() -> None:
    compatible = evaluate_intent_operation_bridge("attack_discovery", "sequence_detection")
    assert bridge_status_from_result(compatible, primary_skill_observed=True) == BRIDGE_STATUS_COMPATIBLE

    incompatible = evaluate_intent_operation_bridge("attack_discovery", "metadata_discovery")
    assert bridge_status_from_result(incompatible, primary_skill_observed=True) == BRIDGE_STATUS_INCOMPATIBLE

    modifier = evaluate_intent_operation_bridge("spl_generation", "aggregate_and_rank")
    assert bridge_status_from_result(modifier, primary_skill_observed=True) == BRIDGE_STATUS_MODIFIER_ONLY

    no_skill = evaluate_intent_operation_bridge("attack_discovery", None)
    assert bridge_status_from_result(no_skill, primary_skill_observed=False) == BRIDGE_STATUS_NOT_EVALUATED


def test_chat_selected_skill_and_message_unchanged_with_bridge(monkeypatch) -> None:
    _patch_common_chat_dependencies(
        monkeypatch,
        skill="attack_discovery",
        disable_deterministic_route_plan=True,
    )

    response = chat(ChatRequest(message="Top source IPs by failed login count in the last hour."))

    assert response.selected_skill == "attack_discovery"
    assert_governed_spl_review_posture(response)
    bridge = response.route_plan_shadow.intent_operation_bridge if response.route_plan_shadow else None
    assert bridge is not None
    assert bridge["bridge_status"] == BRIDGE_STATUS_NOT_EVALUATED
    assert bridge["legacy_intent"] == "attack_discovery"
    assert bridge["primary_skill_observed"] is None
    assert bridge["disagreements"] == []


def test_bridge_compatible_when_primary_skill_observed(monkeypatch) -> None:
    _patch_common_chat_dependencies(
        monkeypatch,
        skill="attack_discovery",
        disable_deterministic_route_plan=True,
    )
    monkeypatch.setattr("app.api.routes_chat._route_plan_shadow_candidate", lambda query: _valid_route_plan_candidate())

    response = chat(ChatRequest(message="Find the top 10 users with failed Okta login attempts in the last 24 hours."))

    assert response.selected_skill == _CANONICAL_OKTA_FAILED_LOGIN_SKILL
    bridge = response.route_plan_shadow.intent_operation_bridge
    assert bridge["bridge_status"] == BRIDGE_STATUS_COMPATIBLE
    assert bridge["primary_skill_observed"] == "aggregate_and_rank"
    assert bridge["compatible"] is True


def test_bridge_incompatible_does_not_change_selected_skill(monkeypatch) -> None:
    candidate = _valid_route_plan_candidate()
    candidate["primary_skill"] = "metadata_discovery"
    candidate["operation_type"] = "metadata_query"
    _patch_common_chat_dependencies(
        monkeypatch,
        skill="attack_discovery",
        disable_deterministic_route_plan=True,
    )
    monkeypatch.setattr("app.api.routes_chat._route_plan_shadow_candidate", lambda query: candidate)

    response = chat(ChatRequest(message="Find the top 10 users with failed Okta login attempts in the last 24 hours."))

    assert response.selected_skill == _CANONICAL_OKTA_FAILED_LOGIN_SKILL
    bridge = response.route_plan_shadow.intent_operation_bridge
    assert bridge["bridge_status"] == BRIDGE_STATUS_INCOMPATIBLE
    assert bridge["compatible"] is False
    assert len(bridge["disagreements"]) == 1
    assert response.route_plan_shadow.disagreements == []


def test_bridge_modifier_only_for_spl_generation(monkeypatch) -> None:
    _patch_common_chat_dependencies(monkeypatch, skill="spl_generation")
    monkeypatch.setattr("app.api.routes_chat._route_plan_shadow_candidate", lambda query: _valid_route_plan_candidate())

    response = chat(ChatRequest(message="Generate SPL for failed logins by user."))

    assert response.selected_skill == "spl_generation"
    bridge = response.route_plan_shadow.intent_operation_bridge
    assert bridge["bridge_status"] == BRIDGE_STATUS_MODIFIER_ONLY
    assert bridge["spl_generation_modifier_detected"] is True
    assert bridge["compatible"] is True


def test_lineage_includes_intent_operation_bridge_stage(monkeypatch) -> None:
    _patch_common_chat_dependencies(monkeypatch, skill="knowledge_recall")

    response = chat(ChatRequest(message="Which SOP covers brute force authentication?"))

    stage_ids = [s.stage_id for s in response.investigation_lineage.stages]
    assert "intent_operation_bridge" in stage_ids
    bridge_stage = next(s for s in response.investigation_lineage.stages if s.stage_id == "intent_operation_bridge")
    assert bridge_stage.current_mode_source == "shadow"
    assert bridge_stage.technical_output["bridge_status"] == BRIDGE_STATUS_NOT_EVALUATED


def test_experience_center_unchanged() -> None:
    response = run_demo_scenario_fixture("failed_login_spike_app01")

    assert response.route_plan_shadow is None
    assert response.demo_mode is True


def test_apply_shadow_does_not_mutate_route_plan_fields() -> None:
    shadow: dict[str, Any] = {"primary_skill": "aggregate_and_rank", "disagreements": []}
    apply_intent_operation_bridge_to_shadow(shadow, legacy_intent="attack_discovery")

    assert shadow["primary_skill"] == "aggregate_and_rank"
    assert shadow["disagreements"] == []
