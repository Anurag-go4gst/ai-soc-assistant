"""Stage 3L-S3 Step 3: cov.q046 operation authority pilot (shadow/planning only)."""

from __future__ import annotations

from typing import Any

import pytest

from app.api.routes_chat import chat
from app.api.routes_scenarios import run_demo_scenario_fixture
from app.config import settings
from app.routing.route_authority_allowlist import COV_Q046_PILOT_COVERAGE_ID
from app.routing.route_authority_gate import (
    FALLBACK_COVERAGE_ID_NOT_ALLOWLISTED,
    FALLBACK_GLOBAL_KILL_SWITCH_DISABLED,
    FALLBACK_MISSING_THRESHOLD_REF,
    evaluate_route_authority,
)
from app.schemas.requests import ChatRequest
from app.tests.test_route_plan_stage3k_r2 import (
    _patch_common_chat_dependencies,
    _valid_route_plan_candidate,
)


def _enable_pilot_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.config.settings.route_authority_operation_authoritative_enabled",
        True,
    )
    monkeypatch.setattr(
        "app.config.settings.route_authority_operation_coverage_allowlist",
        COV_Q046_PILOT_COVERAGE_ID,
    )


def _cov_q046_candidate_with_slots() -> dict[str, Any]:
    candidate = _valid_route_plan_candidate()
    candidate["parameters"]["threshold_ref"] = {"policy_id": "failed_login_excessive_default"}
    candidate["parameters"]["time_window"] = "last_24_hours"
    return candidate


def test_production_defaults_authority_off_allowlist_empty() -> None:
    assert settings.route_authority_operation_authoritative_enabled is False
    assert settings.route_authority_operation_coverage_allowlist.strip() == ""


def test_happy_path_authority_applied_only_with_explicit_lab_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_pilot_authority(monkeypatch)
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")
    monkeypatch.setattr(
        "app.api.routes_chat._route_plan_shadow_candidate",
        lambda query: _cov_q046_candidate_with_slots(),
    )

    response = chat(
        ChatRequest(message="Find top 10 users with failed Okta logins in the last 24 hours.")
    )

    assert response.selected_skill == "attack_discovery"
    compare = response.route_plan_shadow.route_authority_compare
    assert compare["coverage_id_resolved"] == COV_Q046_PILOT_COVERAGE_ID
    assert compare["operation_authoritative_applied"] is True
    assert compare["authority_holder"] == "route_plan_primary_skill"
    assert compare["authority_decision"] == "applied"
    assert compare["coverage_id_resolved"] == COV_Q046_PILOT_COVERAGE_ID
    assert "Operation authority applied" in compare["authority_trace"]
    assert compare["planning_primary_skill"] == "aggregate_and_rank"
    assert response.execution.executed_spl is None


def test_missing_threshold_ref_never_defaults_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_pilot_authority(monkeypatch)
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")
    monkeypatch.setattr(
        "app.api.routes_chat._route_plan_shadow_candidate",
        lambda query: _valid_route_plan_candidate(),
    )

    response = chat(
        ChatRequest(message="Find top 10 users with failed Okta logins in the last 24 hours.")
    )

    assert response.selected_skill == "attack_discovery"
    compare = response.route_plan_shadow.route_authority_compare
    assert compare["coverage_id_resolved"] == COV_Q046_PILOT_COVERAGE_ID
    assert compare["operation_authoritative_applied"] is False
    assert compare["authority_fallback_reason"] == FALLBACK_MISSING_THRESHOLD_REF
    assert compare["authority_decision"] == "fallback"
    assert "not applied" in compare["authority_trace"].lower()


def test_other_coverage_id_not_implicitly_upgraded(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_pilot_authority(monkeypatch)
    candidate = _valid_route_plan_candidate()
    candidate["pattern_id"] = "top_outbound_source_ips"
    candidate["parameters"]["threshold_ref"] = {"policy_id": "x"}
    candidate["parameters"]["time_window"] = "last_24_hours"
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")
    monkeypatch.setattr("app.api.routes_chat._route_plan_shadow_candidate", lambda query: candidate)

    response = chat(ChatRequest(message="Which source IPs generated the most outbound connections?"))

    compare = response.route_plan_shadow.route_authority_compare
    assert compare["coverage_id_resolved"] == "cov.q002.top_outbound_source_ips"
    assert compare["operation_authoritative_applied"] is False
    assert compare["authority_fallback_reason"] == FALLBACK_COVERAGE_ID_NOT_ALLOWLISTED


def test_default_mode_global_kill_switch_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.config.settings.route_authority_operation_authoritative_enabled",
        False,
    )
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")
    monkeypatch.setattr(
        "app.api.routes_chat._route_plan_shadow_candidate",
        lambda query: _cov_q046_candidate_with_slots(),
    )

    response = chat(ChatRequest(message="Which users have excessive failed logins?"))

    compare = response.route_plan_shadow.route_authority_compare
    assert compare["operation_authoritative_applied"] is False
    assert compare["authority_fallback_reason"] == FALLBACK_GLOBAL_KILL_SWITCH_DISABLED
    assert compare["authority_holder"] == "legacy_selected_skill"


def test_experience_center_unchanged() -> None:
    response = run_demo_scenario_fixture("failed_login_spike_app01")
    assert response.route_plan_shadow is None


def test_unit_no_threshold_default_injected(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_pilot_authority(monkeypatch)
    shadow = {
        "primary_skill": "aggregate_and_rank",
        "pattern_id": "top_failed_okta_login_users",
        "normalized_plan_available": True,
        "candidate_available": True,
        "route_status": "route_ready",
        "validation_result": {"is_valid": True},
        "route_plan_parameters": {},
        "intent_operation_bridge": {"bridge_status": "compatible", "compatible": True},
    }
    result = evaluate_route_authority(
        selected_skill="attack_discovery",
        route_plan_shadow=shadow,
        coverage_id=COV_Q046_PILOT_COVERAGE_ID,
    )
    assert result.authority_fallback_reason == FALLBACK_MISSING_THRESHOLD_REF
    assert "threshold_ref" not in shadow["route_plan_parameters"]
