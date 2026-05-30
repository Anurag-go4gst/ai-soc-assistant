"""Stage 3L-S7.2: Registry-backed precondition dependency state tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import settings
from app.coverage.coverage_loader import coverage_for_id
from app.routing.precondition_dependency_state import (
    PRIMARY_FIXTURE_BLOCKED_SKILLS,
    build_hard_precondition_dependency_state,
    build_hard_precondition_dependency_state_for_coverage,
)
from app.routing.precondition_evaluator import (
    HardPreconditionDependencyState,
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
    evaluate_hard_preconditions,
)
from app.routing.route_plan_models import RouteStatus

_IOC_FIXTURE = Path(__file__).resolve().parents[1] / "intel" / "fixtures" / "ioc_registry.sample.json"
_DETECTION_FIXTURE = Path(__file__).resolve().parents[1] / "detections" / "fixtures" / "detection_registry.sample.json"

COV_Q046 = "cov.q046.excessive_failed_logins_sample"
COV_Q007 = "cov.q007.dga_detection_binding"
COV_IOC_DOMAIN = "cov.q036.known_malicious_domains"


def _q046_plan(**overrides: object) -> dict:
    entry = coverage_for_id(COV_Q046)
    assert entry is not None
    plan = {
        **entry.route_plan_shape,
        "template_ref": entry.template_ref,
        "evidence_contract_ref": entry.evidence_contract_ref,
        "time_window": {"earliest": "-24h", "latest": "now"},
        "parameters": dict(entry.route_plan_shape.get("parameters") or {}),
    }
    plan.update(overrides)
    return plan


def test_cov_q046_builds_registry_backed_dependency_state() -> None:
    entry = coverage_for_id(COV_Q046)
    assert entry is not None
    plan = _q046_plan(parameters={"threshold_ref": "default_failed_login_baseline"})

    state = build_hard_precondition_dependency_state(plan, entry)

    assert state.require_template is True
    assert state.require_evidence_contract is True
    assert state.template_available is True
    assert state.template_sample_only is True
    assert state.evidence_contract_available is True
    assert state.require_threshold_policy is True
    assert state.threshold_policy_present is True
    assert state.require_time_window is True
    assert state.time_window_present is True


def test_missing_template_ref_marks_template_unavailable() -> None:
    state = build_hard_precondition_dependency_state(
        {"template_ref": "nonexistent.template.ref"},
        None,
    )
    assert state.template_available is False
    result = evaluate_hard_preconditions(
        {"template_ref": "nonexistent.template.ref"},
        state,
    )
    assert result.route_status == RouteStatus.CANNOT_ROUTE_MISSING_TEMPLATE.value
    assert FINDING_MISSING_TEMPLATE in result.blocking_findings


def test_missing_evidence_contract_marks_unavailable() -> None:
    state = build_hard_precondition_dependency_state(
        {"evidence_contract_ref": "unknown:contract:ref"},
        None,
    )
    assert state.evidence_contract_available is False
    result = evaluate_hard_preconditions(
        {"evidence_contract_ref": "unknown:contract:ref"},
        state,
    )
    assert result.route_status == RouteStatus.CANNOT_ROUTE_MISSING_EVIDENCE_CONTRACT.value
    assert FINDING_MISSING_EVIDENCE_CONTRACT in result.blocking_findings


def test_ioc_lookup_present_and_fresh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ioc_registry_enabled", True)
    monkeypatch.setattr(settings, "ioc_registry_path", str(_IOC_FIXTURE))

    entry = coverage_for_id(COV_IOC_DOMAIN)
    assert entry is not None
    plan = {**entry.route_plan_shape, "lookup_ref": entry.lookup_ref}

    state = build_hard_precondition_dependency_state(plan, entry)
    assert state.require_lookup is True
    assert state.lookup_available is True
    assert state.lookup_fresh is True

    result = evaluate_hard_preconditions(plan, state)
    assert result.route_status == RouteStatus.ROUTE_READY.value


def test_ioc_lookup_stale(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    stale_payload = json.loads(_IOC_FIXTURE.read_text(encoding="utf-8"))
    stale_payload["sources"][0]["last_refreshed"] = "2020-01-01T00:00:00Z"
    stale_payload["sources"][0]["max_staleness_hours"] = 1
    stale_path = tmp_path / "ioc_stale.json"
    stale_path.write_text(json.dumps(stale_payload), encoding="utf-8")

    monkeypatch.setattr(settings, "ioc_registry_enabled", True)
    monkeypatch.setattr(settings, "ioc_registry_path", str(stale_path))

    entry = coverage_for_id(COV_IOC_DOMAIN)
    assert entry is not None
    plan = {**entry.route_plan_shape, "lookup_ref": entry.lookup_ref}
    state = build_hard_precondition_dependency_state(plan, entry)

    assert state.lookup_available is True
    assert state.lookup_fresh is False

    result = evaluate_hard_preconditions(plan, state)
    assert result.route_status == RouteStatus.CANNOT_ROUTE_LOOKUP_STALE.value
    assert FINDING_LOOKUP_STALE in result.blocking_findings


def test_ioc_lookup_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ioc_registry_enabled", True)
    monkeypatch.setattr(settings, "ioc_registry_path", str(_IOC_FIXTURE))

    state = build_hard_precondition_dependency_state(
        {"lookup_ref": "lookup_that_does_not_exist"},
        None,
    )
    assert state.lookup_available is False
    result = evaluate_hard_preconditions({"lookup_ref": "lookup_that_does_not_exist"}, state)
    assert result.route_status == RouteStatus.CANNOT_ROUTE_MISSING_LOOKUP.value
    assert FINDING_MISSING_CONFIGURED_LOOKUP in result.blocking_findings


def test_detection_registered_and_vetted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "detection_registry_enabled", True)
    monkeypatch.setattr(settings, "detection_registry_path", str(_DETECTION_FIXTURE))

    entry = coverage_for_id(COV_Q007)
    assert entry is not None
    plan = {
        **entry.route_plan_shape,
        "detection_ref": entry.detection_ref,
        "detection_family": entry.detection_family,
        "time_window": {"earliest": "-24h", "latest": "now"},
    }
    state = build_hard_precondition_dependency_state(plan, entry)

    assert state.detection_registered is True
    assert state.detection_vetted is True


def test_detection_unregistered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "detection_registry_enabled", True)
    monkeypatch.setattr(settings, "detection_registry_path", str(_DETECTION_FIXTURE))

    state = build_hard_precondition_dependency_state(
        {"detection_ref": "soc.unknown.detection"},
        None,
    )
    assert state.detection_registered is False
    result = evaluate_hard_preconditions({"detection_ref": "soc.unknown.detection"}, state)
    assert result.route_status == RouteStatus.CANNOT_ROUTE_MISSING_DETECTION.value
    assert FINDING_MISSING_CONFIGURED_DETECTION in result.blocking_findings


def test_detection_unvetted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from app.detections.detection_registry import clear_detection_registry_cache

    payload = json.loads(_DETECTION_FIXTURE.read_text(encoding="utf-8"))
    for record in payload["detections"]:
        if record.get("detection_ref") == "soc.dga.v1":
            record["vetting_status"] = "unvetted"
    path = tmp_path / "detection_unvetted.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(settings, "detection_registry_enabled", True)
    monkeypatch.setattr(settings, "detection_registry_path", str(path))
    clear_detection_registry_cache()

    state = build_hard_precondition_dependency_state(
        {"detection_ref": "soc.dga.v1", "detection_family": "dga"},
        None,
    )
    assert state.detection_registered is True
    assert state.detection_vetted is False

    result = evaluate_hard_preconditions({"detection_ref": "soc.dga.v1"}, state)
    assert result.route_status == RouteStatus.CANNOT_ROUTE_UNVETTED_DETECTION.value
    assert FINDING_DETECTION_UNVETTED in result.blocking_findings


def test_source_class_unsupported() -> None:
    state = build_hard_precondition_dependency_state(
        {"source_class": "unsupported_custom_source"},
        None,
    )
    assert state.source_class_supported is False
    result = evaluate_hard_preconditions({"source_class": "unsupported_custom_source"}, state)
    assert result.route_status == RouteStatus.CANNOT_ROUTE_UNSUPPORTED_SOURCE.value
    assert FINDING_UNSUPPORTED_SOURCE_CLASS in result.blocking_findings


def test_missing_threshold_ref_sets_require_false() -> None:
    entry = coverage_for_id(COV_Q046)
    assert entry is not None
    plan = _q046_plan(parameters={})
    state = build_hard_precondition_dependency_state(plan, entry)
    assert state.require_threshold_policy is False
    assert state.threshold_policy_present is False


def test_missing_time_window_sets_present_false() -> None:
    entry = coverage_for_id(COV_Q046)
    assert entry is not None
    plan = _q046_plan(time_window={}, parameters={})
    state = build_hard_precondition_dependency_state(plan, entry)
    assert state.time_window_present is False
    result = evaluate_hard_preconditions(
        plan,
        HardPreconditionDependencyState(
            require_time_window=True,
            time_window_present=state.time_window_present,
        ),
    )
    assert result.route_status == RouteStatus.CLARIFICATION_REQUIRED.value
    assert FINDING_MISSING_REQUIRED_TIME_WINDOW in result.blocking_findings


def test_primary_fixture_blocked_skills_remain_unavailable() -> None:
    for skill in PRIMARY_FIXTURE_BLOCKED_SKILLS:
        state = build_hard_precondition_dependency_state({"primary_skill": skill}, None)
        assert state.require_primary_fixture is True
        assert state.primary_fixture_available is False
        result = evaluate_hard_preconditions({"primary_skill": skill}, state)
        assert result.route_status == RouteStatus.CANNOT_ROUTE_MISSING_PRIMARY_FIXTURE.value
        assert FINDING_MISSING_PRIMARY_FIXTURE in result.blocking_findings


def test_cov_q007_blocked_when_detection_registry_disabled() -> None:
    entry = coverage_for_id(COV_Q007)
    assert entry is not None
    plan = {
        **entry.route_plan_shape,
        "detection_ref": entry.detection_ref,
        "time_window": {"earliest": "-24h", "latest": "now"},
    }
    state = build_hard_precondition_dependency_state(plan, entry)
    assert state.detection_registered is False
    assert state.detection_vetted is False

    result = evaluate_hard_preconditions(plan, state)
    assert result.route_status == RouteStatus.CANNOT_ROUTE_MISSING_DETECTION.value
    assert FINDING_MISSING_CONFIGURED_DETECTION in result.blocking_findings


def _q007_plan() -> dict:
    entry = coverage_for_id(COV_Q007)
    assert entry is not None
    return {
        **entry.route_plan_shape,
        "detection_ref": entry.detection_ref,
        "time_window": {"earliest": "-24h", "latest": "now"},
    }


def test_cov_q007_integration_detection_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "detection_registry_enabled", True)
    monkeypatch.setattr(settings, "detection_registry_path", str(_DETECTION_FIXTURE))

    plan = _q007_plan()
    state = build_hard_precondition_dependency_state(plan, coverage_for_id(COV_Q007))
    result = evaluate_hard_preconditions(plan, state)
    assert result.route_status == RouteStatus.ROUTE_READY.value


def test_cov_q046_integration_sample_template_blocks() -> None:
    plan = _q046_plan(parameters={"threshold_ref": "default_failed_login_baseline"})
    entry = coverage_for_id(COV_Q046)
    state = build_hard_precondition_dependency_state(plan, entry)
    result = evaluate_hard_preconditions(plan, state)
    assert result.route_status == RouteStatus.CANNOT_ROUTE_MISSING_TEMPLATE.value
    assert FINDING_MISSING_TEMPLATE in result.blocking_findings


def test_cov_q046_clarification_when_threshold_required_but_absent() -> None:
    plan = _q046_plan(parameters={}, time_window={"earliest": "-24h", "latest": "now"})
    entry = coverage_for_id(COV_Q046)
    state = build_hard_precondition_dependency_state(plan, entry)
    assert state.require_threshold_policy is False
    result = evaluate_hard_preconditions(plan, state)
    assert FINDING_MISSING_REQUIRED_THRESHOLD_REF not in result.blocking_findings


def test_ioc_negative_preflight_alignment_when_registry_disabled() -> None:
    entry = coverage_for_id("cov.q004.known_malicious_ips")
    assert entry is not None
    plan = {**entry.route_plan_shape, "lookup_ref": entry.lookup_ref}
    state = build_hard_precondition_dependency_state(plan, entry)
    assert state.lookup_available is False
    result = evaluate_hard_preconditions(plan, state)
    assert result.route_status == RouteStatus.CANNOT_ROUTE_MISSING_LOOKUP.value


def test_dependency_state_module_has_no_forbidden_imports() -> None:
    import ast

    module_path = Path(__file__).resolve().parents[1] / "routing" / "precondition_dependency_state.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    full_imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            full_imports.append(node.module)
    forbidden = ("app.api", "app.connectors", "app.mcp", "app.synthesis")
    for module in full_imports:
        for prefix in forbidden:
            assert not module.startswith(prefix), module
