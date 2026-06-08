#!/usr/bin/env python3
"""SOC clean-answer evaluation — governed imperative /chat response quality."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT / "backend", REPO_ROOT):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

from app.evals.langgraph_dual_parity import build_parity_index, run_dual_parity_eval  # noqa: E402
from app.evals.soc_clean_answer_eval import (  # noqa: E402
    DEFAULT_TIMEOUT_SECONDS,
    run_clean_answer_eval,
    write_clean_answer_outputs,
)

DEFAULT_JSON = REPO_ROOT / "docs" / "evals" / "soc_clean_answer_eval_report.json"
DEFAULT_MD = REPO_ROOT / "docs" / "evals" / "soc_clean_answer_eval_summary.md"
DEFAULT_CSV = REPO_ROOT / "docs" / "evals" / "soc_clean_answer_eval_report.csv"
DEFAULT_ANSWERS_JSON = REPO_ROOT / "docs" / "evals" / "soc_clean_answer_eval_answers.json"
DEFAULT_ANSWERS_MD = REPO_ROOT / "docs" / "evals" / "soc_clean_answer_eval_answers.md"


def _partial_writer(path: Path, *, profile: dict[str, object] | None = None) -> Callable[[dict[str, object]], None]:
    rows: list[dict[str, object]] = []

    def _on_row_complete(row: dict[str, object]) -> None:
        rows.append(row)
        payload = {
            "schema_version": "partial",
            "profile": profile or {},
            "rows": rows,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    return _on_row_complete


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail on critical/major manual-demo violations")
    parser.add_argument("--emit-answers", action="store_true", help="Write human-review answers JSON/Markdown")
    parser.add_argument("--limit", type=int, default=None, help="Limit rows (dev/test only)")
    parser.add_argument("--skip-105", action="store_true", help="Skip 105-question map rows")
    parser.add_argument("--skip-demo", action="store_true", help="Skip demo scenario rows")
    parser.add_argument("--skip-manual", action="store_true", help="Skip known manual rows")
    parser.add_argument("--live-composer", action="store_true", help="Enable live LLM composer (optional local)")
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help=f"Per-question timeout seconds (default {DEFAULT_TIMEOUT_SECONDS}; live composer uses 120 unless set)",
    )
    parser.add_argument("--question-id", type=str, default=None, help="Evaluate a single row_id")
    parser.add_argument("--resume", action="store_true", help="Resume from existing answers JSON if present")
    parser.add_argument("--max-concurrency", type=int, default=1, help="Max concurrent question evaluations")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    parser.add_argument("--csv-out", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_ANSWERS_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_ANSWERS_MD)
    parser.add_argument("--no-csv", action="store_true")
    parser.add_argument(
        "--skip-parity",
        action="store_true",
        help="Skip LangGraph parity merge in human-review output",
    )
    args = parser.parse_args(argv)

    include_105 = not args.skip_105
    include_demo = not args.skip_demo
    include_manual = not args.skip_manual

    parity_index: dict[str, dict[str, object]] = {}
    if args.emit_answers and not args.skip_parity:
        parity_result = run_dual_parity_eval(
            limit=args.limit,
            include_105=include_105,
            include_demo=include_demo,
            include_manual=include_manual,
        )
        parity_index = build_parity_index(parity_result.report)

    on_row_complete = None
    if args.emit_answers and args.resume:
        on_row_complete = _partial_writer(args.output_json)

    result = run_clean_answer_eval(
        limit=args.limit,
        include_105=include_105,
        include_demo=include_demo,
        include_manual=include_manual,
        live_composer=args.live_composer,
        timeout_seconds=args.timeout,
        question_id=args.question_id,
        resume=args.resume,
        resume_path=args.output_json if args.resume else None,
        max_concurrency=max(1, args.max_concurrency),
        include_parity=args.emit_answers and not args.skip_parity,
        parity_index=parity_index,
        emit_answers=args.emit_answers,
        on_row_complete=on_row_complete,
    )
    write_clean_answer_outputs(
        result,
        json_path=args.json_out,
        markdown_path=args.md_out,
        csv_path=None if args.no_csv else args.csv_out,
        answers_json_path=args.output_json if args.emit_answers else None,
        answers_markdown_path=args.output_md if args.emit_answers else None,
    )
    summary = result.report.get("summary") or {}
    print(
        "soc_clean_answer_eval:",
        f"total={summary.get('total_evaluated')}",
        f"pass={summary.get('pass_count', summary.get('clean_pass_count'))}",
        f"review={summary.get('review_count', 0)}",
        f"fail={summary.get('fail_count', 0)}",
        f"critical={summary.get('critical_failures')}",
        f"major={summary.get('major_failures')}",
        f"display={summary.get('display_failures')}",
    )
    if args.emit_answers:
        print(f"answers_json={args.output_json}")
        print(f"answers_md={args.output_md}")
    if args.check and result.failures:
        for failure in result.failures:
            print(f"CHECK_FAIL:{failure}", file=sys.stderr)
        return 1
    if args.check:
        print("--check ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
