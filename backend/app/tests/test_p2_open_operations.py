from __future__ import annotations

from typing import Any

import pytest

from app.routing.open_operation_validation import validate_open_operation
from app.routing.route_plan_models import RouteStatus
from app.routing.route_plan_validator import validate_route_plan_candidate
from app.tests.test_route_plan_stage3k_r2 import _valid_route_plan_candidate


def test_open_operation_structural_pass_sets_proposed_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.route_plan_open_operations_enabled", True)
    candidate = _valid_route_plan_candidate()
    candidate["primary_skill"] = "custom_hunt_operation"
    candidate["operation_type"] = "ranked_review"
    candidate["pattern_id"] = "open_custom_hunt"
    candidate["post_enrichment"] = []

    result = validate_route_plan_candidate(candidate)

    assert "open_operation_structural_pass_advisory_only" in result.warnings
    plan = result.normalized_route_plan or {}
    assert plan.get("operation_provenance") == "open_proposed"
    assert plan.get("route_status") == "open_operation_proposed"
    assert result.is_valid is False


def test_open_operation_rejects_invalid_identifier(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.route_plan_open_operations_enabled", True)
    candidate = _valid_route_plan_candidate()
    candidate["primary_skill"] = "Bad-Operation"

    result = validate_route_plan_candidate(candidate)

    assert any("open_operation_invalid_identifier" in item for item in result.blocking_findings)


def test_closed_enum_when_open_operations_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.route_plan_open_operations_enabled", False)
    candidate = _valid_route_plan_candidate()
    candidate["primary_skill"] = "custom_hunt_operation"

    result = validate_route_plan_candidate(candidate)

    assert any(item.startswith("unknown_primary_skill:") for item in result.blocking_findings)


def test_seed_catalog_operation_provenance() -> None:
    candidate = _valid_route_plan_candidate()
    result = validate_route_plan_candidate(candidate)
    plan = result.normalized_route_plan or {}
    assert plan.get("operation_provenance") == "seed_catalog"
    assert plan.get("route_status") == RouteStatus.ROUTE_READY.value
