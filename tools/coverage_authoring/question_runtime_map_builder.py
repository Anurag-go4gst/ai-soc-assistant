"""Build Stage 3L-S6 question_runtime_map_v1.json from Q0 taxonomy + Q4 manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mitre_permitted import build_mitre_permitted_for_row, load_taxonomy_mitre_by_ref
from registries import MANIFEST_PATH, REPO_ROOT, TAXONOMY_PATH
from taxonomy_lookup import TaxonomyRow, load_taxonomy_rows

SUPPLEMENTAL_TAXONOMY_PATH = REPO_ROOT / "tools" / "coverage_authoring" / "supplemental_taxonomy_rows.json"

from operation_report_fields import build_report_entry
from pattern_runtime_mapping import (
    AUTHORITY_PILOT_COVERAGE_ID,
    AUTHORITY_PILOT_QUESTION_REF,
    LEGACY_ROUTER_INTENT_BY_PATTERN,
    PATTERN_TO_RUNTIME,
)

MAP_VERSION = "stage3l_s6_v1"
OPERATION_REPORT_VERSION = "stage3l_s6_2_v1"
OUTPUT_PATH = REPO_ROOT / "backend" / "app" / "coverage" / "question_runtime_map_v1.json"
OPERATION_REPORT_PATH = REPO_ROOT / "docs" / "stage3l_s6_105_question_operation_map.json"


def _load_manifest_by_question_ref() -> dict[str, dict[str, Any]]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    by_ref: dict[str, dict[str, Any]] = {}
    for entry in payload.get("entries", []):
        by_ref[str(entry["question_ref"])] = entry
    return by_ref


def _load_supplemental_rows() -> list[dict[str, Any]]:
    if not SUPPLEMENTAL_TAXONOMY_PATH.is_file():
        return []
    payload = json.loads(SUPPLEMENTAL_TAXONOMY_PATH.read_text(encoding="utf-8"))
    entries = payload.get("entries", [])
    return [item for item in entries if isinstance(item, dict) and item.get("question_ref")]


def _map_row(
    row: TaxonomyRow,
    manifest_entry: dict[str, Any] | None,
    *,
    taxonomy_mitre_by_ref: dict[str, list[str]],
) -> dict[str, Any]:
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

    from mitre_permitted import use_case_mitre_for_question_ref

    taxonomy_mitre = taxonomy_mitre_by_ref.get(row.question_ref, [])
    mitre_block = build_mitre_permitted_for_row(
        question_ref=row.question_ref,
        taxonomy_mitre=taxonomy_mitre,
        use_case_mitre=use_case_mitre_for_question_ref(row.question_ref),
    )
    record.update(mitre_block)

    return record


def _map_supplemental_row(raw: dict[str, Any], manifest_by_ref: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ref = str(raw["question_ref"]).strip().lower()
    if not ref.startswith("q0."):
        raise ValueError(f"supplemental row must use q0.qNNN ref: {ref!r}")
    number = int(ref.split(".")[-1].lstrip("q"))
    row = TaxonomyRow(
        number=number,
        question=str(raw.get("question") or raw.get("original_question") or ""),
        pattern_type=str(raw.get("pattern_type") or "other_or_unclear"),
        question_ref=ref,
    )
    taxonomy_mitre = raw.get("suggested_mitre_candidates")
    if isinstance(taxonomy_mitre, list):
        taxonomy_slice = [str(item).upper() for item in taxonomy_mitre]
    else:
        from mitre_permitted import parse_mitre_ids_from_cell

        taxonomy_slice = parse_mitre_ids_from_cell(str(taxonomy_mitre or ""))
    record = _map_row(row, manifest_by_ref.get(ref), taxonomy_mitre_by_ref={ref: taxonomy_slice})
    record.update({k: v for k, v in raw.items() if k not in record})
    return record


def build_question_runtime_map(
    *,
    taxonomy_path: Path | None = None,
) -> dict[str, Any]:
    rows = load_taxonomy_rows(taxonomy_path)
    manifest_by_ref = _load_manifest_by_question_ref()
    taxonomy_mitre_by_ref = load_taxonomy_mitre_by_ref(taxonomy_path)
    entries = [
        _map_row(row, manifest_by_ref.get(row.question_ref), taxonomy_mitre_by_ref=taxonomy_mitre_by_ref)
        for row in rows
    ]
    existing_refs = {item["question_ref"] for item in entries}
    for raw in _load_supplemental_rows():
        ref = str(raw["question_ref"]).strip().lower()
        if ref in existing_refs:
            continue
        entries.append(_map_supplemental_row(raw, manifest_by_ref))
        existing_refs.add(ref)
    entries.sort(key=lambda item: int(str(item["question_ref"]).split(".")[-1].lstrip("q")))
    in_manifest = sum(1 for item in entries if item["promotion_status"] == "in_manifest")
    supplemental_count = len(_load_supplemental_rows())
    return {
        "map_version": MAP_VERSION,
        "taxonomy_source": str((taxonomy_path or TAXONOMY_PATH).relative_to(REPO_ROOT)),
        "supplemental_source": str(SUPPLEMENTAL_TAXONOMY_PATH.relative_to(REPO_ROOT)),
        "runtime_mapping_source": "docs/soc_runtime_skill_route_plan_stage3k_q05.md",
        "manifest_source": "backend/app/coverage/pattern_coverage_v1.json",
        "question_count": len(entries),
        "supplemental_row_count": supplemental_count,
        "manifest_row_count": in_manifest,
        "authority_pilot_question_ref": AUTHORITY_PILOT_QUESTION_REF,
        "entries": entries,
    }


def build_operation_map_report(
    *,
    taxonomy_path: Path | None = None,
    runtime_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """S6.2 provisional report from the same rows as S6.1 (no second source of truth)."""
    runtime = runtime_payload or build_question_runtime_map(taxonomy_path=taxonomy_path)
    report_entries = [build_report_entry(row) for row in runtime["entries"]]
    return {
        "report_version": OPERATION_REPORT_VERSION,
        "source_of_truth": (
            "tools/coverage_authoring/question_runtime_map_builder.py "
            "+ docs/soc_question_taxonomy_stage3k_q0.md + pattern_coverage_v1.json"
        ),
        "runtime_map_artifact": str(OUTPUT_PATH.relative_to(REPO_ROOT)),
        "taxonomy_source": runtime["taxonomy_source"],
        "question_count": runtime["question_count"],
        "manifest_row_count": runtime["manifest_row_count"],
        "provisional_disclaimer": (
            "Provisional analysis only. Not coverage readiness. Not authority approval. "
            "Not live /chat support."
        ),
        "entries": report_entries,
    }


def write_question_runtime_map(path: Path | None = None) -> Path:
    target = path or OUTPUT_PATH
    payload = build_question_runtime_map()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target


def write_operation_map_report(
    path: Path | None = None,
    *,
    taxonomy_path: Path | None = None,
    runtime_payload: dict[str, Any] | None = None,
) -> Path:
    runtime = runtime_payload or build_question_runtime_map(taxonomy_path=taxonomy_path)
    target = path or OPERATION_REPORT_PATH
    payload = build_operation_map_report(taxonomy_path=taxonomy_path, runtime_payload=runtime)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target


def write_all_question_maps(
    *,
    taxonomy_path: Path | None = None,
) -> tuple[Path, Path]:
    """Regenerate S6.1 runtime map and S6.2 report from one builder pass."""
    runtime_payload = build_question_runtime_map(taxonomy_path=taxonomy_path)
    runtime_path = OUTPUT_PATH
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.write_text(json.dumps(runtime_payload, indent=2) + "\n", encoding="utf-8")
    report_path = write_operation_map_report(
        taxonomy_path=taxonomy_path,
        runtime_payload=runtime_payload,
    )
    return runtime_path, report_path


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
