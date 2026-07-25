#!/usr/bin/env python3
"""Production dual-runtime parity — imperative canonical vs Resource Planner graph.

Scratch-only until plan item 35 lands the artifact-safe writer: this script refuses to
write anywhere under ``docs/evals/``.

Usage:
  PYTHONPATH=backend:. python3 scripts/run_production_parity_eval.py --out-dir /tmp/parity
  PYTHONPATH=backend:. python3 scripts/run_production_parity_eval.py --out-dir /tmp/parity --check
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT / "backend", REPO_ROOT):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

from app.evals.production_runtime_parity import (  # noqa: E402
    RuntimeFallbackError,
    run_production_parity,
    validate_report,
    write_report,
)

_FORBIDDEN_OUTPUT = REPO_ROOT / "docs" / "evals"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True, help="scratch directory for the report")
    parser.add_argument("--check", action="store_true", help="exit 1 on corpus/metadata failure or critical mismatch")
    parser.add_argument("--limit", type=int, default=None, help="dev only; forces --no-check and taints the report")
    args = parser.parse_args(argv)

    out_dir = args.out_dir.resolve()
    if out_dir == _FORBIDDEN_OUTPUT or _FORBIDDEN_OUTPUT in out_dir.parents:
        print(f"refusing to write under {_FORBIDDEN_OUTPUT} before plan item 35", file=sys.stderr)
        return 2

    rows = None
    if args.limit is not None:
        from app.evals.langgraph_dual_parity import load_eval_rows

        rows = load_eval_rows()[: args.limit]

    try:
        report = run_production_parity(rows)
    except RuntimeFallbackError as exc:
        print(f"RUNTIME FALLBACK: {exc}", file=sys.stderr)
        return 3

    if args.limit is not None:
        report["metadata"]["partial_run"] = True

    path = write_report(report, out_dir)
    summary = report["summary"]
    meta = report["metadata"]
    print(
        f"production_parity: total={meta['corpus_count']} base_105={meta['base_105_loaded']} "
        f"exact={summary['exact_match']} approved={summary['approved_difference']} "
        f"critical={summary['critical_mismatch']}"
    )
    print(f"wrote {path}")

    if args.check:
        if args.limit is not None:
            print("CHECK_FAIL: partial run cannot satisfy --check", file=sys.stderr)
            return 1
        failures = validate_report(report)
        for failure in failures:
            print(f"CHECK_FAIL: {failure}", file=sys.stderr)
        return 1 if failures else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
