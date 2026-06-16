#!/usr/bin/env python3
"""ATLAS raw duplicate / multi-tactic verification gate (plan §7 E2).

Offline, deterministic, no LLM. Runs BEFORE any normalization so an operator can
review how the MITRE ATLAS Navigator layers repeat technique IDs across tactics.
Raw layers are read-only and never modified.

Three checks over the ``techniques`` rows of ATLAS_Matrix.json:
  1. cross-tactic repeats   — same techniqueID under >1 distinct tactic
  2. same-tactic duplicates — same (techniqueID, tactic) appearing >1 time
  3. parent/sub collisions  — AML.Txxxx present alongside AML.Txxxx.yyy

Writes docs/threat-intel/atlas/reports/atlas_duplicate_report.{json,md}.
Exit 0 always (a report, not a gate failure); operator reviews before normalize.
"""
from __future__ import annotations

import collections
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATLAS_DIR = ROOT / "docs" / "threat-intel" / "atlas"
MATRIX_PATH = ATLAS_DIR / "raw" / "ATLAS_Matrix.json"
REPORTS_DIR = ATLAS_DIR / "reports"


def _load_layer(path: Path) -> list[dict]:
    """Return the ``techniques`` rows of an ATLAS Navigator layer.

    Raises FileNotFoundError/ValueError loudly — this is an operator tool, not the
    air-gapped runtime, so a missing raw file is a setup error worth surfacing.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    techniques = payload.get("techniques") if isinstance(payload, dict) else None
    if not isinstance(techniques, list):
        raise ValueError(f"{path.name}: no 'techniques' list in layer")
    return [row for row in techniques if isinstance(row, dict)]


def _parent_id(technique_id: str) -> str:
    """AML.T0051.000 -> AML.T0051; parent IDs return themselves."""
    parts = technique_id.split(".")
    # AML . Txxxx . yyy  -> three dot-segments for a sub-technique.
    return ".".join(parts[:2]) if len(parts) > 2 else technique_id


def analyze(rows: list[dict]) -> dict:
    id_tactics: dict[str, set[str]] = {}
    pair_counts: collections.Counter[tuple[str, str]] = collections.Counter()
    all_ids: set[str] = set()

    for row in rows:
        tid = str(row.get("techniqueID") or "").strip()
        tactic = str(row.get("tactic") or "").strip()
        if not tid:
            continue
        all_ids.add(tid)
        id_tactics.setdefault(tid, set()).add(tactic)
        pair_counts[(tid, tactic)] += 1

    cross_tactic = {
        tid: sorted(tactics)
        for tid, tactics in sorted(id_tactics.items())
        if len(tactics) > 1
    }
    same_tactic = {
        f"{tid}|{tactic}": count
        for (tid, tactic), count in sorted(pair_counts.items())
        if count > 1
    }

    # Parent/sub collisions: a sub-technique whose parent ID is also present.
    subs = {tid for tid in all_ids if len(tid.split(".")) > 2}
    parent_sub = {
        sub: _parent_id(sub)
        for sub in sorted(subs)
        if _parent_id(sub) in all_ids
    }

    return {
        "schema_role": "atlas_duplicate_report_v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_file": str(MATRIX_PATH.relative_to(ROOT)),
        "row_count": len(rows),
        "distinct_technique_count": len(all_ids),
        "cross_tactic_repeat_count": len(cross_tactic),
        "same_tactic_duplicate_count": len(same_tactic),
        "parent_sub_collision_count": len(parent_sub),
        "cross_tactic_repeats": cross_tactic,
        "same_tactic_duplicates": same_tactic,
        "parent_sub_collisions": parent_sub,
        "note": (
            "ATLAS Navigator layers may legitimately repeat a techniqueID across "
            "tactics. Do NOT collapse until this report is reviewed (plan §7 E2)."
        ),
    }


def _render_md(report: dict) -> str:
    lines = [
        "# ATLAS raw duplicate / multi-tactic report",
        "",
        f"- Generated: `{report['generated_at_utc']}`",
        f"- Source: `{report['source_file']}`",
        f"- Rows: **{report['row_count']}** → distinct techniqueIDs: "
        f"**{report['distinct_technique_count']}**",
        f"- Cross-tactic repeats: **{report['cross_tactic_repeat_count']}**",
        f"- Same-tactic duplicates: **{report['same_tactic_duplicate_count']}**",
        f"- Parent/sub collisions: **{report['parent_sub_collision_count']}**",
        "",
        f"> {report['note']}",
        "",
        "## Cross-tactic repeats (same ID under multiple tactics)",
        "",
    ]
    if report["cross_tactic_repeats"]:
        lines.append("| techniqueID | tactics |")
        lines.append("|---|---|")
        for tid, tactics in report["cross_tactic_repeats"].items():
            lines.append(f"| `{tid}` | {', '.join(tactics)} |")
    else:
        lines.append("_None._")
    lines += ["", "## Same-tactic duplicates", ""]
    if report["same_tactic_duplicates"]:
        lines.append("| techniqueID\\|tactic | count |")
        lines.append("|---|---|")
        for key, count in report["same_tactic_duplicates"].items():
            lines.append(f"| `{key}` | {count} |")
    else:
        lines.append("_None._")
    lines += ["", "## Parent/sub collisions", ""]
    if report["parent_sub_collisions"]:
        lines.append("| sub-technique | parent also present |")
        lines.append("|---|---|")
        for sub, parent in report["parent_sub_collisions"].items():
            lines.append(f"| `{sub}` | `{parent}` |")
    else:
        lines.append("_None._")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    rows = _load_layer(MATRIX_PATH)
    report = analyze(rows)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "atlas_duplicate_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    (REPORTS_DIR / "atlas_duplicate_report.md").write_text(
        _render_md(report), encoding="utf-8"
    )
    print(
        f"ATLAS duplicate report: {report['row_count']} rows, "
        f"{report['distinct_technique_count']} distinct, "
        f"{report['cross_tactic_repeat_count']} cross-tactic, "
        f"{report['same_tactic_duplicate_count']} same-tactic dup, "
        f"{report['parent_sub_collision_count']} parent/sub collisions "
        f"-> {REPORTS_DIR.relative_to(ROOT)}/atlas_duplicate_report.{{json,md}}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
