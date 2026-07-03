#!/usr/bin/env python3
"""Capture in-catalogue (105/50) answer-contract fixtures for plan 0.3.

Usage:
  PYTHONPATH=backend:. python3 scripts/capture_in_catalogue_contract_fixtures.py --freeze
  PYTHONPATH=backend:. python3 scripts/capture_in_catalogue_contract_fixtures.py --check
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT / "backend", REPO_ROOT):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from app.evals.in_catalogue_contract import (  # noqa: E402
    BASELINE_PATH,
    capture_all,
    check_against_baseline,
    freeze_baseline,
    iter_in_catalogue_entries,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()

    entries = iter_in_catalogue_entries()
    print(f"catalogue entries: {len(entries)}")
    rows = capture_all(entries)

    if args.freeze:
        errors = freeze_baseline(rows)
        if errors:
            print(f"refusing freeze: {len(errors)} error row(s), first={errors[0]}")
            return 1
        print(f"froze {BASELINE_PATH} ({len(rows)} rows)")
        return 0

    diffs = check_against_baseline(rows)
    if diffs:
        print("CONTRACT DRIFT:")
        for diff in diffs[:20]:
            print(f"  - {diff}")
        if len(diffs) > 20:
            print(f"  ... and {len(diffs) - 20} more")
        return 1
    print(f"RESULT: PASS ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
