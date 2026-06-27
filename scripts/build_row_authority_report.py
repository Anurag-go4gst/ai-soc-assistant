#!/usr/bin/env python3
"""Build the report-only row authority audit for the 105 runtime map.

This is an offline artifact generator. It reads the existing runtime map and
coverage manifest, derives one reasoned ``row_authority_status`` per known row,
and projects that status back to the already-shipped ``s3_authority_ready``
boolean. It does not import ``app.*`` modules and does not affect /chat.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.coverage.promotion_lifecycle import projected_demotion_reasons_for_row
from app.coverage.row_authority import (
    AUTHORITY_READY,
    NEEDS_CLARIFICATION,
    NEEDS_DETECTION_BINDING,
    NEEDS_LOOKUP,
    UNSUPPORTED,
    WEAK_NEEDS_ENRICHMENT,
    classify_runtime_row_authority,
    project_s3_authority_ready,
)

RUNTIME_MAP_PATH = REPO_ROOT / "backend" / "app" / "coverage" / "question_runtime_map_v1.json"
MANIFEST_PATH = REPO_ROOT / "backend" / "app" / "coverage" / "pattern_coverage_v1.json"
CATALOG_PATH = REPO_ROOT / "backend" / "app" / "use_cases" / "catalog.json"
OUTPUT_JSON_PATH = REPO_ROOT / "docs" / "evals" / "row_authority_report.json"
OUTPUT_MD_PATH = REPO_ROOT / "docs" / "evals" / "row_authority_report.md"
CATALOG_AUTHORITY_READY = "catalog_authority_ready"
CATALOG_WEAK_NEEDS_ENRICHMENT = "catalog_weak_needs_enrichment"


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _manifest_by_question(manifest: Any) -> dict[str, dict[str, Any]]:
    entries = manifest.get("entries") if isinstance(manifest, dict) else None
    if not isinstance(entries, list):
        return {}
    index: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        question_ref = entry.get("question_ref")
        if isinstance(question_ref, str) and question_ref:
            index[question_ref] = entry
    return index


def _classify_catalog_authority(record: dict[str, Any]) -> tuple[str, bool, list[str]]:
    explicit_t0 = "t0_exact_authority" in record
    t0_authority = record.get("t0_exact_authority") is True
    blockers: list[str] = []
    if explicit_t0 and t0_authority and not record.get("llm_advisory_recommended") and not record.get("human_review_required"):
        return CATALOG_AUTHORITY_READY, True, blockers
    if not explicit_t0:
        blockers.append("t0_exact_authority_not_explicit")
    if not t0_authority:
        blockers.append("t0_exact_authority_false")
    if record.get("llm_advisory_recommended"):
        blockers.append("llm_advisory_recommended")
    if record.get("human_review_required"):
        blockers.append("human_review_required")
    if record.get("requires_t2_shape_check"):
        blockers.append("requires_t2_shape_check")
    return CATALOG_WEAK_NEEDS_ENRICHMENT, False, blockers


def _catalog_rows(catalog: Any) -> list[dict[str, Any]]:
    records = catalog.get("use_cases") if isinstance(catalog, dict) else None
    if not isinstance(records, list):
        return []
    rows: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        use_case_id = record.get("use_case_id")
        if not isinstance(use_case_id, str) or not use_case_id:
            continue
        status, ready, blockers = _classify_catalog_authority(record)
        rows.append(
            {
                "row_kind": "catalog",
                "row_id": use_case_id,
                "use_case_id": use_case_id,
                "display_name": record.get("display_name"),
                "question_ref": None,
                "question": None,
                "row_authority_status": status,
                "s3_authority_ready": ready,
                "existing_s3_authority_ready": None,
                "may_skip_llm": ready,
                "registry_tier": record.get("registry_tier"),
                "use_case_type": record.get("use_case_type"),
                "t0_exact_authority": record.get("t0_exact_authority"),
                "llm_advisory_recommended": record.get("llm_advisory_recommended"),
                "requires_t2_shape_check": record.get("requires_t2_shape_check"),
                "human_review_required": record.get("human_review_required"),
                "default_spl_template": record.get("default_spl_template"),
                "required_sources": list(record.get("required_sources") or []),
                "optional_sources": list(record.get("optional_sources") or []),
                "mitre_candidates": list(record.get("mitre_candidates") or []),
                "blockers": blockers,
            }
        )
    rows.sort(key=lambda row: row["row_id"])
    return rows


def build_report(runtime_map: Any, manifest: Any, catalog: Any | None = None) -> dict[str, Any]:
    entries = runtime_map.get("entries") if isinstance(runtime_map, dict) else None
    if not isinstance(entries, list):
        raise ValueError("runtime map missing entries list")

    manifest_index = _manifest_by_question(manifest)
    rows: list[dict[str, Any]] = []
    projection_mismatches: list[dict[str, Any]] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        question_ref = entry.get("question_ref")
        if not isinstance(question_ref, str) or not question_ref:
            continue
        status, blockers = classify_runtime_row_authority(entry, manifest_index.get(question_ref))
        projected_ready = project_s3_authority_ready(status)
        existing_ready = entry.get("s3_authority_ready") is True
        if projected_ready != existing_ready:
            projection_mismatches.append(
                {
                    "question_ref": question_ref,
                    "existing_s3_authority_ready": existing_ready,
                    "projected_s3_authority_ready": projected_ready,
                    "row_authority_status": status,
                }
            )
        rows.append(
            {
                "row_kind": "question_105",
                "row_id": question_ref,
                "question_ref": question_ref,
                "question": entry.get("question"),
                "row_authority_status": status,
                "s3_authority_ready": projected_ready,
                "existing_s3_authority_ready": existing_ready,
                "may_skip_llm": projected_ready,
                "projected_demotion_reasons": projected_demotion_reasons_for_row(
                    row_authority_status=status,
                    source_profile_bindings_missing=any(
                        "source" in str(item).lower() or "binding" in str(item).lower()
                        for item in blockers
                    ),
                ),
                "promotion_status": entry.get("promotion_status"),
                "manifest_coverage_id": entry.get("manifest_coverage_id"),
                "manifest_readiness": entry.get("manifest_readiness"),
                "pattern_type": entry.get("pattern_type"),
                "proposed_primary_skill": entry.get("proposed_primary_skill"),
                "proposed_operation_type": entry.get("proposed_operation_type"),
                "dependency_class": entry.get("dependency_class"),
                "route_blocked": entry.get("route_blocked") is True,
                "mitre_registry": entry.get("mitre_registry"),
                "blockers": blockers,
            }
        )

    rows.sort(key=lambda row: row["question_ref"])
    catalog_rows = _catalog_rows(catalog) if catalog is not None else []
    all_rows = [*rows, *catalog_rows]
    status_counts = dict(sorted(Counter(row["row_authority_status"] for row in all_rows).items()))
    return {
        "schema_version": "2026-06-row-authority-v1",
        "runtime_map_path": str(RUNTIME_MAP_PATH.relative_to(REPO_ROOT)),
        "manifest_path": str(MANIFEST_PATH.relative_to(REPO_ROOT)),
        "catalog_path": str(CATALOG_PATH.relative_to(REPO_ROOT)),
        "row_count": len(all_rows),
        "question_105_count": len(rows),
        "catalog_count": len(catalog_rows),
        "status_counts": status_counts,
        "projection_mismatches": projection_mismatches,
        "rows": all_rows,
    }


def _serialize_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _serialize_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Row Authority Report",
        "",
        "Report-only audit for the 105-question runtime map. `row_authority_status` is the reasoned enum; `s3_authority_ready` is the one-way projected readiness boolean.",
        "",
        f"- Rows: **{report['row_count']}**",
        f"- 105-question rows: **{report.get('question_105_count', 0)}**",
        f"- Catalogue rows: **{report.get('catalog_count', 0)}**",
        f"- Projection mismatches against existing `s3_authority_ready`: **{len(report['projection_mismatches'])}**",
        "",
        "## Status Counts",
        "",
        "| row_authority_status | rows |",
        "|---|---:|",
    ]
    for status, count in report["status_counts"].items():
        lines.append(f"| `{status}` | {count} |")
    lines.extend(
        [
            "",
            "## Special Cases",
            "",
            "| question_ref | row_authority_status | s3_authority_ready | blockers |",
            "|---|---|---:|---|",
        ]
    )
    special_refs = {"q0.q028", "q0.q045", "q0.q046", "q0.q103", "q0.q104", "q0.q105"}
    for row in report["rows"]:
        if row.get("row_kind") != "question_105":
            continue
        if row["question_ref"] not in special_refs and row["manifest_coverage_id"] is None:
            continue
        blockers = ", ".join(row["blockers"]) if row["blockers"] else "-"
        lines.append(
            f"| `{row['question_ref']}` | `{row['row_authority_status']}` | "
            f"{str(row['s3_authority_ready']).lower()} | {blockers} |"
        )
    lines.append("")
    return "\n".join(lines)


def _write_outputs(report: dict[str, Any]) -> None:
    OUTPUT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON_PATH.write_text(_serialize_json(report), encoding="utf-8")
    OUTPUT_MD_PATH.write_text(_serialize_markdown(report), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if generated outputs differ from disk.")
    args = parser.parse_args(argv)

    report = build_report(_load_json(RUNTIME_MAP_PATH), _load_json(MANIFEST_PATH), _load_json(CATALOG_PATH))
    rendered_json = _serialize_json(report)
    rendered_md = _serialize_markdown(report)

    if args.check:
        failures: list[str] = []
        for path, rendered in ((OUTPUT_JSON_PATH, rendered_json), (OUTPUT_MD_PATH, rendered_md)):
            try:
                existing = path.read_text(encoding="utf-8")
            except OSError as exc:
                failures.append(f"cannot read {path}: {exc}")
                continue
            if existing != rendered:
                failures.append(f"{path} is stale")
        if failures:
            for failure in failures:
                print(f"--check failed: {failure}", file=sys.stderr)
            return 1
        print("row authority report check ok")
        return 0

    _write_outputs(report)
    print(f"wrote {OUTPUT_JSON_PATH} and {OUTPUT_MD_PATH} ({report['row_count']} rows).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
