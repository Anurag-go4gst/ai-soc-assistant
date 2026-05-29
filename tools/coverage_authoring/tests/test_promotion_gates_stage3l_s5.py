"""Stage 3L-S5: Q4A promotion gate evaluation."""

from __future__ import annotations

from app.coverage.coverage_loader import load_pattern_coverage_manifest

from promotion_gates import evaluate_promotion_gates
from registries import load_registry_snapshot
from test_coverage_drafter_q4a import _minimal_entry


def test_manifest_q046_fails_duplicate_gate() -> None:
    manifest = load_pattern_coverage_manifest()
    entry = next(e for e in manifest.entries if e.question_ref == "q0.q046")
    result = evaluate_promotion_gates(entry, load_registry_snapshot())
    assert not result.manifest_copy_ready
    assert any(check.gate_id == "coverage_id_not_in_manifest" and not check.passed for check in result.checks)


def test_promotion_gates_json_shape() -> None:
    entry = _minimal_entry(coverage_id="cov.test.promotion_gate_new")
    result = evaluate_promotion_gates(entry, load_registry_snapshot())
    payload = result.model_dump()
    assert payload["coverage_id"] == "cov.test.promotion_gate_new"
    assert "checks" in payload
    assert isinstance(payload["checks"][0]["gate_id"], str)


def test_authority_pilot_always_blocked_pending_coe() -> None:
    manifest = load_pattern_coverage_manifest()
    pilot = next(e for e in manifest.entries if e.question_ref == "q0.q046")
    result = evaluate_promotion_gates(pilot, load_registry_snapshot())
    assert not result.authority_pilot_ready
    assert any(check.gate_id == "coe_signoff_recorded" for check in result.authority_checks)
