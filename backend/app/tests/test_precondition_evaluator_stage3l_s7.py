"""Stage 3L-S7.1: Pure hard-precondition evaluator tests."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from app.routing.precondition_evaluator import (
    FINDING_DETECTION_UNVETTED,
    FINDING_LOOKUP_STALE,
    FINDING_MISSING_CONFIGURED_DETECTION,
    FINDING_MISSING_CONFIGURED_LOOKUP,
    FINDING_MISSING_EVIDENCE_CONTRACT,
    FINDING_MISSING_PRIMARY_FIXTURE,
    FINDING_MISSING_REQUIRED_THRESHOLD_REF,
    FINDING_MISSING_REQUIRED_TIME_WINDOW,
    FINDING_MISSING_TEMPLATE,
    FINDING_UNSUPPORTED_SOURCE_CLASS,
    PRECONDITION_DETECTION_REGISTERED,
    PRECONDITION_DETECTION_VETTED,
    PRECONDITION_LOOKUP_AVAILABLE,
    PRECONDITION_LOOKUP_FRESH,
    HARD_PRECONDITION_IDS,
    HardPreconditionDependencyState,
    evaluate_hard_preconditions,
)
from app.routing.route_plan_models import RouteStatus


def _minimal_route_plan(**overrides: object) -> dict:
    base = {
        "route_status": RouteStatus.ROUTE_READY.value,
        "primary_skill": "aggregate_and_rank",
        "operation_type": "top_n",
        "pattern_id": "test_pattern",
        "source_class": "okta_authentication_logs",
        "time_window": {"earliest": "-24h", "latest": "now"},
        "parameters": {},
        "hard_preconditions": [],
    }
    base.update(overrides)
    return base


def _all_required_state(**overrides: object) -> HardPreconditionDependencyState:
    base = {
        "require_template": True,
        "require_evidence_contract": True,
        "require_lookup": True,
        "require_detection": True,
        "require_source_class": True,
        "require_threshold_policy": True,
        "require_time_window": True,
        "require_primary_fixture": True,
        "template_available": True,
        "template_sample_only": False,
        "evidence_contract_available": True,
        "lookup_available": True,
        "lookup_fresh": True,
        "detection_registered": True,
        "detection_vetted": True,
        "source_class_supported": True,
        "threshold_policy_present": True,
        "time_window_present": True,
        "primary_fixture_available": True,
    }
    base.update(overrides)
    return HardPreconditionDependencyState(**base)


def test_all_preconditions_pass() -> None:
    plan = _minimal_route_plan(
        parameters={"threshold_ref": "default_failed_login_baseline"},
    )
    result = evaluate_hard_preconditions(plan, _all_required_state())
    assert result.route_status == RouteStatus.ROUTE_READY.value
    assert result.dependency_readiness == "ready"
    assert result.preconditions_failed == []
    assert set(result.preconditions_checked) == set(HARD_PRECONDITION_IDS)
    assert set(result.preconditions_passed) == set(HARD_PRECONDITION_IDS)
    assert result.blocking_findings == []


def test_missing_template_blocks() -> None:
    result = evaluate_hard_preconditions(
        _minimal_route_plan(),
        _all_required_state(template_available=False),
    )
    assert result.route_status == RouteStatus.CANNOT_ROUTE_MISSING_TEMPLATE.value
    assert FINDING_MISSING_TEMPLATE in result.blocking_findings


def test_sample_only_template_blocks() -> None:
    result = evaluate_hard_preconditions(
        _minimal_route_plan(),
        _all_required_state(template_sample_only=True),
    )
    assert result.route_status == RouteStatus.CANNOT_ROUTE_MISSING_TEMPLATE.value
    assert FINDING_MISSING_TEMPLATE in result.blocking_findings


def test_missing_evidence_contract_blocks() -> None:
    result = evaluate_hard_preconditions(
        _minimal_route_plan(),
        _all_required_state(evidence_contract_available=False),
    )
    assert result.route_status == RouteStatus.CANNOT_ROUTE_MISSING_EVIDENCE_CONTRACT.value
    assert FINDING_MISSING_EVIDENCE_CONTRACT in result.blocking_findings


def test_missing_lookup_blocks() -> None:
    result = evaluate_hard_preconditions(
        _minimal_route_plan(),
        _all_required_state(lookup_available=False, lookup_fresh=True),
    )
    assert result.route_status == RouteStatus.CANNOT_ROUTE_MISSING_LOOKUP.value
    assert FINDING_MISSING_CONFIGURED_LOOKUP in result.blocking_findings


def test_stale_lookup_blocks() -> None:
    result = evaluate_hard_preconditions(
        _minimal_route_plan(),
        _all_required_state(lookup_available=True, lookup_fresh=False),
    )
    assert result.route_status == RouteStatus.CANNOT_ROUTE_LOOKUP_STALE.value
    assert FINDING_LOOKUP_STALE in result.blocking_findings
    assert PRECONDITION_LOOKUP_FRESH in result.preconditions_failed


def test_missing_detection_blocks() -> None:
    result = evaluate_hard_preconditions(
        _minimal_route_plan(),
        _all_required_state(detection_registered=False, detection_vetted=True),
    )
    assert result.route_status == RouteStatus.CANNOT_ROUTE_MISSING_DETECTION.value
    assert FINDING_MISSING_CONFIGURED_DETECTION in result.blocking_findings


def test_unvetted_detection_blocks() -> None:
    result = evaluate_hard_preconditions(
        _minimal_route_plan(),
        _all_required_state(detection_registered=True, detection_vetted=False),
    )
    assert result.route_status == RouteStatus.CANNOT_ROUTE_UNVETTED_DETECTION.value
    assert FINDING_DETECTION_UNVETTED in result.blocking_findings
    assert PRECONDITION_DETECTION_VETTED in result.preconditions_failed


def test_unsupported_source_class_blocks() -> None:
    result = evaluate_hard_preconditions(
        _minimal_route_plan(),
        _all_required_state(source_class_supported=False),
    )
    assert result.route_status == RouteStatus.CANNOT_ROUTE_UNSUPPORTED_SOURCE.value
    assert FINDING_UNSUPPORTED_SOURCE_CLASS in result.blocking_findings


def test_missing_threshold_returns_clarification() -> None:
    result = evaluate_hard_preconditions(
        _minimal_route_plan(parameters={}),
        _all_required_state(threshold_policy_present=False),
    )
    assert result.route_status == RouteStatus.CLARIFICATION_REQUIRED.value
    assert FINDING_MISSING_REQUIRED_THRESHOLD_REF in result.blocking_findings


def test_missing_threshold_ref_on_plan_returns_clarification() -> None:
    result = evaluate_hard_preconditions(
        _minimal_route_plan(parameters={}, time_window={"earliest": "-24h", "latest": "now"}),
        HardPreconditionDependencyState(
            require_threshold_policy=True,
            threshold_policy_present=True,
            require_time_window=False,
        ),
    )
    assert result.route_status == RouteStatus.CLARIFICATION_REQUIRED.value
    assert FINDING_MISSING_REQUIRED_THRESHOLD_REF in result.blocking_findings


def test_missing_time_window_returns_clarification() -> None:
    result = evaluate_hard_preconditions(
        _minimal_route_plan(time_window={}),
        HardPreconditionDependencyState(
            require_time_window=True,
            time_window_present=False,
        ),
    )
    assert result.route_status == RouteStatus.CLARIFICATION_REQUIRED.value
    assert FINDING_MISSING_REQUIRED_TIME_WINDOW in result.blocking_findings


def test_missing_primary_fixture_blocks_authority_readiness() -> None:
    result = evaluate_hard_preconditions(
        _minimal_route_plan(),
        _all_required_state(primary_fixture_available=False),
    )
    assert result.route_status == RouteStatus.CANNOT_ROUTE_MISSING_PRIMARY_FIXTURE.value
    assert FINDING_MISSING_PRIMARY_FIXTURE in result.blocking_findings
    assert result.dependency_readiness == "blocked"


def test_multiple_failures_all_reported() -> None:
    result = evaluate_hard_preconditions(
        _minimal_route_plan(),
        _all_required_state(
            template_available=False,
            lookup_available=False,
            lookup_fresh=False,
            detection_registered=False,
        ),
    )
    assert len(result.preconditions_failed) >= 4
    assert FINDING_MISSING_TEMPLATE in result.blocking_findings
    assert FINDING_MISSING_CONFIGURED_LOOKUP in result.blocking_findings
    assert FINDING_LOOKUP_STALE in result.blocking_findings
    assert FINDING_MISSING_CONFIGURED_DETECTION in result.blocking_findings
    assert PRECONDITION_LOOKUP_AVAILABLE in result.preconditions_failed
    assert PRECONDITION_LOOKUP_FRESH in result.preconditions_failed
    assert PRECONDITION_DETECTION_REGISTERED in result.preconditions_failed


def test_clarification_only_readiness() -> None:
    result = evaluate_hard_preconditions(
        _minimal_route_plan(parameters={}, time_window={}),
        HardPreconditionDependencyState(
            require_threshold_policy=True,
            require_time_window=True,
            threshold_policy_present=False,
            time_window_present=False,
        ),
    )
    assert result.route_status == RouteStatus.CLARIFICATION_REQUIRED.value
    assert result.dependency_readiness == "clarification_required"
    assert FINDING_MISSING_REQUIRED_THRESHOLD_REF in result.blocking_findings
    assert FINDING_MISSING_REQUIRED_TIME_WINDOW in result.blocking_findings


def test_dependency_state_from_dict() -> None:
    result = evaluate_hard_preconditions(
        _minimal_route_plan(),
        {"require_template": True, "template_available": False},
    )
    assert result.route_status == RouteStatus.CANNOT_ROUTE_MISSING_TEMPLATE.value


def test_model_dump_round_trip() -> None:
    plan = _minimal_route_plan(parameters={"threshold_ref": "default_failed_login_baseline"})
    result = evaluate_hard_preconditions(plan, _all_required_state())
    payload = result.model_dump()
    assert payload["route_status"] == RouteStatus.ROUTE_READY.value
    assert isinstance(payload["preconditions_checked"], list)


def test_evaluator_module_has_no_forbidden_imports() -> None:
    module_path = Path(__file__).resolve().parents[1] / "routing" / "precondition_evaluator.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    forbidden_roots = {
        "app.api",
        "app.connectors",
        "app.mcp",
        "app.synthesis",
        "app.demo",
        "splunk",
    }
    full_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            full_imports.append(node.module)
    for module in full_imports:
        for forbidden in forbidden_roots:
            assert not module.startswith(forbidden), f"forbidden import {module}"
    assert "app.routing.route_plan_models" in full_imports or any(
        i == "app" for i in imports
    )


def test_evaluator_does_not_import_routes_chat() -> None:
    from app.routing import precondition_evaluator

    source = inspect.getsource(precondition_evaluator)
    assert "routes_chat" not in source
    assert "mcp" not in source.lower() or "app.connectors" not in source
