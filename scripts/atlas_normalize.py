#!/usr/bin/env python3
"""ATLAS raw → normalized canonical layer (plan §7 E3/E4).

Offline, deterministic, no LLM. Runs AFTER the duplicate gate
(`atlas_duplicate_check.py`). Collapses the ATLAS Navigator matrix into one
canonical row per ``techniqueID`` with a ``tactics: []`` list (Navigator repeats a
technique across tactics — see the duplicate report), preserves per-tactic
case-study scores in a side map, and stamps provenance + the raw artifact
``source_sha256`` so the normalized file is traceable to the immutable raw input.

Never edits raw payloads; only writes new files under ``normalized/``. Generated
intermediate files may be deleted after review; raw files are never deleted.

Writes docs/threat-intel/atlas/normalized/atlas_matrix_normalized.json.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATLAS_DIR = ROOT / "docs" / "threat-intel" / "atlas"
MATRIX_PATH = ATLAS_DIR / "raw" / "ATLAS_Matrix.json"
FREQ_PATH = ATLAS_DIR / "raw" / "ATLAS_Case_Study_Frequency.json"
NORMALIZED_DIR = ATLAS_DIR / "normalized"

NORMALIZATION_RULES_VERSION = "atlas-normalize-v1"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_layer(path: Path) -> tuple[list[dict], dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    techniques = payload.get("techniques") if isinstance(payload, dict) else None
    if not isinstance(techniques, list):
        raise ValueError(f"{path.name}: no 'techniques' list")
    return [row for row in techniques if isinstance(row, dict)], payload


def normalize(matrix_rows: list[dict], freq_rows: list[dict]) -> dict:
    """One canonical row per techniqueID; tactics as a sorted list; per-tactic
    scores preserved in a side map."""
    freq = {
        str(r.get("techniqueID") or ""): r.get("score", 0)
        for r in freq_rows
        if r.get("techniqueID")
    }
    canonical: dict[str, dict] = {}
    for row in matrix_rows:
        tid = str(row.get("techniqueID") or "").strip()
        tactic = str(row.get("tactic") or "").strip()
        if not tid:
            continue
        entry = canonical.setdefault(
            tid,
            {"technique_id": tid, "tactics": set(), "per_tactic_score": {}, "case_study_score": freq.get(tid, 0)},
        )
        if tactic:
            entry["tactics"].add(tactic)
            score = row.get("score")
            if score is not None:
                entry["per_tactic_score"][tactic] = score

    rows = [
        {
            "technique_id": tid,
            "tactics": sorted(entry["tactics"]),
            "per_tactic_score": dict(sorted(entry["per_tactic_score"].items())),
            "case_study_score": entry["case_study_score"],
        }
        for tid, entry in sorted(canonical.items())
    ]
    return {"technique_count": len(rows), "techniques": rows}


def build_report() -> dict:
    matrix_rows, matrix_payload = _load_layer(MATRIX_PATH)
    freq_rows, _ = _load_layer(FREQ_PATH)
    normalized = normalize(matrix_rows, freq_rows)
    return {
        "schema_role": "atlas_matrix_normalized_v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "normalization_rules_version": NORMALIZATION_RULES_VERSION,
        "provenance": {
            "source_file": str(MATRIX_PATH.relative_to(ROOT)),
            "source_sha256": _sha256_file(MATRIX_PATH),
            "atlas_data_version": matrix_payload.get("versions") or matrix_payload.get("version"),
            "raw_row_count": len(matrix_rows),
        },
        **normalized,
    }


def main() -> int:
    report = build_report()
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    out = NORMALIZED_DIR / "atlas_matrix_normalized.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"ATLAS normalized: {report['provenance']['raw_row_count']} raw rows -> "
        f"{report['technique_count']} canonical techniques "
        f"(source_sha256={report['provenance']['source_sha256'][:12]}...) -> "
        f"{out.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
