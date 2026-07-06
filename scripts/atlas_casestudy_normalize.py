#!/usr/bin/env python3
"""ATLAS case-study rows → normalized JSON (plan 2026-07-06 item 3)."""
from __future__ import annotations

import ast
import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATLAS_DIR = ROOT / "docs" / "threat-intel" / "atlas"
CSV_PATH = ATLAS_DIR / "raw" / "atlas_nodes_2026_04.csv"
NORMALIZED_DIR = ATLAS_DIR / "normalized"
NORMALIZATION_RULES_VERSION = "atlas-casestudy-normalize-v1"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _technique_ids(row: dict[str, str]) -> list[str]:
    raw = (row.get("CHILD_TECHNIQUES") or "").strip()
    if not raw or raw == "[]":
        return []
    parsed = ast.literal_eval(raw)
    return sorted(str(item).strip() for item in parsed if str(item).strip())


def build_report() -> dict:
    rows: list[dict] = []
    with CSV_PATH.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("entity") or "").strip() != "casestudy":
                continue
            text = str(row.get("text") or row.get("description") or "")
            rows.append(
                {
                    "case_study_id": str(row.get("id") or "").strip(),
                    "name": str(row.get("name") or "").strip(),
                    "summary": text[:280].strip(),
                    "url": str(row.get("url") or "").strip(),
                    "technique_ids": _technique_ids(row),
                }
            )
    rows.sort(key=lambda item: item["case_study_id"])
    return {
        "schema_role": "atlas_casestudies_normalized_v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "normalization_rules_version": NORMALIZATION_RULES_VERSION,
        "provenance": {
            "source_file": str(CSV_PATH.relative_to(ROOT)),
            "source_sha256": _sha256_file(CSV_PATH),
        },
        "case_study_count": len(rows),
        "case_studies": rows,
    }


def main() -> int:
    report = build_report()
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    out = NORMALIZED_DIR / "atlas_casestudies_normalized.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"ATLAS case studies: {report['case_study_count']} -> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
