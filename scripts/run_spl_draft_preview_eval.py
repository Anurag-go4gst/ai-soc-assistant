#!/usr/bin/env python3
"""SPL draft preview evaluation — lab-only draft lane harness."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT / "backend", REPO_ROOT):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

from app.evals.spl_draft_preview_eval import (  # noqa: E402
    run_spl_draft_preview_eval,
    write_spl_draft_preview_outputs,
)

DEFAULT_JSON = REPO_ROOT / "docs" / "evals" / "spl_draft_preview_eval_report.json"
DEFAULT_MD = REPO_ROOT / "docs" / "evals" / "spl_draft_preview_eval_summary.md"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Exit non-zero on eval failures")
    parser.add_argument("--questions", type=Path, default=None, help="Override questions JSON path")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    args = parser.parse_args(argv)

    result = run_spl_draft_preview_eval(questions_path=args.questions)
    write_spl_draft_preview_outputs(result, json_path=args.json_out, md_path=args.md_out)
    print(f"Wrote {args.json_out}")
    print(f"Wrote {args.md_out}")
    print(f"Passed {result.passed_rows}/{result.total_rows}")
    qs = result.quality_summary
    print(
        "Quality SOC-STD-SPL-001: "
        f"hard_fail={qs.get('hard_fail_count', 0)} "
        f"warning={qs.get('warning_count', 0)} "
        f"advisory={qs.get('advisory_count', 0)}"
    )
    if args.check and result.failed_rows:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
