#!/usr/bin/env python3
"""Paraphrase intake eval (T1.2, plan rev 3 WS1) — definitive verdict.

Runs the 51-row reviewed corpus (docs/evals/paraphrase_105.jsonl) through
query understanding + intent classification only (no full pipeline — fast)
and checks each row's expectation:

- registry rows: lands on the expected canonical question_ref
- clarification rows: requires_clarification classified
- unsafe rows: human review (HIL) required
- judgment/guidance rows: intent family within the allowed class set

Usage:
  PYTHONPATH=backend:. python3 scripts/eval_paraphrase.py --check
  PYTHONPATH=backend:. python3 scripts/eval_paraphrase.py --without-semantic   # baseline mode
  PYTHONPATH=backend:. python3 scripts/eval_paraphrase.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT / "backend", REPO_ROOT):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

CORPUS_PATH = REPO_ROOT / "docs" / "evals" / "paraphrase_105.jsonl"
DEFAULT_MIN_RATE = 0.90


def _evaluate_row(row: dict) -> tuple[bool, str]:
    from app.chat.intent_classifier import build_query_to_intent
    from app.query_understanding.parser import understand_query

    expected = row.get("expected") or {}
    understanding = understand_query(row["paraphrase"])
    result = build_query_to_intent(query=row["paraphrase"], query_understanding=understanding)
    intent = result.intent_classification

    if expected.get("question_ref"):
        if understanding.mapped_question_ref != expected["question_ref"]:
            # Confused-band rule (calibration decision, 2026-06-11): extreme
            # shorthand/typo forms must never be landed silently; they pass by
            # surfacing the right row among the explicit "did you mean"
            # candidates the analyst adjudicates (T1.4 consumes these).
            if row.get("class") in {"shorthand", "typo"}:
                from app.coverage.semantic_question_index import semantic_candidates

                candidate_refs = [c["question_ref"] for c in semantic_candidates(row["paraphrase"])]
                if expected["question_ref"] in candidate_refs:
                    return True, f"candidate-band: expected ref among suggestions {candidate_refs}"
            return False, (
                f"landed {understanding.mapped_question_ref or 'nowhere'} "
                f"(path {understanding.deterministic_match_path}), expected {expected['question_ref']}"
            )
    if expected.get("requires_clarification"):
        if not (intent.requires_clarification or intent.intent_family == "clarification_required"):
            return False, f"expected clarification, got intent {intent.intent_family}"
    if expected.get("requires_hil"):
        if not (intent.requires_hil or intent.requires_clarification):
            return False, f"expected HIL/blocked, got intent {intent.intent_family}"
    if expected.get("intent_families"):
        if intent.intent_family not in set(expected["intent_families"]):
            return False, (
                f"intent {intent.intent_family} not in allowed {expected['intent_families']}"
            )
    if expected.get("must_not_confirm"):
        if intent.intent_family in {"spl_generation_and_run"}:
            return False, "judgment question escalated to execution intent"
    return True, "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 below --min-rate")
    parser.add_argument("--min-rate", type=float, default=DEFAULT_MIN_RATE)
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument(
        "--without-semantic",
        action="store_true",
        help="baseline mode: disable the T1.1 semantic tier (threshold above 1.0)",
    )
    args = parser.parse_args()

    if args.without_semantic:
        import app.coverage.semantic_question_index as sqi

        sqi.SEMANTIC_MATCH_THRESHOLD = 2.0

    rows = [json.loads(line) for line in CORPUS_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    started = time.monotonic()
    results = []
    failures = []
    by_class: dict[str, list[bool]] = {}
    for row in rows:
        try:
            passed, reason = _evaluate_row(row)
        except Exception as exc:
            passed, reason = False, f"exception {type(exc).__name__}: {exc}"
        results.append({**row, "passed": passed, "reason": reason})
        by_class.setdefault(row["class"], []).append(passed)
        if not passed:
            failures.append(f"{row['paraphrase_id']}: {reason}")
    elapsed = time.monotonic() - started

    passed_count = sum(1 for item in results if item["passed"])
    rate = passed_count / len(rows) if rows else 0.0
    for cls, outcomes in sorted(by_class.items()):
        print(f"  class {cls}: {sum(outcomes)}/{len(outcomes)}")
    if failures:
        print(f"FAILURES ({len(failures)}):")
        for item in failures:
            print(f"  - {item}")

    if args.json:
        args.json.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {args.json}")

    verdict = "PASS" if rate >= args.min_rate else "FAIL"
    mode = " [baseline: semantic tier off]" if args.without_semantic else ""
    print(f"RESULT: {verdict} ({passed_count}/{len(rows)} rows, rate {rate:.2f}, min {args.min_rate}, {elapsed:.1f}s){mode}")
    if verdict == "FAIL" and args.check:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
