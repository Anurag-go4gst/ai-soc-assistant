from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.coverage.promotion_status_review import (
    PromotionStatusWriteRequest,
    ReviewedPromotionEvidence,
    apply_promotion_status_write,
    compute_row_revision,
    evaluate_promotion_status_write,
)
from app.use_cases import answer_packs

_REPO = Path(__file__).resolve().parents[3]
_RUNTIME_MAP = _REPO / "backend" / "app" / "coverage" / "question_runtime_map_v1.json"


def _temp_map(tmp_path: Path, entry: dict) -> Path:
    payload = {
        "map_version": "test",
        "entries": [entry],
    }
    path = tmp_path / "runtime_map.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _base_entry(**overrides: object) -> dict:
    row = {
        "question_ref": "q0.q999",
        "question": "Test promotion row",
        "promotion_status": "not_in_manifest",
        "manifest_coverage_id": "cov.test.promotion",
        "manifest_readiness": "source_ready",
        "proposed_primary_skill": "spl_generation",
        "route_blocked": False,
        "s3_authority_ready": True,
        "dependency_class": "threshold_baseline_plus_source",
    }
    row.update(overrides)
    return row


def _evidence(**overrides: object) -> ReviewedPromotionEvidence:
    base = {
        "operator_id": "coe.reviewer",
        "review_ticket": "PROMO-1",
        "pack_id": "q0.q046",
        "golden_passed": True,
        "golden_run_ref": "governance-regression-2026-06-27",
    }
    base.update(overrides)
    return ReviewedPromotionEvidence(**base)


def test_promotion_write_dry_run_shows_before_after_and_blockers(tmp_path: Path) -> None:
    entry = _base_entry()
    map_path = _temp_map(tmp_path, entry)
    revision = compute_row_revision(entry)
    result = evaluate_promotion_status_write(
        PromotionStatusWriteRequest(
            action="promote",
            question_ref="q0.q999",
            row_revision=revision,
            reviewed_evidence=_evidence(),
            dry_run=True,
            runtime_map_path=map_path,
        )
    )

    assert result.allowed is False
    assert result.before_status == "not_in_manifest"
    assert "s3_authority_ready_required" in result.blockers or "reviewed_answer_pack_required" in result.blockers
    assert result.applied is False


def test_promotion_write_blocks_stale_row_revision(tmp_path: Path) -> None:
    entry = _base_entry()
    map_path = _temp_map(tmp_path, entry)
    result = evaluate_promotion_status_write(
        PromotionStatusWriteRequest(
            action="promote",
            question_ref="q0.q999",
            row_revision="deadbeefdeadbeef",
            reviewed_evidence=_evidence(),
            dry_run=True,
            runtime_map_path=map_path,
        )
    )

    assert result.allowed is False
    assert "stale_row_revision" in result.blockers


def test_promotion_apply_writes_audit_and_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    entry = _base_entry()
    map_path = _temp_map(tmp_path, entry)
    audit_path = tmp_path / "audit.jsonl"
    revision = compute_row_revision(entry)

    def _fake_pack(**_: object) -> dict:
        return {"case_id": "q0.q999", "review_status": "reviewed"}

    monkeypatch.setattr(answer_packs, "reviewed_answer_pack", _fake_pack)
    monkeypatch.setattr(
        "app.coverage.promotion_status_review.reviewed_answer_pack",
        _fake_pack,
    )
    monkeypatch.setattr(
        "app.coverage.promotion_status_review.project_s3_authority_ready",
        lambda _status: True,
    )
    monkeypatch.setattr(
        "app.coverage.promotion_status_review.classify_runtime_row_authority",
        lambda *_args, **_kwargs: ("exact_known_authority_ready", []),
    )

    result = apply_promotion_status_write(
        PromotionStatusWriteRequest(
            action="promote",
            question_ref="q0.q999",
            row_revision=revision,
            reviewed_evidence=_evidence(pack_id="q0.q999"),
            dry_run=False,
            runtime_map_path=map_path,
            audit_path=audit_path,
        )
    )

    assert result.allowed is True
    assert result.applied is True
    assert result.after_status == "in_manifest"
    saved = json.loads(map_path.read_text(encoding="utf-8"))
    assert saved["entries"][0]["promotion_status"] == "in_manifest"
    audit_lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(audit_lines) == 1
    audit = json.loads(audit_lines[0])
    assert audit["before_promotion_status"] == "not_in_manifest"
    assert audit["llm_authority"] is False


def test_demotion_write_requires_reviewed_reason(tmp_path: Path) -> None:
    entry = _base_entry(promotion_status="in_manifest", authority_pilot_candidate=False)
    map_path = _temp_map(tmp_path, entry)
    revision = compute_row_revision(entry)
    result = evaluate_promotion_status_write(
        PromotionStatusWriteRequest(
            action="demote",
            question_ref="q0.q999",
            row_revision=revision,
            reviewed_evidence=_evidence(reviewed_reason=""),
            dry_run=True,
            runtime_map_path=map_path,
        )
    )

    assert result.allowed is False
    assert "reviewed_demotion_reason_required" in result.blockers


def test_demotion_apply_is_audited(tmp_path: Path) -> None:
    entry = _base_entry(promotion_status="in_manifest", authority_pilot_candidate=False)
    map_path = _temp_map(tmp_path, entry)
    audit_path = tmp_path / "audit.jsonl"
    revision = compute_row_revision(entry)
    result = apply_promotion_status_write(
        PromotionStatusWriteRequest(
            action="demote",
            question_ref="q0.q999",
            row_revision=revision,
            reviewed_evidence=_evidence(reviewed_reason="golden regression failed on binding drift"),
            dry_run=False,
            runtime_map_path=map_path,
            audit_path=audit_path,
        )
    )

    assert result.allowed is True
    assert result.applied is True
    assert result.after_status == "not_in_manifest"
    assert audit_path.exists()


def test_runtime_map_authority_is_not_mutated_by_classifier_import() -> None:
  # Classifier path remains read-only: no write helpers on question_runtime_map loader.
    from app.coverage import question_runtime_map as loader

    assert not hasattr(loader, "write_promotion_status")
    assert not hasattr(loader, "apply_promotion_status")
