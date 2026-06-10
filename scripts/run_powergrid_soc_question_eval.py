#!/usr/bin/env python3
"""PowerGrid SOC question evaluation — live /chat API harness (Phase 13C)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT / "backend", REPO_ROOT):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

from app.evals.powergrid_soc_question_eval import (  # noqa: E402
    DEFAULT_TIMEOUT_SECONDS,
    run_powergrid_eval,
    write_powergrid_outputs,
)

DEFAULT_JSON = REPO_ROOT / "docs" / "evals" / "powergrid_soc_question_eval_report.json"
DEFAULT_MD = REPO_ROOT / "docs" / "evals" / "powergrid_soc_question_eval_summary.md"
DEFAULT_CSV = REPO_ROOT / "docs" / "evals" / "powergrid_soc_question_eval_report.csv"
DEFAULT_ANSWERS_MD = REPO_ROOT / "docs" / "evals" / "powergrid_soc_question_eval_answers.md"
DEFAULT_BANK = REPO_ROOT / "docs" / "evals" / "powergrid_soc_question_bank.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", type=str, default="http://127.0.0.1:8010", help="Backend base URL")
    parser.add_argument("--check", action="store_true", help="Fail on critical governance violations")
    parser.add_argument("--strict", action="store_true", help="Also fail --check on major warnings")
    parser.add_argument("--emit-answers", action="store_true", help="Write human-review answers markdown")
    parser.add_argument("--limit", type=int, default=None, help="Limit question rows (dev/test)")
    parser.add_argument("--question-id", type=str, default=None, help="Evaluate a single question_id")
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Per-question HTTP timeout seconds (default {DEFAULT_TIMEOUT_SECONDS})",
    )
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    parser.add_argument("--csv-out", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--answers-md-out", type=Path, default=DEFAULT_ANSWERS_MD)
    parser.add_argument("--question-bank", type=Path, default=DEFAULT_BANK)
    parser.add_argument(
        "--profile",
        choices=("default", "deterministic", "live_llm"),
        default="default",
        help="Label run and pick default output suffix (deterministic vs live_llm)",
    )
    args = parser.parse_args(argv)

    if args.profile != "default":
        suffix = "_deterministic" if args.profile == "deterministic" else "_llm"
        evals = REPO_ROOT / "docs" / "evals"
        if args.json_out == DEFAULT_JSON:
            args.json_out = evals / f"powergrid_soc_question_eval_report{suffix}.json"
        if args.md_out == DEFAULT_MD:
            args.md_out = evals / f"powergrid_soc_question_eval_summary{suffix}.md"
        if args.csv_out == DEFAULT_CSV:
            args.csv_out = evals / f"powergrid_soc_question_eval_report{suffix}.csv"
        if args.answers_md_out == DEFAULT_ANSWERS_MD:
            args.answers_md_out = evals / f"powergrid_soc_question_eval_answers{suffix}.md"

    result = run_powergrid_eval(
        base_url=args.base_url,
        timeout_seconds=args.timeout,
        limit=args.limit,
        question_id=args.question_id,
        question_bank_path=args.question_bank,
        emit_answers=args.emit_answers,
        strict=args.strict,
        eval_profile=args.profile if args.profile != "default" else "default",
    )
    write_powergrid_outputs(
        result,
        json_path=args.json_out,
        markdown_path=args.md_out,
        csv_path=args.csv_out,
        answers_markdown_path=args.answers_md_out if args.emit_answers else None,
    )
    summary = result.report.get("summary") or {}
    print(
        "powergrid_soc_question_eval:",
        f"total={summary.get('total_evaluated')}",
        f"pass={summary.get('pass_count')}",
        f"review={summary.get('review_count')}",
        f"fail={summary.get('fail_count')}",
        f"critical={summary.get('critical_violations_total')}",
        f"major={summary.get('major_warnings_total')}",
    )
    if args.emit_answers:
        print(f"answers_md={args.answers_md_out}")
    total = summary.get("total_evaluated") or 0
    pass_count = summary.get("pass_count") or 0
    verdict = "PASS" if not result.failures else "FAIL"
    print(f"RESULT: {verdict} ({pass_count}/{total} rows, {len(result.failures)} check failures)")
    if args.check and result.failures:
        for failure in result.failures:
            print(f"CHECK_FAIL:{failure}", file=sys.stderr)
        return 1
    if args.check:
        print("--check ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
