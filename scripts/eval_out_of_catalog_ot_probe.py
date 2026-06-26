#!/usr/bin/env python3
"""Out-of-catalog OT probe gate — natural analyst asks not in 105/50 catalogue.

Usage:
  PYTHONPATH=backend:. python3 scripts/eval_out_of_catalog_ot_probe.py
  PYTHONPATH=backend:. python3 scripts/eval_out_of_catalog_ot_probe.py --check
  PYTHONPATH=backend:. python3 scripts/eval_out_of_catalog_ot_probe.py --freeze
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT / "backend", REPO_ROOT):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

from app.evals.out_of_catalog_ot_probe import (  # noqa: E402
    BASELINE_PATH,
    check_against_baseline,
    evaluate_all,
    freeze_baseline,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="fail on violations or baseline drift")
    mode.add_argument("--freeze", action="store_true", help="write baseline JSON (requires green run)")
    parser.add_argument("--json", type=Path, default=None, help="write full report JSON")
    parser.add_argument(
        "--synthesis-enabled",
        action="store_true",
        help="also enforce live LLM composer expectations (off in CI)",
    )
    args = parser.parse_args()

    started = time.monotonic()
    report = evaluate_all(synthesis_enabled=args.synthesis_enabled)
    elapsed = time.monotonic() - started

    if args.json:
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {args.json}")

    for row in report["rows"]:
        status = row["severity"].upper()
        obs = row.get("observed") or {}
        line = (
            f"  [{status}] {row['id']}: skill={obs.get('selected_skill')} "
            f"signal={obs.get('signal_class')} actions={obs.get('action_count')}"
        )
        if row.get("violations"):
            line += f" — {row['violations']}"
        print(line)

    counts = report["counts"]
    if args.freeze:
        if report["critical_count"]:
            print(f"refusing to freeze: {report['critical_count']} probe(s) failed")
            return 1
        freeze_baseline(report)
        print(f"froze baseline {BASELINE_PATH}")
        print(f"RESULT: PASS ({counts['pass']}/{report['probe_count']} probes, {elapsed:.1f}s)")
        return 0

    if args.check:
        if report["critical_count"]:
            print(f"RESULT: FAIL violations ({counts['fail']} fail, {counts['error']} error)")
            return 1
        diffs = check_against_baseline(report)
        if diffs:
            print("BASELINE DIFFS:")
            for diff in diffs:
                print(f"  - {diff}")
            print(f"RESULT: FAIL baseline ({len(diffs)} diff(s), {elapsed:.1f}s)")
            return 1
        print(f"RESULT: PASS ({counts['pass']}/{report['probe_count']} probes, {elapsed:.1f}s)")
        return 0

    print(json.dumps({"counts": counts, "critical_count": report["critical_count"]}, indent=2))
    return 0 if not report["critical_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
