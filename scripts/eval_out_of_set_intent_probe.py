#!/usr/bin/env python3
"""Out-of-set intent probe gate (intent cascade plan §7).

Runs deterministic intent classification over novel / sentinel / non-SOC probes.

Usage:
  PYTHONPATH=backend:. python3 scripts/eval_out_of_set_intent_probe.py
  PYTHONPATH=backend:. python3 scripts/eval_out_of_set_intent_probe.py --check
  PYTHONPATH=backend:. python3 scripts/eval_out_of_set_intent_probe.py --freeze
  PYTHONPATH=backend:. python3 scripts/eval_out_of_set_intent_probe.py --json /tmp/intent_probes.json
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

from app.evals.intent_probe_eval import (  # noqa: E402
    BASELINE_PATH,
    check_against_baseline,
    evaluate_all,
    freeze_baseline,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="compare against frozen baseline")
    mode.add_argument("--freeze", action="store_true", help="write intent_out_of_set_probes_baseline.json")
    parser.add_argument("--json", type=Path, default=None, help="write full report JSON")
    args = parser.parse_args()

    started = time.monotonic()
    report = evaluate_all()
    elapsed = time.monotonic() - started

    if args.json:
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {args.json}")

    counts = report["counts"]
    for row in report["rows"]:
        status = row["severity"].upper()
        line = (
            f"  [{status}] {row['id']}: {row['intent_family']} "
            f"match={row['match_path']} clar={row['requires_clarification']}"
        )
        if row["reasons"]:
            line += f" — {'; '.join(row['reasons'])}"
        print(line)

    if args.freeze:
        if report["critical_count"]:
            print(f"refusing to freeze: {report['critical_count']} probe(s) failed expectations")
            return 1
        freeze_baseline(report)
        print(f"froze baseline {BASELINE_PATH}")
        print(
            f"RESULT: PASS ({counts['pass']}/{report['probe_count']} probes, "
            f"{counts['review']} review, {elapsed:.1f}s)"
        )
        return 0

    if args.check:
        diffs = check_against_baseline(report)
        if diffs:
            print("BASELINE DIFFS:")
            for diff in diffs:
                print(f"  - {diff}")
            print(f"RESULT: FAIL ({report['probe_count'] - len(diffs)}/{report['probe_count']} probes, {elapsed:.1f}s)")
            return 1
        print(f"RESULT: PASS ({report['probe_count']}/{report['probe_count']} probes match baseline, {elapsed:.1f}s)")
        return 0

    verdict = "PASS" if report["critical_count"] == 0 else "FAIL"
    print(
        f"RESULT: {verdict} ({counts['pass']}/{report['probe_count']} pass, "
        f"{counts['review']} review, {counts['fail']} fail, {elapsed:.1f}s)"
    )
    return 1 if report["critical_count"] else 0


if __name__ == "__main__":
    sys.exit(main())
