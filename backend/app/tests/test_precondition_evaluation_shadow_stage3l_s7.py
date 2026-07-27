"""Stage 3L-S7.3: Hard-precondition evaluation on route_plan_shadow (observational)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.api.routes_chat import chat
from app.api.routes_scenarios import run_demo_scenario_fixture
from app.config import settings
from app.coverage.coverage_loader import coverage_for_id
from app.routing.precondition_evaluation_shadow import (
    apply_precondition_evaluation_to_shadow,
)
from app.routing.precondition_evaluator import FINDING_MISSING_TEMPLATE
from app.routing.route_plan_models import RouteStatus
from app.schemas.requests import ChatRequest
from app.tests.test_p2_known_path_authority import _CANONICAL_OKTA_FAILED_LOGIN_SKILL
from app.tests.test_route_plan_stage3k_r2 import _patch_common_chat_dependencies, _valid_route_plan_candidate

COV_Q046 = "cov.q046.excessive_failed_logins_sample"
COV_Q007 = "cov.q007.dga_detection_binding"


def test_shadow_cov_q046_precondition_evaluation_blocks_sample_template() -> None:
    shadow = {
        "primary_skill": "threshold_anomaly",
        "pattern_id": "top_failed_okta_login_users",
        "route_plan_parameters": {"threshold_ref": "default_failed_login_baseline"},
        "route_plan_time_window": {"earliest": "-24h", "latest": "now"},
        "route_authority_compare": {"coverage_id_resolved": COV_Q046},
    }
    payload = apply_precondition_evaluation_to_shadow(shadow)

    assert payload["observation_only"] is True
    assert payload["evaluation_skipped"] is False
    assert payload["coverage_id"] == COV_Q046
    assert payload["route_status"] == RouteStatus.CANNOT_ROUTE_MISSING_TEMPLATE.value
    assert FINDING_MISSING_TEMPLATE in payload["blocking_findings"]
    assert shadow["precondition_evaluation"] is payload


def test_shadow_precondition_does_not_mutate_primary_skill() -> None:
    shadow = {
        "primary_skill": "attack_discovery",
        "pattern_id": "top_failed_okta_login_users",
        "route_authority_compare": {"coverage_id_resolved": COV_Q046},
    }
    apply_precondition_evaluation_to_shadow(shadow)
    assert shadow["primary_skill"] == "attack_discovery"


def test_shadow_skips_when_insufficient_plan() -> None:
    shadow = {"route_authority_compare": {"coverage_id_resolved": COV_Q046}}
    payload = apply_precondition_evaluation_to_shadow(shadow)
    assert payload["evaluation_skipped"] is True
    assert payload["skip_reason"] == "insufficient_shadow_route_plan"


def test_cov_q007_shadow_blocked_without_detection_registry() -> None:
    entry = coverage_for_id(COV_Q007)
    assert entry is not None
    shadow = {
        "primary_skill": entry.route_plan_shape.get("primary_skill"),
        "pattern_id": entry.route_plan_shape.get("pattern_id"),
        "detection_ref": entry.detection_ref,
        "route_plan_time_window": {"earliest": "-24h", "latest": "now"},
        "route_authority_compare": {"coverage_id_resolved": COV_Q007},
    }
    payload = apply_precondition_evaluation_to_shadow(shadow)
    assert payload["route_status"] == RouteStatus.CANNOT_ROUTE_MISSING_DETECTION.value


def test_cov_q007_shadow_ready_when_detection_registry_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "detection_registry_enabled", True)
    monkeypatch.setattr(
        settings,
        "detection_registry_path",
        str(Path(__file__).resolve().parents[1] / "detections" / "fixtures" / "detection_registry.sample.json"),
    )
    entry = coverage_for_id(COV_Q007)
    assert entry is not None
    shadow = {
        "primary_skill": entry.route_plan_shape.get("primary_skill"),
        "pattern_id": entry.route_plan_shape.get("pattern_id"),
        "detection_ref": entry.detection_ref,
        "route_plan_time_window": {"earliest": "-24h", "latest": "now"},
        "route_authority_compare": {"coverage_id_resolved": COV_Q007},
    }
    payload = apply_precondition_evaluation_to_shadow(shadow)
    assert payload["route_status"] == RouteStatus.ROUTE_READY.value


def test_chat_includes_precondition_evaluation_without_changing_selected_skill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_common_chat_dependencies(
        monkeypatch,
        skill=_CANONICAL_OKTA_FAILED_LOGIN_SKILL,
        disable_deterministic_route_plan=True,
    )
    monkeypatch.setattr(
        "app.api.routes_chat._route_plan_shadow_candidate",
        lambda query: _valid_route_plan_candidate(),
    )

    response = chat(
        ChatRequest(message="Find the top 10 users with failed Okta login attempts in the last 24 hours.")
    )

    assert response.selected_skill == _CANONICAL_OKTA_FAILED_LOGIN_SKILL
    evaluation = response.route_plan_shadow.precondition_evaluation
    assert evaluation is not None
    assert evaluation["observation_only"] is True
    assert evaluation["evaluation_skipped"] is False
    assert "preconditions_checked" in evaluation


def test_lineage_includes_hard_preconditions_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_common_chat_dependencies(
        monkeypatch,
        skill=_CANONICAL_OKTA_FAILED_LOGIN_SKILL,
        disable_deterministic_route_plan=True,
    )
    monkeypatch.setattr(
        "app.api.routes_chat._route_plan_shadow_candidate",
        lambda query: _valid_route_plan_candidate(),
    )

    response = chat(
        ChatRequest(message="Find the top 10 users with failed Okta login attempts in the last 24 hours.")
    )

    stage_ids = [stage.stage_id for stage in response.investigation_lineage.stages]
    assert "hard_preconditions" in stage_ids
    hard_stage = next(s for s in response.investigation_lineage.stages if s.stage_id == "hard_preconditions")
    assert hard_stage.current_mode_source == "shadow"
    assert hard_stage.technical_output.get("observation_only") is True


def test_experience_center_unchanged() -> None:
    response = run_demo_scenario_fixture("failed_login_spike_app01")
    assert response.route_plan_shadow is None


def test_precondition_shadow_module_has_no_forbidden_imports() -> None:
    module_path = Path(__file__).resolve().parents[1] / "routing" / "precondition_evaluation_shadow.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    forbidden = ("app.synthesis", "app.mcp", "app.connectors.mcp")
    for module in modules:
        for prefix in forbidden:
            assert not module.startswith(prefix), module
