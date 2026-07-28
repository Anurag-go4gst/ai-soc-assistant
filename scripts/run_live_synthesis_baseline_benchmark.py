#!/usr/bin/env python3
"""Live synthesis baseline benchmark harness (workstream E).

Default mode is deterministic stub output for operator rehearsal and unit tests.
Live HTTP probes require explicit ``--live``, ``--confirm-live``, authorization env,
and approved fixed case ids — never arbitrary query text.

Usage:
  PYTHONPATH=backend:. python3 scripts/run_live_synthesis_baseline_benchmark.py --stub
  PYTHONPATH=backend:. python3 scripts/run_live_synthesis_baseline_benchmark.py --matrix
  PYTHONPATH=backend:. python3 scripts/run_live_synthesis_baseline_benchmark.py --estimate
  PYTHONPATH=backend:. python3 scripts/run_live_synthesis_baseline_benchmark.py --stub --json /tmp/baseline.json
  AI_SOC_LIVE_BENCHMARK_AUTHORIZED=1 APP_AUTH_PASSWORD='***' \\
    PYTHONPATH=backend:. python3 scripts/run_live_synthesis_baseline_benchmark.py \\
    --live --confirm-live --base-url https://example.invalid \\
    --cases E-P1,E-P2,E-P3,E-P4,E-P5,E-P6
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
    APPROVED_LIVE_CASE_IDS,
    DEFAULT_LIVE_OUTPUT_PATH,
    DEFAULT_PROBE_MATRIX,
    LiveHarnessRejected,
    build_live_harness_config,
    estimate_live_probe_cost,
    parse_probe_matrix,
    run_live_benchmark,
    run_stub_benchmark,
    sanitize_report_error_code,
    validate_no_arbitrary_query_inputs,
)


def _default_live_cases() -> list[str]:
    return [row["case_id"] for row in DEFAULT_PROBE_MATRIX]


def _parse_cases(raw: str | None) -> list[str]:
    if not raw:
        return _default_live_cases()
    return [part.strip() for part in raw.split(",") if part.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--stub", action="store_true", help="run deterministic stub benchmark")
    mode.add_argument("--matrix", action="store_true", help="print proposed probe matrix")
    mode.add_argument("--estimate", action="store_true", help="print runtime/cost heuristic")
    mode.add_argument(
        "--live",
        action="store_true",
        help="run controlled live probes against a running backend (operator-only)",
    )
    parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="required safety acknowledgement for --live",
    )
    parser.add_argument("--base-url", type=str, default=None, help="backend base URL (required for --live)")
    parser.add_argument(
        "--cases",
        type=str,
        default=None,
        help=f"comma-separated approved case ids (max 6; default all: {','.join(sorted(APPROVED_LIVE_CASE_IDS))})",
    )
    parser.add_argument(
        "--probe-timeout-s",
        type=int,
        default=300,
        help="per-probe HTTP timeout in seconds (no retries)",
    )
    parser.add_argument(
        "--inter-probe-pause-s",
        type=float,
        default=2.0,
        help="pause between sequential probes",
    )
    parser.add_argument(
        "--message",
        type=str,
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="write sanitized report JSON (live default: /tmp/...)",
    )
    args = parser.parse_args()

    if args.matrix:
        print(
            json.dumps(
                {
                    "probe_matrix_version": "1",
                    "approved_case_ids": sorted(APPROVED_LIVE_CASE_IDS),
                    "probes": list(DEFAULT_PROBE_MATRIX),
                },
                indent=2,
            )
        )
        return 0

    if args.estimate:
        print(json.dumps(estimate_live_probe_cost(), indent=2))
        return 0

    if args.live:
        try:
            validate_no_arbitrary_query_inputs(message=args.message, query=args.query)
            config = build_live_harness_config(
                base_url=args.base_url,
                case_ids=_parse_cases(args.cases),
                confirm_live=args.confirm_live,
                probe_timeout_s=args.probe_timeout_s,
                inter_probe_pause_s=args.inter_probe_pause_s,
                message=args.message,
                query=args.query,
            )
        except LiveHarnessRejected as exc:
            print(f"ERROR: {sanitize_report_error_code(exc.code)}", file=sys.stderr)
            return 2

        report = run_live_benchmark(config)
        payload = report.to_sanitized_dict()
        output_path = args.json or Path(DEFAULT_LIVE_OUTPUT_PATH)
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {output_path}")
        print(json.dumps(payload["summary"], indent=2))
        status = "aborted" if report.aborted else "complete"
        print(
            f"RESULT: live harness {status} "
            f"({payload['run_count']} probes, evidence_class={payload['evidence_class']})"
        )
        return 1 if report.aborted else 0

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
