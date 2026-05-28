"""Stage 3K-Q4 pattern coverage pack tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import settings
from app.coverage.coverage_loader import (
    clear_pattern_coverage_cache,
    coverage_for_id,
    coverage_for_question,
    coverage_for_skill,
    entry_declares_dependency_missing,
    known_detection_refs,
    known_evidence_contract_refs,
    known_lookup_refs,
    known_template_refs,
    list_coverage,
    load_pattern_coverage_manifest,
    resolve_evidence_contract_ref,
)
from app.coverage.coverage_models import CoverageReadiness
from app.detections.detection_binder import bind_detection
from app.detections.detection_registry import clear_detection_registry_cache
from app.intel.ioc_lookup import (
    BLOCK_CANNOT_ROUTE_LOOKUP_STALE,
    BLOCK_LOOKUP_STALE,
    preflight_ioc_requirements,
)
from app.intel.ioc_registry import clear_ioc_registry_cache
from app.routing.route_plan_models import PreflightContext, RouteStatus
from app.routing.route_plan_preflight import preflight_route_plan
from app.spl.template_matcher import match_route_plan_to_template
from app.spl.template_registry import get_spl_template

_MANIFEST = Path(__file__).resolve().parents[1] / "coverage" / "pattern_coverage_v1.json"
_IOC_FIXTURE = Path(__file__).resolve().parents[1] / "intel" / "fixtures" / "ioc_registry.sample.json"
_DETECTION_FIXTURE = Path(__file__).resolve().parents[1] / "detections" / "fixtures" / "detection_registry.sample.json"


@pytest.fixture(autouse=True)
def _reset_caches() -> None:
    clear_pattern_coverage_cache()
    clear_ioc_registry_cache()
    clear_detection_registry_cache()
    yield
    clear_pattern_coverage_cache()
    clear_ioc_registry_cache()
    clear_detection_registry_cache()


def test_manifest_loads_and_conforms_to_schema() -> None:
    manifest = load_pattern_coverage_manifest(_MANIFEST)

    assert manifest.pack_version == "stage3k_q4_v1"
    assert manifest.coe_synthetic_fixture is True
    assert manifest.production_execution is False


def test_coverage_ids_unique_and_count_in_range() -> None:
    entries = list_coverage()

    ids = [entry.coverage_id for entry in entries]
    assert len(ids) == len(set(ids))
    assert 8 <= len(entries) <= 10


def test_required_coverage_categories_present() -> None:
    groups = {entry.coverage_group for entry in list_coverage()}

    assert "template_only" in groups
    assert "ioc_dependent" in groups
    assert "detection_dependent" in groups
    assert "multi_signal" in groups
    assert "negative_cannot_route" in groups


def test_entry_references_resolve_or_dependency_missing() -> None:
    for entry in list_coverage():
        if entry.template_ref is not None:
            assert entry.template_ref in known_template_refs()

        if entry.lookup_ref is not None:
            assert entry.lookup_ref in known_lookup_refs()

        if entry.detection_ref is not None:
            assert entry.detection_ref in known_detection_refs(bindable_only=True)

        if entry_declares_dependency_missing(entry):
            continue
        assert resolve_evidence_contract_ref(entry.evidence_contract_ref)


def test_template_only_entries_have_no_executable_spl_in_manifest() -> None:
    manifest_blob = _MANIFEST.read_text(encoding="utf-8")

    for entry in list_coverage():
        if entry.coverage_group != "template_only":
            continue
        shape_blob = json.dumps(entry.route_plan_shape)
        assert "search index=" not in shape_blob
        assert "| stats " not in shape_blob
        assert entry.coverage_id in manifest_blob
        assert entry.governance.execution_eligible is False
        assert entry.governance.spl_execution_enabled is False


def test_template_backed_entries_keep_execution_eligible_false() -> None:
    for entry in list_coverage():
        if entry.template_ref is None:
            continue
        assert entry.governance.execution_eligible is False


def test_sample_template_matches_route_plan_shape() -> None:
    entry = coverage_for_id("cov.q046.excessive_failed_logins_sample")
    assert entry is not None

    match = match_route_plan_to_template(entry.route_plan_shape)

    assert match.matched is True
    assert match.matched_template_id == entry.template_ref
    assert match.production_executable is False


def test_ioc_entries_declare_local_lookup_dependency() -> None:
    for entry in list_coverage():
        if entry.coverage_group != "ioc_dependent":
            continue
        assert entry.lookup_ref is not None
        assert entry.readiness == CoverageReadiness.IOC_DEPENDENT


def test_stale_ioc_uses_q2_stale_blocking_reasons(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stale_payload = json.loads(_IOC_FIXTURE.read_text(encoding="utf-8"))
    stale_payload["sources"][0]["last_refreshed"] = "2020-01-01T00:00:00Z"
    stale_payload["sources"][0]["max_staleness_hours"] = 1
    stale_path = tmp_path / "ioc_stale.json"
    stale_path.write_text(json.dumps(stale_payload), encoding="utf-8")

    monkeypatch.setattr(settings, "ioc_registry_enabled", True)
    monkeypatch.setattr(settings, "ioc_registry_path", str(stale_path))

    block = preflight_ioc_requirements(lookup_required=True, registry_path=stale_path)
    assert block is not None
    assert block.blocking_reason == BLOCK_CANNOT_ROUTE_LOOKUP_STALE

    result = preflight_route_plan(
        "Which hosts contacted known malicious IPs today?",
        PreflightContext(configured_lookups=set()),
    )
    assert result.route_status == RouteStatus.CANNOT_ROUTE_MISSING_LOOKUP
    assert BLOCK_CANNOT_ROUTE_LOOKUP_STALE in result.blocking_findings
    assert BLOCK_LOOKUP_STALE in result.blocking_findings


def test_detection_entries_bind_through_q3_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "detection_registry_enabled", True)

    binding = bind_detection("dga", {"query": "dns"}, registry_path=_DETECTION_FIXTURE)
    assert binding.bound is True
    assert binding.detection_ref == "soc.dga.v1"

    entry = coverage_for_id("cov.q007.dga_detection_binding")
    assert entry is not None
    assert entry.detection_ref == binding.detection_ref


def test_negative_notable_case_preflight_matches_manifest() -> None:
    entry = coverage_for_id("cov.q045.notable_missing_context")
    assert entry is not None

    result = preflight_route_plan(entry.question, PreflightContext())

    assert result.route_status is not None
    assert result.route_status.value == entry.expected_route_status
    assert "notable_id" in result.missing_slots


def test_ioc_negative_preflight_when_registry_disabled() -> None:
    entry = coverage_for_id("cov.q004.known_malicious_ips")
    assert entry is not None

    result = preflight_route_plan(
        entry.question,
        PreflightContext(configured_lookups=set()),
    )

    assert result.route_status == RouteStatus.CANNOT_ROUTE_MISSING_LOOKUP
    assert any("missing_configured_lookup" in finding for finding in result.blocking_findings)


def test_every_entry_execution_authorized_false() -> None:
    for entry in list_coverage():
        gov = entry.governance
        assert gov.execution_authorized is False
        assert gov.mcp_execution_enabled is False
        assert gov.llm_final_synthesis_enabled is False
        assert gov.answer_guard_enabled is False


def test_helpers_filter_coverage() -> None:
    assert coverage_for_question("q0.q002")
    assert coverage_for_skill("aggregate_and_rank")
    assert coverage_for_id("cov.q002.top_outbound_source_ips") is not None


def test_no_live_llm_or_answer_guard_imports_in_coverage_package() -> None:
    package_root = Path(__file__).resolve().parents[1] / "coverage"
    for path in package_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "adapt_llm_output" not in text
        assert "answer_guard" not in text.lower() or path.name == "coverage_models.py"


def test_auth_spike_template_exists_without_manifest_spl() -> None:
    entry = coverage_for_id("cov.q062.auth_failed_login_spike_raw")
    assert entry is not None
    template = get_spl_template(entry.template_ref)
    assert template is not None
    manifest_text = _MANIFEST.read_text(encoding="utf-8")
    assert template.spl_text not in manifest_text
