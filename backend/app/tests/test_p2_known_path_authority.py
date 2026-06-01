from __future__ import annotations

from typing import Any

import pytest

from app.api.routes_chat import chat
from app.routing.route_authority_allowlist import COV_Q046_PILOT_COVERAGE_ID
from app.routing.route_authority_gate import FALLBACK_COVERAGE_ID_NOT_ALLOWLISTED
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


def test_allowlisted_known_path_surfaces_operation_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_pilot_authority(monkeypatch)
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")
    monkeypatch.setattr(
        "app.api.routes_chat._route_plan_shadow_candidate",
        lambda query: _cov_q046_candidate_with_slots(),
    )

    response = chat(ChatRequest(message="Find top 10 users with failed Okta logins in the last 24 hours."))

    assert response.selected_skill == "attack_discovery"
    assert response.primary_operation == "aggregate_and_rank"
    assert response.coverage_id == COV_Q046_PILOT_COVERAGE_ID
    assert response.route_authority is not None
    assert response.route_authority["authority_decision"] == "applied"
    assert response.route_authority["authority_holder"] == "route_plan_primary_skill"
    assert response.route_authority["legacy_selected_skill_preserved"] == "attack_discovery"
    assert response.execution.executed_spl is None


def test_non_allowlisted_known_path_surfaces_fallback_without_applying(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_pilot_authority(monkeypatch)
    monkeypatch.setattr("app.config.settings.route_authority_operation_coverage_allowlist", "")
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")
    monkeypatch.setattr(
        "app.api.routes_chat._route_plan_shadow_candidate",
        lambda query: _cov_q046_candidate_with_slots(),
    )

    response = chat(ChatRequest(message="Find top 10 users with failed Okta logins in the last 24 hours."))

    assert response.selected_skill == "attack_discovery"
    assert response.primary_operation == "aggregate_and_rank"
    assert response.coverage_id == COV_Q046_PILOT_COVERAGE_ID
    assert response.route_authority is not None
    assert response.route_authority["authority_decision"] == "fallback"
    assert response.route_authority["authority_fallback_reason"] == FALLBACK_COVERAGE_ID_NOT_ALLOWLISTED
    assert response.route_authority["authority_holder"] == "legacy_selected_skill"
    assert response.execution.executed_spl is None
