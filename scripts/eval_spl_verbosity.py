"""Phase A verbosity metric (secondary) — pipe count and char length per SPL lane.

Used only to support the Phase E simplifier work. Verbosity is NOT a quality
goal on its own; this script measures the size of correct SPL, never grades it.
Reuses the resolvers from eval_spl_relevance so lanes match exactly.

Usage:
    PYTHONPATH=backend:. python3 scripts/eval_spl_verbosity.py
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

from eval_spl_relevance import (  # noqa: E402  shared resolvers, same lanes
    _eval_105,
    _eval_catalogue,
    _load_active_templates,
    resolve_spl_for_query,
)

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "backend" / "app" / "coverage" / "question_runtime_map_v1.json"
CATALOG_PATH = ROOT / "backend" / "app" / "use_cases" / "catalog.json"
REPORT_MD = ROOT / "docs" / "evals" / "spl_verbosity_summary.md"


def _spl_for_row(row, active):
    if row["corpus"] == "105":
        return resolve_spl_for_query(row["question"], pattern_type=row["pattern_type"],
                                     active_templates=active)[0]
    return resolve_spl_for_query(row["question"], use_case_id=row["ref"],
                                 active_templates=active)[0]


def main() -> int:
    active = _load_active_templates()
    rows = _eval_105(active) + _eval_catalogue(active)
    by_lane: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for row in rows:
        spl = _spl_for_row(row, active)
        if not spl:
            continue
        by_lane[row["lane"]].append((spl.count("|"), len(spl)))

    lines = ["# SPL Verbosity (Phase A, secondary metric)", "",
             "| Lane | n | median pipes | max pipes | median chars | max chars |",
             "|------|---|--------------|-----------|--------------|-----------|"]
    print("SPL VERBOSITY (pipes / chars by lane)")
    for lane in sorted(by_lane):
        pipes = [p for p, _ in by_lane[lane]]
        chars = [c for _, c in by_lane[lane]]
        med_p, max_p = int(statistics.median(pipes)), max(pipes)
        med_c, max_c = int(statistics.median(chars)), max(chars)
        print(f"  {lane:9s}: n={len(pipes):3d}  pipes med={med_p} max={max_p}  "
              f"chars med={med_c} max={max_c}")
        lines.append(f"| {lane} | {len(pipes)} | {med_p} | {max_p} | {med_c} | {max_c} |")
    lines += ["", "> Measures size of *correct* SPL for Phase E simplifier targeting. "
              "Not a quality grade."]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  report: {REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
