"""Stage 3L-S5.1: Committed manifest promotion audit."""

from __future__ import annotations

from app.coverage.manifest_promotion_audit import audit_committed_manifest
from app.coverage.manifest_promotion_gates import evaluate_promotion_gates
from app.coverage.coverage_loader import coverage_for_id


def test_committed_manifest_audit_all_pass_with_coe_signoff() -> None:
    report = audit_committed_manifest(coe_signoff_recorded=True)
    assert report["entry_count"] >= 1
    assert report["all_manifest_integrity_ok"] is True


def test_cov_q046_authority_pilot_ready_when_coe_signed() -> None:
    entry = coverage_for_id("cov.q046.excessive_failed_logins_sample")
    assert entry is not None
    result = evaluate_promotion_gates(entry, mode="committed", coe_signoff_recorded=True)
    assert result.manifest_integrity_ok is True
    assert result.authority_pilot_ready is True


def test_draft_mode_still_blocks_duplicate_manifest_id() -> None:
    entry = coverage_for_id("cov.q046.excessive_failed_logins_sample")
    assert entry is not None
    result = evaluate_promotion_gates(entry, mode="draft", coe_signoff_recorded=True)
    assert result.manifest_copy_ready is False
    duplicate = [c for c in result.checks if c.gate_id == "coverage_id_not_in_manifest"]
    assert duplicate and duplicate[0].passed is False
