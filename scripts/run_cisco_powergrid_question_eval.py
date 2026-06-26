#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("AI_SOC_SPL_DRAFT_PREVIEW_ENABLED", "true")
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT))

from app.evals.cisco_powergrid_soc_question_eval import run_cisco_eval  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic Cisco power-grid question eval")
    parser.add_argument("--question-bank", type=Path, default=REPO_ROOT / "docs/evals/cisco_powergrid_question_bank.json")
    parser.add_argument("--json-out", type=Path, default=REPO_ROOT / "docs/evals/cisco_powergrid_soc_question_eval_report_deterministic.json")
    parser.add_argument("--md-out", type=Path, default=REPO_ROOT / "docs/evals/cisco_powergrid_soc_question_eval_summary_deterministic.md")
    parser.add_argument("--min-wave", choices=["batch1", "batch2_metadata", "wave1", "wave2", "wave3"], default="wave3")
    parser.add_argument("--profile", default="deterministic")
    parser.add_argument("--question-id", default="")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    report = run_cisco_eval(args.question_bank, min_wave=args.min_wave, question_id=args.question_id or None)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = [
        "# Cisco PowerGrid Eval Summary",
        "",
        f"- Profile: `{args.profile}`",
        f"- Min wave: `{args.min_wave}`",
        f"- PASS: {report['pass']}",
        f"- REVIEW: {report['review']}",
        f"- FAIL: {report['fail']}",
        f"- Critical violations: {report['critical_violations']}",
        "",
    ]
    args.md_out.write_text("\n".join(summary), encoding="utf-8")
    print(
        "cisco_powergrid_question_eval:",
        f"PASS={report['pass']}",
        f"REVIEW={report['review']}",
        f"FAIL={report['fail']}",
        f"CRITICAL={report['critical_violations']}",
    )
    if args.check and (report["fail"] or report["critical_violations"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
