#!/usr/bin/env python3
"""Sentinel happy-path gate — required before every commit (plan rev 3, B3).

Runs the 17-row frozen sentinel set through the real in-process chat pipeline
and verdicts against backend/app/evals/fixtures/sentinel_baseline.json.

Usage:
  PYTHONPATH=backend:. python3 scripts/eval_sentinel.py --check     # gate
  PYTHONPATH=backend:. python3 scripts/eval_sentinel.py --freeze    # new baseline
  PYTHONPATH=backend:. python3 scripts/eval_sentinel.py --json out.json
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

from app.evals.sentinel_eval import (  # noqa: E402
    BASELINE_PATH,
    check_against_baseline,
    freeze_baseline,
    load_sentinel_rows,
    run_sentinel,
)


def baseline_row_keys() -> set[str]:
    """Row keys in the frozen baseline, for attributing diffs to rows."""
    if not BASELINE_PATH.exists():
        return set()
    return set(json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("rows", {}))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="compare against frozen baseline; exit 1 on diff")
    mode.add_argument("--freeze", action="store_true", help="write a new baseline fixture")
    parser.add_argument("--json", type=Path, default=None, help="write per-row captures JSON")
    args = parser.parse_args()

    rows = load_sentinel_rows()
    started = time.monotonic()
    captures = run_sentinel(rows)
    elapsed = time.monotonic() - started
    total = len(rows)

    if args.json:
        args.json.write_text(json.dumps(captures, indent=2, sort_keys=True), encoding="utf-8")
        print(f"wrote {args.json}")

    if args.freeze:
        errors = freeze_baseline(captures)
        if errors:
            print(f"refusing to freeze: rows errored: {', '.join(errors)}")
            print(f"RESULT: FAIL ({total - len(errors)}/{total} rows, {elapsed:.1f}s)")
            return 1
        print(f"froze baseline {BASELINE_PATH}")
        print(f"RESULT: PASS ({total}/{total} rows frozen, {elapsed:.1f}s)")
        return 0

    diffs = check_against_baseline(captures)
    if diffs:
        # Row keys are themselves dotted ("q0.q045", "pg.dns.001"), so splitting a diff
        # string on "." collapsed every row into its prefix ("q0", "pg") and the summary
        # reported a constant "15/17" no matter how many rows actually differed. Match
        # the diff against the real row keys instead.
        row_keys = sorted(set(captures) | set(baseline_row_keys()), key=len, reverse=True)
        failed_keys = set()
        for diff in diffs:
            for key in row_keys:
                if diff.startswith(f"{key}.") or diff.startswith(f"{key}:"):
                    failed_keys.add(key)
                    break
        print(f"DIFFS ({len(diffs)}):")
        for diff in diffs:
            print(f"  - {diff}")
        print(f"RESULT: FAIL ({total - len(failed_keys)}/{total} rows, {elapsed:.1f}s)")
        return 1
    print(f"RESULT: PASS ({total}/{total} rows, {elapsed:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
