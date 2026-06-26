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

RUNTIME_MAP_PATH = REPO_ROOT / "backend" / "app" / "coverage" / "question_runtime_map_v1.json"
MANIFEST_PATH = REPO_ROOT / "backend" / "app" / "coverage" / "pattern_coverage_v1.json"
OUTPUT_JSON_PATH = REPO_ROOT / "docs" / "evals" / "row_authority_report.json"
OUTPUT_MD_PATH = REPO_ROOT / "docs" / "evals" / "row_authority_report.md"

AUTHORITY_READY = "exact_known_authority_ready"
WEAK_NEEDS_ENRICHMENT = "exact_known_weak_needs_enrichment"
NEEDS_LOOKUP = "exact_known_needs_lookup"
NEEDS_DETECTION_BINDING = "exact_known_needs_detection_binding"
NEEDS_CONTEXT_BINDING = "exact_known_needs_context_binding"
NEEDS_CLARIFICATION = "exact_known_needs_clarification"
UNSUPPORTED = "exact_known_unsupported"

AUTHORITY_READY_READINESS = frozenset({"source_ready"})
LOOKUP_READINESS = frozenset({"ioc_dependent", "lookup_dependent"})
DETECTION_READINESS = frozenset({"detection_dependent"})
CONTEXT_READINESS = frozenset({"blocked_missing_context", "context_dependent"})


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


def _project_s3_authority_ready(row_authority_status: str) -> bool:
    return row_authority_status == AUTHORITY_READY


def classify_row_authority(entry: dict[str, Any], manifest_entry: dict[str, Any] | None = None) -> tuple[str, list[str]]:
    """Return ``(row_authority_status, blockers)`` for one runtime-map row."""
    blockers: list[str] = []
    question_ref = str(entry.get("question_ref") or "")
    readiness = entry.get("manifest_readiness")
    promotion_status = entry.get("promotion_status")
    dependency_class = entry.get("dependency_class")

    if entry.get("route_blocked") is True or not entry.get("proposed_primary_skill"):
        if entry.get("route_blocked") is True:
            blockers.append("route_blocked")
        if not entry.get("proposed_primary_skill"):
            blockers.append("missing_proposed_primary_skill")
        return UNSUPPORTED, blockers

    if question_ref in {"q0.q045", "q0.q103", "q0.q104", "q0.q105"}:
        blockers.append("requires_clarification_or_case_context")
        return NEEDS_CLARIFICATION, blockers

    if readiness in LOOKUP_READINESS or dependency_class == "local_lookup":
        blockers.append(f"manifest_readiness:{readiness or 'missing'}")
        return NEEDS_LOOKUP, blockers

    if readiness in DETECTION_READINESS or dependency_class == "detection_binding":
        blockers.append(f"manifest_readiness:{readiness or 'missing'}")
        return NEEDS_DETECTION_BINDING, blockers

    if readiness in CONTEXT_READINESS:
        blockers.append(f"manifest_readiness:{readiness}")
        return NEEDS_CONTEXT_BINDING, blockers

    existing_ready = entry.get("s3_authority_ready") is True
    manifest_execution_eligible = False
    if isinstance(manifest_entry, dict):
        governance = manifest_entry.get("governance")
        if isinstance(governance, dict):
            manifest_execution_eligible = governance.get("execution_eligible") is True

    if existing_ready and promotion_status == "in_manifest" and readiness in AUTHORITY_READY_READINESS:
        if manifest_execution_eligible:
            return AUTHORITY_READY, blockers
        blockers.append("manifest_execution_eligible_false")
        return WEAK_NEEDS_ENRICHMENT, blockers

    if promotion_status != "in_manifest":
        blockers.append(f"promotion_status:{promotion_status or 'missing'}")
    if not readiness:
        blockers.append("manifest_readiness:missing")
    elif readiness not in AUTHORITY_READY_READINESS:
        blockers.append(f"manifest_readiness:{readiness}")
    if entry.get("skill_drift") is True:
        blockers.append("skill_drift")
    for blocker in entry.get("s3_authority_blockers") or []:
        if isinstance(blocker, str) and blocker not in blockers:
            blockers.append(blocker)
    return WEAK_NEEDS_ENRICHMENT, blockers


def build_report(runtime_map: Any, manifest: Any) -> dict[str, Any]:
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
        status, blockers = classify_row_authority(entry, manifest_index.get(question_ref))
        projected_ready = _project_s3_authority_ready(status)
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
                "question_ref": question_ref,
                "question": entry.get("question"),
                "row_authority_status": status,
                "s3_authority_ready": projected_ready,
                "existing_s3_authority_ready": existing_ready,
                "may_skip_llm": projected_ready,
                "promotion_status": entry.get("promotion_status"),
                "manifest_coverage_id": entry.get("manifest_coverage_id"),
                "manifest_readiness": entry.get("manifest_readiness"),
                "dependency_class": entry.get("dependency_class"),
                "route_blocked": entry.get("route_blocked") is True,
                "blockers": blockers,
            }
        )

    rows.sort(key=lambda row: row["question_ref"])
    status_counts = dict(sorted(Counter(row["row_authority_status"] for row in rows).items()))
    return {
        "schema_version": "2026-06-row-authority-v1",
        "runtime_map_path": str(RUNTIME_MAP_PATH.relative_to(REPO_ROOT)),
        "manifest_path": str(MANIFEST_PATH.relative_to(REPO_ROOT)),
        "row_count": len(rows),
        "status_counts": status_counts,
        "projection_mismatches": projection_mismatches,
        "rows": rows,
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

    report = build_report(_load_json(RUNTIME_MAP_PATH), _load_json(MANIFEST_PATH))
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
