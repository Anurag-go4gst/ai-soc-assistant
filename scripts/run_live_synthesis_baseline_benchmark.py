#!/usr/bin/env python3
"""Live synthesis baseline benchmark harness (workstream E phase 1).

Default mode is deterministic stub output for operator rehearsal and unit tests.
Live HTTP probes require explicit ``--live`` and run outside CI.

Usage:
  PYTHONPATH=backend:. python3 scripts/run_live_synthesis_baseline_benchmark.py --stub
  PYTHONPATH=backend:. python3 scripts/run_live_synthesis_baseline_benchmark.py --matrix
  PYTHONPATH=backend:. python3 scripts/run_live_synthesis_baseline_benchmark.py --estimate
  PYTHONPATH=backend:. python3 scripts/run_live_synthesis_baseline_benchmark.py --stub --json /tmp/baseline.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT / "backend", REPO_ROOT):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

from app.evals.live_synthesis_benchmark import (  # noqa: E402
    DEFAULT_PROBE_MATRIX,
    estimate_live_probe_cost,
    parse_probe_matrix,
    run_stub_benchmark,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--stub", action="store_true", help="run deterministic stub benchmark")
    mode.add_argument("--matrix", action="store_true", help="print proposed probe matrix")
    mode.add_argument("--estimate", action="store_true", help="print runtime/cost heuristic")
    mode.add_argument(
        "--live",
        action="store_true",
        help="reserved for controlled baseline (requires running backend + live synthesis flags)",
    )
    parser.add_argument("--json", type=Path, default=None, help="write sanitized report JSON")
    args = parser.parse_args()

    if args.matrix:
        print(json.dumps({"probe_matrix_version": "1", "probes": list(DEFAULT_PROBE_MATRIX)}, indent=2))
        return 0

    if args.estimate:
        print(json.dumps(estimate_live_probe_cost(), indent=2))
        return 0

    if args.live:
        print(
            "ERROR: --live baseline probes are not enabled in phase 1. "
            "Use instrumentation on a running backend after COE review.",
            file=sys.stderr,
        )
        return 2

    report = run_stub_benchmark(parse_probe_matrix())
    payload = report.to_sanitized_dict()
    if args.json:
        args.json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {args.json}")
    print(json.dumps(payload["summary"], indent=2))
    print(f"RESULT: stub benchmark complete ({payload['run_count']} probes, mode={payload['mode']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
