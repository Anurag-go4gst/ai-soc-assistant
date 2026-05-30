"""Stage 3L-S7.4: S5 promotion audit alignment with S7 precondition evaluator."""

from __future__ import annotations

from app.coverage.coverage_loader import coverage_for_id, list_coverage
from app.coverage.manifest_precondition_alignment import (
    audit_committed_precondition_alignment,
    evaluate_manifest_precondition_alignment,
)
from app.coverage.manifest_promotion_audit import audit_committed_manifest
from app.routing.route_plan_models import RouteStatus


def test_committed_audit_includes_precondition_alignment() -> None:
    report = audit_committed_manifest(coe_signoff_recorded=True)
    assert report["all_manifest_integrity_ok"] is True
    assert report["all_precondition_alignment_ok"] is True
    assert len(report["entries"]) == len(list_coverage())
    for item in report["entries"]:
        align = item["precondition_alignment"]
        assert align["coverage_id"] == item["coverage_id"]
        assert align["alignment_status"] in ("aligned", "documented_gap")


def test_cov_q046_documented_sample_template_gap() -> None:
    entry = coverage_for_id("cov.q046.excessive_failed_logins_sample")
    assert entry is not None
    alignment = evaluate_manifest_precondition_alignment(entry)
    assert alignment.promotion_integrity_ok is True
    assert alignment.precondition_route_status == RouteStatus.CANNOT_ROUTE_MISSING_TEMPLATE.value
    assert alignment.alignment_status == "documented_gap"
    assert "coe_fixture_sample_template_blocks_s7" in alignment.documented_gap_ids


def test_cov_q004_aligned_with_manifest_expectation() -> None:
    entry = coverage_for_id("cov.q004.known_malicious_ips")
    assert entry is not None
    alignment = evaluate_manifest_precondition_alignment(entry)
    assert alignment.matches_manifest_expectation is True
    assert alignment.alignment_status == "aligned"
    assert alignment.precondition_route_status == RouteStatus.CANNOT_ROUTE_MISSING_LOOKUP.value


def test_cov_q062_production_template_aligned() -> None:
    entry = coverage_for_id("cov.q062.auth_failed_login_spike_raw")
    assert entry is not None
    alignment = evaluate_manifest_precondition_alignment(entry)
    assert alignment.alignment_status == "aligned"
    assert alignment.precondition_route_status == RouteStatus.ROUTE_READY.value


def test_standalone_precondition_alignment_audit() -> None:
    report = audit_committed_precondition_alignment(coe_signoff_recorded=True)
    assert report["all_precondition_alignment_ok"] is True
    assert report["entry_count"] >= 10
