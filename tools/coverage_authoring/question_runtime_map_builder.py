"""Build Stage 3L-S6 question_runtime_map_v1.json from Q0 taxonomy + Q4 manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from registries import MANIFEST_PATH, REPO_ROOT, TAXONOMY_PATH
from taxonomy_lookup import TaxonomyRow, load_taxonomy_rows

from pattern_runtime_mapping import (
    AUTHORITY_PILOT_COVERAGE_ID,
    AUTHORITY_PILOT_QUESTION_REF,
    LEGACY_ROUTER_INTENT_BY_PATTERN,
    PATTERN_TO_RUNTIME,
)

MAP_VERSION = "stage3l_s6_v1"
OUTPUT_PATH = REPO_ROOT / "backend" / "app" / "coverage" / "question_runtime_map_v1.json"


def _load_manifest_by_question_ref() -> dict[str, dict[str, Any]]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    by_ref: dict[str, dict[str, Any]] = {}
    for entry in payload.get("entries", []):
        by_ref[str(entry["question_ref"])] = entry
    return by_ref


def _map_row(row: TaxonomyRow, manifest_entry: dict[str, Any] | None) -> dict[str, Any]:
    pattern = row.pattern_type
    runtime = PATTERN_TO_RUNTIME.get(pattern, PATTERN_TO_RUNTIME["other_or_unclear"])
    legacy_intent = LEGACY_ROUTER_INTENT_BY_PATTERN.get(pattern, "attack_discovery")

    record: dict[str, Any] = {
        "question_number": row.number,
        "question_ref": row.question_ref,
        "question": row.question,
        "pattern_type": pattern,
        "legacy_router_intent_hint": legacy_intent,
        "proposed_primary_skill": runtime.get("proposed_primary_skill"),
        "proposed_operation_type": runtime.get("proposed_operation_type"),
        "dependency_class": runtime.get("dependency_class"),
        "route_blocked": bool(runtime.get("route_blocked")),
        "promotion_status": "not_in_manifest",
        "manifest_coverage_id": None,
        "manifest_primary_skill": None,
        "manifest_readiness": None,
        "authority_pilot_candidate": row.question_ref == AUTHORITY_PILOT_QUESTION_REF,
        "s3_authority_ready": False,
        "skill_drift": False,
    }

    if manifest_entry is not None:
        record["promotion_status"] = "in_manifest"
        record["manifest_coverage_id"] = manifest_entry["coverage_id"]
        record["manifest_primary_skill"] = manifest_entry["primary_skill"]
        record["manifest_readiness"] = manifest_entry["readiness"]
        proposed = record["proposed_primary_skill"]
        actual = manifest_entry["primary_skill"]
        if proposed is not None and proposed != actual:
            record["skill_drift"] = True
            record["skill_drift_note"] = (
                f"taxonomy proposes {proposed!r}; manifest uses {actual!r} (fixture/calibration choice)"
            )

    if record["authority_pilot_candidate"]:
        record["authority_pilot_coverage_id"] = AUTHORITY_PILOT_COVERAGE_ID
        record["s3_authority_ready"] = False
        record["s3_authority_blockers"] = [
            "coe_step3_implementation_not_approved",
            "operation_authoritative_enabled_defaults_false",
        ]

    return record


def build_question_runtime_map(
    *,
    taxonomy_path: Path | None = None,
) -> dict[str, Any]:
    rows = load_taxonomy_rows(taxonomy_path)
    manifest_by_ref = _load_manifest_by_question_ref()
    entries = [_map_row(row, manifest_by_ref.get(row.question_ref)) for row in rows]
    in_manifest = sum(1 for item in entries if item["promotion_status"] == "in_manifest")
    return {
        "map_version": MAP_VERSION,
        "taxonomy_source": str((taxonomy_path or TAXONOMY_PATH).relative_to(REPO_ROOT)),
        "runtime_mapping_source": "docs/soc_runtime_skill_route_plan_stage3k_q05.md",
        "manifest_source": "backend/app/coverage/pattern_coverage_v1.json",
        "question_count": len(entries),
        "manifest_row_count": in_manifest,
        "authority_pilot_question_ref": AUTHORITY_PILOT_QUESTION_REF,
        "entries": entries,
    }


def write_question_runtime_map(path: Path | None = None) -> Path:
    target = path or OUTPUT_PATH
    payload = build_question_runtime_map()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target


def main() -> int:
    written = write_question_runtime_map()
    payload = json.loads(written.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "written": str(written),
                "question_count": payload["question_count"],
                "manifest_row_count": payload["manifest_row_count"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
