"""Stage 3L-S2B: output artifact token resolution (shadow/lineage only)."""

from __future__ import annotations

from app.api.routes_chat import chat
from app.api.routes_scenarios import run_demo_scenario_fixture
from app.routing.intent_to_operation_bridge import evaluate_intent_operation_bridge
from app.routing.intent_operation_bridge_shadow import apply_intent_operation_bridge_to_shadow
from app.routing.output_artifacts import (
    OUTPUT_ARTIFACT_ANALYST_SUMMARY_ONLY,
    OUTPUT_ARTIFACT_CANDIDATE_SPL_VISIBLE,
    OUTPUT_ARTIFACT_KNOWLEDGE_ONLY,
    resolve_output_artifacts,
)
from app.schemas.requests import ChatRequest
from app.tests.test_route_plan_stage3k_r2 import _patch_common_chat_dependencies, _valid_route_plan_candidate


def test_resolve_tokens_by_legacy_intent() -> None:
    assert resolve_output_artifacts("attack_discovery").tokens == [OUTPUT_ARTIFACT_CANDIDATE_SPL_VISIBLE]
    assert resolve_output_artifacts("knowledge_recall").tokens == [OUTPUT_ARTIFACT_KNOWLEDGE_ONLY]
    assert resolve_output_artifacts("alert_summary").tokens == [OUTPUT_ARTIFACT_ANALYST_SUMMARY_ONLY]


def test_spl_generation_uses_bridge_hint() -> None:
    bridge = evaluate_intent_operation_bridge("spl_generation", "aggregate_and_rank")
    resolved = resolve_output_artifacts("spl_generation", bridge=bridge)
    assert resolved.tokens == [OUTPUT_ARTIFACT_CANDIDATE_SPL_VISIBLE]
    assert resolved.bridge_hint_applied is True


def test_unknown_intent_empty_tokens() -> None:
    resolved = resolve_output_artifacts("not_a_legacy_intent")
    assert resolved.tokens == []
    assert resolved.unknown_legacy_intent is True


def test_shadow_includes_output_artifacts() -> None:
    shadow: dict = {"primary_skill": "aggregate_and_rank"}
    apply_intent_operation_bridge_to_shadow(shadow, legacy_intent="attack_discovery")
    artifacts = shadow["output_artifacts"]
    assert artifacts["resolved_artifacts"] == [OUTPUT_ARTIFACT_CANDIDATE_SPL_VISIBLE]
    assert artifacts["renderer_applied"] is False


def test_chat_experience_center_unchanged(monkeypatch) -> None:
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")
    response = chat(ChatRequest(message="Top source IPs by failed login count in the last hour."))
    assert response.selected_skill == "attack_discovery"
    assert response.route_plan_shadow is not None
    assert response.route_plan_shadow.output_artifacts is not None
    assert response.route_plan_shadow.output_artifacts["resolved_artifacts"] == [OUTPUT_ARTIFACT_CANDIDATE_SPL_VISIBLE]


def test_lineage_includes_output_artifacts_stage(monkeypatch) -> None:
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")
    monkeypatch.setattr("app.api.routes_chat._route_plan_shadow_candidate", lambda query: _valid_route_plan_candidate())
    response = chat(ChatRequest(message="Find the top 10 users with failed Okta login attempts in the last 24 hours."))
    stage_ids = [s.stage_id for s in response.investigation_lineage.stages]
    assert "output_artifacts" in stage_ids


def test_demo_scenario_unchanged() -> None:
    response = run_demo_scenario_fixture("failed_login_spike_app01")
    assert response.selected_skill == "attack_discovery"
    assert response.route_plan_shadow is None
