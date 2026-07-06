#!/usr/bin/env python3
"""ATLAS flat nodes CSV shape / referential-integrity gate (plan 2026-07-06 item 2).

Offline, deterministic, no LLM. Runs BEFORE case-study/mitigation normalization.
Fails loudly on unexpected column sets or dangling references.

Writes docs/threat-intel/atlas/reports/atlas_nodes_duplicate_report.{json,md}.
Exit 0 when all checks pass; non-zero on schema drift or integrity failures.
"""
from __future__ import annotations

import ast
import csv
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATLAS_DIR = ROOT / "docs" / "threat-intel" / "atlas"
CSV_PATH = ATLAS_DIR / "raw" / "atlas_nodes_2026_04.csv"
REPORTS_DIR = ATLAS_DIR / "reports"

EXPECTED_COLUMNS = (
    "id",
    "name",
    "entity",
    "text",
    "description",
    "url",
    "keywords",
    "hashtags",
    "PARENT_TACTICS",
    "PARENT_TECHNIQUES",
    "PARENT_MITIGATIONS",
    "PARENT_CASESTUDIES",
    "CHILD_TECHNIQUES",
)

EXPECTED_ENTITY_COUNTS = {
    "tactic": 16,
    "technique": 170,
    "casestudy": 57,
    "mitigation": 35,
}

LIST_COLUMNS = (
    "PARENT_TACTICS",
    "PARENT_TECHNIQUES",
    "PARENT_MITIGATIONS",
    "PARENT_CASESTUDIES",
    "CHILD_TECHNIQUES",
)

VALID_ID_RE = re.compile(r"^AML\.(T|TA|CS|M)\d")


def _parse_list_cell(value: str) -> list[str]:
    raw = (value or "").strip()
    if not raw or raw == "[]":
        return []
    parsed = ast.literal_eval(raw)
    if not isinstance(parsed, list):
        raise ValueError(f"expected list literal, got {type(parsed).__name__}")
    return [str(item).strip() for item in parsed if str(item).strip()]


def analyze(rows: list[dict[str, str]]) -> dict:
    entity_counts: Counter[str] = Counter()
    duplicate_ids: dict[str, int] = {}
    seen_by_entity: dict[str, set[str]] = {}
    dangling: list[dict[str, str]] = []
    all_ids: set[str] = set()

    for row in rows:
        row_id = str(row.get("id") or "").strip()
        entity = str(row.get("entity") or "").strip()
        if row_id:
            all_ids.add(row_id)
            entity_counts[entity] += 1
            bucket = seen_by_entity.setdefault(entity, set())
            if row_id in bucket:
                duplicate_ids[row_id] = duplicate_ids.get(row_id, 1) + 1
            bucket.add(row_id)

    for row in rows:
        row_id = str(row.get("id") or "").strip()
        for column in LIST_COLUMNS:
            try:
                refs = _parse_list_cell(str(row.get(column) or ""))
            except (ValueError, SyntaxError) as exc:
                dangling.append(
                    {
                        "row_id": row_id,
                        "column": column,
                        "issue": f"invalid_list_literal: {exc}",
                    }
                )
                continue
            for ref in refs:
                if not VALID_ID_RE.match(ref):
                    dangling.append(
                        {
                            "row_id": row_id,
                            "column": column,
                            "issue": f"invalid_id_format: {ref}",
                        }
                    )
                    continue
                if ref not in all_ids:
                    dangling.append(
                        {
                            "row_id": row_id,
                            "column": column,
                            "issue": f"dangling_reference: {ref}",
                        }
                    )

    entity_mismatches = {
        entity: {"expected": expected, "actual": entity_counts.get(entity, 0)}
        for entity, expected in EXPECTED_ENTITY_COUNTS.items()
        if entity_counts.get(entity, 0) != expected
    }

    return {
        "schema_role": "atlas_nodes_duplicate_report_v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_file": str(CSV_PATH.relative_to(ROOT)),
        "row_count": len(rows),
        "entity_counts": dict(sorted(entity_counts.items())),
        "expected_entity_counts": EXPECTED_ENTITY_COUNTS,
        "entity_count_mismatches": entity_mismatches,
        "duplicate_id_count": len(duplicate_ids),
        "duplicate_ids": duplicate_ids,
        "dangling_reference_count": len(dangling),
        "dangling_references": dangling[:50],
        "dangling_reference_truncated": len(dangling) > 50,
        "passed": not entity_mismatches and not duplicate_ids and not dangling,
    }


def _render_md(report: dict) -> str:
    lines = [
        "# ATLAS nodes CSV duplicate / integrity report",
        "",
        f"- Generated: `{report['generated_at_utc']}`",
        f"- Source: `{report['source_file']}`",
        f"- Rows: **{report['row_count']}**",
        f"- Entity counts: `{report['entity_counts']}`",
        f"- Expected: `{report['expected_entity_counts']}`",
        f"- Duplicate ids: **{report['duplicate_id_count']}**",
        f"- Dangling references: **{report['dangling_reference_count']}**",
        f"- Passed: **{report['passed']}**",
        "",
    ]
    if report["entity_count_mismatches"]:
        lines += ["## Entity count mismatches", "", "```json", json.dumps(report["entity_count_mismatches"], indent=2), "```", ""]
    if report["duplicate_ids"]:
        lines += ["## Duplicate ids", "", "```json", json.dumps(report["duplicate_ids"], indent=2), "```", ""]
    if report["dangling_references"]:
        lines += ["## Dangling references (first 50)", "", "```json", json.dumps(report["dangling_references"], indent=2), "```", ""]
    return "\n".join(lines)


def _load_rows() -> list[dict[str, str]]:
    if not CSV_PATH.is_file():
        raise FileNotFoundError(f"missing staged CSV: {CSV_PATH}")
    with CSV_PATH.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SystemExit("unexpected_column_set: empty CSV header")
        actual = tuple(reader.fieldnames)
        if actual != EXPECTED_COLUMNS:
            raise SystemExit(
                "unexpected_column_set: "
                f"expected={list(EXPECTED_COLUMNS)} actual={list(actual)}"
            )
        return [dict(row) for row in reader]


def main() -> int:
    rows = _load_rows()
    report = analyze(rows)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "atlas_nodes_duplicate_report.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    (REPORTS_DIR / "atlas_nodes_duplicate_report.md").write_text(
        _render_md(report),
        encoding="utf-8",
    )
    print(
        f"ATLAS nodes report: {report['row_count']} rows, "
        f"entities={report['entity_counts']}, "
        f"dangling={report['dangling_reference_count']}, "
        f"passed={report['passed']} "
        f"-> {REPORTS_DIR.relative_to(ROOT)}/atlas_nodes_duplicate_report.{{json,md}}"
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
