"""Stage 3L-S5.2: Human-reviewed promotion candidate artifacts (no manifest writes)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.coverage.coverage_models import PatternCoverageEntry

from io_utils import assert_not_coverage_backend_path, assert_not_manifest_path
from promotion_gates import evaluate_promotion_gates
PROMOTION_CANDIDATES_DIR = Path(__file__).resolve().parent / "promotion_candidates"


def build_review_checklist(*, manifest_copy_ready: bool) -> list[str]:
    return [
        "Confirm draft_only, requires_human_review=true, promoted_to_manifest=false on source draft",
        "Review validation_errors and validation_warnings in promotion_gate_result",
        "Verify readiness label and expected_blockers match SOC expectations",
        "Confirm all governance execution flags remain false",
        "Manually paste manifest_patch_hint into pattern_coverage_v1.json entries[] (human edit only)",
        "Run: python tools/coverage_authoring/check_manifest_promotion.py",
        "Regenerate S6 map: coverage_drafter.py --emit-runtime-map",
        "Run backend pytest for pattern coverage and question runtime map tests",
        f"manifest_copy_ready={manifest_copy_ready} (must be true before manual copy)",
    ]


def build_promotion_candidate(entry: PatternCoverageEntry) -> dict[str, Any]:
    """Build a review artifact. Never mutates entry or manifest."""
    gate_result = evaluate_promotion_gates(entry, mode="draft")
    entry_dump = entry.model_dump(mode="json")
    return {
        "artifact_type": "stage3l_s5_promotion_candidate",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "would_write_manifest": False,
        "entry": entry_dump,
        "promotion_gate_result": gate_result.model_dump(),
        "manifest_patch_hint": entry_dump,
        "review_checklist": build_review_checklist(
            manifest_copy_ready=gate_result.manifest_copy_ready,
        ),
        "human_review_required": True,
        "notes": (
            "manifest_patch_hint is a single entries[] object for manual paste only. "
            "Do not use this artifact to overwrite pattern_coverage_v1.json."
        ),
    }


def resolve_promotion_candidate_path(path: Path) -> Path:
    resolved = path.resolve()
    candidates_root = PROMOTION_CANDIDATES_DIR.resolve()
    candidates_root.mkdir(parents=True, exist_ok=True)
    if candidates_root not in resolved.parents and resolved != candidates_root:
        raise ValueError(f"Promotion candidate output must be under {candidates_root}")
    return resolved


def write_promotion_candidate(
    entry: PatternCoverageEntry,
    output: Path | None = None,
) -> Path:
    """Write review artifact under promotion_candidates/ only."""
    payload = build_promotion_candidate(entry)
    if output is None:
        slug = entry.coverage_id.replace(".", "_")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = PROMOTION_CANDIDATES_DIR / f"promotion_candidate_{timestamp}_{slug}.json"
    else:
        assert_not_manifest_path(output)
        assert_not_coverage_backend_path(output)
        target = resolve_promotion_candidate_path(output)
    assert_not_manifest_path(target)
    assert_not_coverage_backend_path(target)
    if target.name == "pattern_coverage_v1.json":
        raise ValueError("Refusing to write a full replacement manifest filename")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target


def assert_candidate_payload_safe(payload: dict[str, Any]) -> None:
    """Guardrails for generated artifacts."""
    if payload.get("would_write_manifest") is not False:
        raise ValueError("would_write_manifest must be false")
    if "entries" in payload and isinstance(payload.get("entries"), list):
        if len(payload["entries"]) > 1 or payload.get("pack_version"):
            raise ValueError("Full manifest replacement artifacts are not allowed")
    hint = payload.get("manifest_patch_hint")
    if isinstance(hint, dict) and "entries" in hint:
        raise ValueError("manifest_patch_hint must be a single entry object, not a manifest wrapper")
