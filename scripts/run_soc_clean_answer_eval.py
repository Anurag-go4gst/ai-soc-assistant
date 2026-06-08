#!/usr/bin/env python3
"""SOC clean-answer evaluation — governed imperative /chat response quality."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT / "backend", REPO_ROOT):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

from app.evals.soc_clean_answer_eval import (  # noqa: E402
    run_clean_answer_eval,
    write_clean_answer_outputs,
)

DEFAULT_JSON = REPO_ROOT / "docs" / "evals" / "soc_clean_answer_eval_report.json"
DEFAULT_MD = REPO_ROOT / "docs" / "evals" / "soc_clean_answer_eval_summary.md"
DEFAULT_CSV = REPO_ROOT / "docs" / "evals" / "soc_clean_answer_eval_report.csv"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail on critical/major manual-demo violations")
    parser.add_argument("--limit", type=int, default=None, help="Limit rows (dev/test only)")
    parser.add_argument("--skip-105", action="store_true", help="Skip 105-question map rows")
    parser.add_argument("--skip-demo", action="store_true", help="Skip demo scenario rows")
    parser.add_argument("--skip-manual", action="store_true", help="Skip known manual rows")
    parser.add_argument("--live-composer", action="store_true", help="Enable live LLM composer (optional local)")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    parser.add_argument("--csv-out", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--no-csv", action="store_true")
    args = parser.parse_args(argv)

    result = run_clean_answer_eval(
        limit=args.limit,
        include_105=not args.skip_105,
        include_demo=not args.skip_demo,
        include_manual=not args.skip_manual,
        live_composer=args.live_composer,
    )
    write_clean_answer_outputs(
        result,
        json_path=args.json_out,
        markdown_path=args.md_out,
        csv_path=None if args.no_csv else args.csv_out,
    )
    summary = result.report.get("summary") or {}
    print(
        "soc_clean_answer_eval:",
        f"total={summary.get('total_evaluated')}",
        f"pass={summary.get('clean_pass_count')}",
        f"critical={summary.get('critical_failures')}",
        f"major={summary.get('major_failures')}",
        f"display={summary.get('display_failures')}",
    )
    if args.check and result.failures:
        for failure in result.failures:
            print(f"CHECK_FAIL:{failure}", file=sys.stderr)
        return 1
    if args.check:
        print("--check ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
