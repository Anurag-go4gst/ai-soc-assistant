"""Stage 3K-Q1E route_plan_shadow template match + lineage tests."""

from __future__ import annotations

from typing import Any

import pytest

from app.api.routes_chat import chat
from app.config import settings
from app.routing.template_match_shadow import (
    SKIP_NO_VALIDATED_ROUTE_PLAN,
    SKIP_ROUTING_SHADOW_DISABLED,
    TEMPLATE_MATCH_STATUS_MATCHED,
    TEMPLATE_MATCH_STATUS_NO_MATCH,
)
from app.schemas.requests import ChatRequest
from app.tests.test_route_plan_stage3k_r2 import (
    FakeTelemetry,
    _patch_common_chat_dependencies,
    _valid_route_plan_candidate,
    fake_plan_workflow,
)


def test_shadow_disabled_skips_template_match(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_common_chat_dependencies(monkeypatch, skill="knowledge_recall")
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", False)
    monkeypatch.setattr("app.api.routes_chat._route_plan_shadow_candidate", lambda query: _valid_route_plan_candidate())

    response = chat(ChatRequest(message="Find the top 10 users with failed Okta login attempts in the last 24 hours."))

    assert response.route_plan_shadow is not None
    assert response.route_plan_shadow.template_match_attempted is False
    assert response.route_plan_shadow.template_match_skip_reason == SKIP_ROUTING_SHADOW_DISABLED
    assert response.route_plan_shadow.matched_template_id is None


def test_validated_route_plan_matches_sample_template(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_common_chat_dependencies(monkeypatch, skill="knowledge_recall")
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", True)
    monkeypatch.setattr("app.api.routes_chat._route_plan_shadow_candidate", lambda query: _valid_route_plan_candidate())

    response = chat(ChatRequest(message="Find the top 10 users with failed Okta login attempts in the last 24 hours."))

    shadow = response.route_plan_shadow
    assert shadow is not None
    assert shadow.template_match_attempted is True
    assert shadow.template_match_skip_reason is None
    assert shadow.matched_template_id == "sample_auth_failed_login_top_users_tstats"
    assert shadow.template_sample_only is True
    assert shadow.template_production_executable is False
    assert shadow.rendered_spl_execution_eligible is False
    assert shadow.rendered_spl_available is True
    assert shadow.rendered_spl_validator_approved is True
    assert shadow.template_match_shadow_status == TEMPLATE_MATCH_STATUS_MATCHED
    assert shadow.evidence_output_contract is not None
    assert shadow.evidence_output_contract.get("output_type") == "ranked_entities"
    assert shadow.rendered_spl_sha256
    assert shadow.coe_synthetic_fixture is True
    assert shadow.captured_live_run is False
    assert shadow.production_execution is False
    assert shadow.llm_called is False

    lineage = response.investigation_lineage
    assert lineage is not None
    template_stage = next(s for s in lineage.stages if s.stage_id == "template_match_shadow")
    assert template_stage.status == TEMPLATE_MATCH_STATUS_MATCHED
    assert "rendered_spl" not in template_stage.technical_output
    assert template_stage.technical_output.get("rendered_spl_sha256") == shadow.rendered_spl_sha256


def test_no_validated_route_plan_skips_template_match(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_common_chat_dependencies(monkeypatch, skill="knowledge_recall")

    response = chat(ChatRequest(message="Which SOP covers brute force authentication?"))

    shadow = response.route_plan_shadow
    assert shadow is not None
    assert shadow.template_match_attempted is False
    assert shadow.template_match_skip_reason == SKIP_NO_VALIDATED_ROUTE_PLAN
    assert shadow.matched_template_id is None
    assert not any(s.stage_id == "template_match_shadow" for s in (response.investigation_lineage.stages or []))


def test_preflight_blocked_skips_template_match(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_common_chat_dependencies(monkeypatch, skill="knowledge_recall")
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", True)

    response = chat(ChatRequest(message="What happened for this notable?"))

    shadow = response.route_plan_shadow
    assert shadow.template_match_attempted is False
    assert shadow.template_match_skip_reason == SKIP_NO_VALIDATED_ROUTE_PLAN


def test_invalid_route_plan_skips_template_match(monkeypatch: pytest.MonkeyPatch) -> None:
    invalid = _valid_route_plan_candidate()
    invalid["parameters"].pop("group_by")
    _patch_common_chat_dependencies(monkeypatch, skill="knowledge_recall")
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", True)
    monkeypatch.setattr("app.api.routes_chat._route_plan_shadow_candidate", lambda query: invalid)

    response = chat(ChatRequest(message="Find the top 10 users with failed Okta login attempts in the last 24 hours."))

    shadow = response.route_plan_shadow
    assert shadow.template_match_attempted is False
    assert shadow.template_match_skip_reason == SKIP_NO_VALIDATED_ROUTE_PLAN


def test_no_matching_template_records_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _valid_route_plan_candidate()
    plan["source_class"] = "unknown_source_xyz"
    plan["parameters"]["group_by"] = {"field": "user"}
    plan.pop("evidence_needs", None)
    _patch_common_chat_dependencies(monkeypatch, skill="knowledge_recall")
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", True)
    monkeypatch.setattr("app.api.routes_chat._route_plan_shadow_candidate", lambda query: plan)

    response = chat(ChatRequest(message="Find users from unknown source."))

    shadow = response.route_plan_shadow
    assert shadow.template_match_attempted is True
    assert shadow.matched_template_id is None
    assert shadow.template_match_shadow_status == TEMPLATE_MATCH_STATUS_NO_MATCH
    assert shadow.template_mismatch_reasons
    assert shadow.rendered_spl_available is False


def test_shadow_never_exposes_rendered_spl_text(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_common_chat_dependencies(monkeypatch, skill="knowledge_recall")
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", True)
    monkeypatch.setattr("app.api.routes_chat._route_plan_shadow_candidate", lambda query: _valid_route_plan_candidate())

    response = chat(ChatRequest(message="Find the top 10 users with failed Okta login attempts in the last 24 hours."))

    shadow_dump = response.route_plan_shadow.model_dump() if response.route_plan_shadow else {}
    assert "rendered_spl" not in shadow_dump
    for stage in response.investigation_lineage.stages if response.investigation_lineage else []:
        assert "rendered_spl" not in stage.technical_output


def test_q1e_does_not_invoke_llm_sidecars(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"matcher_assist": 0, "renderer_assist": 0}

    def _matcher_assist(*args: Any, **kwargs: Any) -> Any:
        calls["matcher_assist"] += 1
        raise AssertionError("Q1E must not call template_matcher_llm_assist")

    def _renderer_assist(*args: Any, **kwargs: Any) -> Any:
        calls["renderer_assist"] += 1
        raise AssertionError("Q1E must not call template_renderer_llm_assist")

    _patch_common_chat_dependencies(monkeypatch, skill="knowledge_recall")
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", True)
    monkeypatch.setattr("app.api.routes_chat._route_plan_shadow_candidate", lambda query: _valid_route_plan_candidate())
    monkeypatch.setattr("app.spl.template_matcher_llm_assist.match_route_plan_with_semantic_assist", _matcher_assist)
    monkeypatch.setattr("app.spl.template_renderer_llm_assist.render_template_with_parameter_assist", _renderer_assist)

    chat(ChatRequest(message="Find the top 10 users with failed Okta login attempts in the last 24 hours."))

    assert calls == {"matcher_assist": 0, "renderer_assist": 0}


def test_chat_analyst_fields_unchanged_with_template_shadow(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")

    baseline = chat(ChatRequest(message="Top source IPs by failed login count in the last hour."))

    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", True)
    monkeypatch.setattr("app.api.routes_chat._route_plan_shadow_candidate", lambda query: _valid_route_plan_candidate())

    with_shadow = chat(ChatRequest(message="Top source IPs by failed login count in the last hour."))

    assert with_shadow.message == baseline.message
    assert with_shadow.note == baseline.note
    assert with_shadow.selected_skill == baseline.selected_skill
    assert with_shadow.analyst_response == baseline.analyst_response
    assert with_shadow.execution.status == baseline.execution.status if with_shadow.execution and baseline.execution else True
