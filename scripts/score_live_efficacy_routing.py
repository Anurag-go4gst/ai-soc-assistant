#!/usr/bin/env python3
"""Score deterministic `/chat` routing against the P1 expected-behavior labels.

P1 step 2 gate (plan `plans/2026-06-21_live-efficacy-remediation-and-test-quality.md`).

Runs the CURRENT deterministic understanding→route stack offline (no LLM, no
network) for every labeled row and reports:
- skill precision = selected_skill in acceptable_skills;
- skill recall    = of rows whose primary intent maps to a single required skill,
  how many got an acceptable skill;
- knowledge_recall over-capture / silent collapse of investigation+SPL rows.

This is reproducible and reflects live behavior because the same
`understand_query` + `select_route_from_understanding` deterministic path backs the
live `/chat` route. (The historical `results.json` capture is kept only for the
original pre-fix baseline.)

Run: `python3 scripts/score_live_efficacy_routing.py [--check]`
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from collections import Counter
from pathlib import Path

warnings.filterwarnings("ignore")

REPO = Path(__file__).resolve().parents[1]
LABELS = REPO / "docs/evals/live_efficacy_100_labels.json"
BANK = REPO / "docs/evals/live_efficacy_100_bank.json"

PRECISION_FLOOR = 0.90
RECALL_FLOOR = 0.85

_INVESTIGATION_OR_SPL = {
    "spl_generation_only",
    "spl_generation_and_run",
    "guided_investigation",
    "live_investigation",
    "mitre_mapping",
}


def _route(question: str) -> str:
    # Import inside so the script can run from the repo root with backend on path.
    for p in (str(REPO / "backend"), str(REPO)):
        if p not in sys.path:
            sys.path.insert(0, p)
    from app.query_understanding.parser import understand_query
    from app.routing.select_route_from_understanding import select_route_from_understanding

    understanding = understand_query(question)
    base, _ = select_route_from_understanding(understanding, question)
    return str(base.get("skill"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit non-zero if gate floors not met")
    args = ap.parse_args()

    labels = {r["id"]: r for r in json.loads(LABELS.read_text())["labels"]}
    bank = json.loads(BANK.read_text())["questions"]

    scored: list[dict] = []
    for q in bank:
        lbl = labels[q["id"]]
        skill = _route(q["question"])
        acceptable = set(lbl["acceptable_skills"])
        scored.append(
            {
                "id": q["id"],
                "category": lbl["category"],
                "expected_intent": lbl["primary_intent"],
                "acceptable_skills": sorted(acceptable),
                "selected_skill": skill,
                "skill_ok": skill in acceptable,
            }
        )

    n = len(scored)
    correct = sum(1 for s in scored if s["skill_ok"])
    precision = correct / n if n else 0.0

    # recall: rows with a single required skill (excludes boundary refusals)
    single = [s for s in scored if len(s["acceptable_skills"]) == 1 and s["expected_intent"] not in {"out_of_scope", "unsafe_execution"}]
    recall = (sum(1 for s in single if s["skill_ok"]) / len(single)) if single else 1.0

    collapse = [
        s for s in scored
        if s["selected_skill"] == "knowledge_recall"
        and "knowledge_recall" not in s["acceptable_skills"]
        and s["expected_intent"] in _INVESTIGATION_OR_SPL
    ]

    print("=== P1 routing scorecard (current deterministic router, offline) ===")
    print(f"rows: {n}")
    print(f"skill precision: {correct}/{n} = {precision:.1%}  (floor {PRECISION_FLOOR:.0%})")
    print(f"skill recall (single-required): {len(single)-sum(1 for s in single if not s['skill_ok'])}/{len(single)} = {recall:.1%}  (floor {RECALL_FLOOR:.0%})")
    print(f"selected_skill distribution: {dict(Counter(s['selected_skill'] for s in scored))}")
    print(f"investigation/SPL collapsed to knowledge_recall: {len(collapse)}  (must be 0)")
    for s in scored:
        if not s["skill_ok"]:
            print(f"  MISS {s['id']} [{s['category']}] expected={s['expected_intent']} acceptable={s['acceptable_skills']} got={s['selected_skill']}")

    gate_ok = precision >= PRECISION_FLOOR and recall >= RECALL_FLOOR and len(collapse) == 0
    print(f"\nGATE precision/recall floors + zero-collapse: {'PASS' if gate_ok else 'FAIL'}")
    if args.check and not gate_ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
