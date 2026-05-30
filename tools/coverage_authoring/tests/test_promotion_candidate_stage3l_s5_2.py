"""Stage 3L-S5.2 promotion candidate artifact tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.coverage.coverage_models import CoverageGovernance, CoverageReadiness, PatternCoverageEntry

from promotion_candidate import (
    assert_candidate_payload_safe,
    build_promotion_candidate,
    resolve_promotion_candidate_path,
    write_promotion_candidate,
)
from promotion_gates import evaluate_promotion_gates
from registries import MANIFEST_PATH

RUNTIME_MANIFEST = MANIFEST_PATH
COVERAGE_BACKEND = RUNTIME_MANIFEST.parent


def _minimal_entry(**overrides: object) -> PatternCoverageEntry:
    base = {
        "coverage_id": "cov.test.promotion_candidate",
        "question_ref": "q0.q999",
        "question": "Test promotion candidate?",
        "coverage_group": "template_only",
        "primary_skill": "aggregate_and_rank",
        "sub_invocations": [],
        "route_plan_shape": {
            "route_status": "route_ready",
            "primary_skill": "aggregate_and_rank",
            "pattern_id": "test",
            "operation_type": "top_n",
            "parameters": {},
        },
        "template_ref": None,
        "lookup_ref": None,
        "detection_family": None,
        "detection_ref": None,
        "evidence_contract_ref": "ranked_entities:user:failed_login_count",
        "readiness": CoverageReadiness.COE_SYNTHETIC_FIXTURE,
        "clarification_required": [],
        "expected_route_status": "route_ready",
        "expected_blockers": [],
        "governance": CoverageGovernance(),
        "notes": "",
    }
    base.update(overrides)
    return PatternCoverageEntry.model_validate(base)


def test_promotion_candidate_payload_shape() -> None:
    entry = _minimal_entry()
    payload = build_promotion_candidate(entry)
    assert_candidate_payload_safe(payload)
    assert payload["would_write_manifest"] is False
    assert payload["human_review_required"] is True
    assert "manifest_patch_hint" in payload
    assert payload["manifest_patch_hint"]["coverage_id"] == entry.coverage_id
    assert "promotion_gate_result" in payload
    assert "review_checklist" in payload


def test_invalid_primary_skill_fails_gates() -> None:
    entry = _minimal_entry(primary_skill="not_a_runtime_skill")
    result = evaluate_promotion_gates(entry, mode="draft")
    assert not result.manifest_copy_ready
    assert any("unknown_primary_skill" in err for err in result.validation_errors)


def test_invalid_operation_type_fails_gates() -> None:
    entry = _minimal_entry(
        route_plan_shape={
            "route_status": "route_ready",
            "primary_skill": "aggregate_and_rank",
            "pattern_id": "test",
            "operation_type": "not_allowed_op",
            "parameters": {},
        },
    )
    result = evaluate_promotion_gates(entry, mode="draft")
    assert not result.manifest_copy_ready
    assert any(item.gate_id == "operation_type_allowed_for_skill" and not item.passed for item in result.checks)


def test_readiness_overclaim_fails_gates() -> None:
    entry = _minimal_entry(
        readiness=CoverageReadiness.DEPENDENCY_MISSING,
        expected_blockers=[],
    )
    result = evaluate_promotion_gates(entry, mode="draft")
    assert not result.manifest_copy_ready
    assert any(
        item.gate_id == "readiness_or_documented_blockers" and not item.passed
        for item in result.checks
    )


def test_promotion_candidate_never_writes_manifest() -> None:
    before = RUNTIME_MANIFEST.read_text(encoding="utf-8")
    entry = _minimal_entry()
    written = write_promotion_candidate(entry)
    try:
        assert RUNTIME_MANIFEST.read_text(encoding="utf-8") == before
        payload = json.loads(written.read_text(encoding="utf-8"))
        assert_candidate_payload_safe(payload)
    finally:
        written.unlink(missing_ok=True)


def test_promotion_candidate_rejects_coverage_backend_output() -> None:
    entry = _minimal_entry()
    with pytest.raises(ValueError, match="coverage backend"):
        write_promotion_candidate(entry, COVERAGE_BACKEND / "evil.json")


def test_promotion_candidate_rejects_outside_candidates_dir(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="promotion_candidates"):
        resolve_promotion_candidate_path(tmp_path / "outside.json")


def test_assert_candidate_rejects_full_manifest_shape() -> None:
    with pytest.raises(ValueError, match="Full manifest"):
        assert_candidate_payload_safe(
            {
                "would_write_manifest": False,
                "pack_version": "x",
                "entries": [{}, {}],
            },
        )


def test_draft_promoted_flag_unchanged_by_build() -> None:
    entry = _minimal_entry()
    payload = build_promotion_candidate(entry)
    assert "promoted_to_manifest" not in payload["entry"] or payload["entry"].get("promoted_to_manifest") is not True
