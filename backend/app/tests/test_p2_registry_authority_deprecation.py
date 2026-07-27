from __future__ import annotations

from typing import Any

import pytest

from app.api.routes_chat import chat
from app.routing.route_authority_allowlist import COV_Q046_PILOT_COVERAGE_ID
from app.routing.registry_route_authority import resolve_effective_routing_skill
from app.schemas.requests import ChatRequest
from app.tests.test_p2_known_path_authority import (
    _CANONICAL_OKTA_FAILED_LOGIN_SKILL,
    _cov_q046_candidate_with_slots,
    _enable_pilot_authority,
)
from app.tests.test_route_plan_stage3k_r2 import _patch_common_chat_dependencies


def test_resolve_effective_skill_uses_registry_mirror_when_legacy_authority_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.settings.legacy_selected_skill_authority_enabled", False)
    resolution = resolve_effective_routing_skill(
        selected_skill="knowledge_recall",
        route_authority={
            "authority_decision": "applied",
            "planning_primary_skill": "aggregate_and_rank",
        },
        primary_operation="aggregate_and_rank",
    )
    assert resolution["legacy_intent_authority"] is False
    assert resolution["effective_skill"] == "attack_discovery"
    assert resolution["skill_resolution"] == "registry_operation_mirror"


def test_p2_9_workflow_uses_mirrored_skill_for_spl_when_legacy_authority_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_pilot_authority(monkeypatch)
    monkeypatch.setattr("app.config.settings.legacy_selected_skill_authority_enabled", False)
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery", disable_deterministic_route_plan=True)
    monkeypatch.setattr(
        "app.api.routes_chat._route_plan_shadow_candidate",
        lambda query: _cov_q046_candidate_with_slots(),
    )

    response = chat(ChatRequest(message="Find top 10 users with failed Okta logins in the last 24 hours."))

    assert response.selected_skill == _CANONICAL_OKTA_FAILED_LOGIN_SKILL
    assert response.legacy_intent_authority is False
    assert response.routing_skill_resolution is not None
    assert response.routing_skill_resolution["effective_skill"] == _CANONICAL_OKTA_FAILED_LOGIN_SKILL
    assert response.routing_skill_resolution["skill_resolution"] == "control_plane_route_adjudication"
    assert response.candidate_spl is not None
    assert response.route_authority is not None
    assert response.route_authority.get("authority_decision") == "applied"
