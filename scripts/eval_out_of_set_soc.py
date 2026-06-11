#!/usr/bin/env python3
"""Out-of-set SOC corpus eval runner (WS5.3) + optional LLM judge (WS5.2).

Deterministic mode is the gate; the LLM judge is offline-eval-only, optional,
and can never change the deterministic verdict or any runtime behavior.

Usage:
  PYTHONPATH=backend:. python3 scripts/eval_out_of_set_soc.py --check
  PYTHONPATH=backend:. python3 scripts/eval_out_of_set_soc.py --check --llm-judge
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT / "backend", REPO_ROOT):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

DEFAULT_JSON = REPO_ROOT / "docs" / "evals" / "out_of_set_soc_eval_report.json"
DEFAULT_MD = REPO_ROOT / "docs" / "evals" / "out_of_set_soc_eval_summary.md"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 on any critical FAIL row")
    parser.add_argument("--llm-judge", action="store_true", help="offline LLM judge (optional, never gating)")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()

    from app.evals.out_of_set_eval import evaluate_corpus

    started = time.monotonic()
    report = evaluate_corpus()
    elapsed = time.monotonic() - started

    judge_summary = None
    if args.llm_judge:
        from app.evals.llm_judge import judge_report

        judge_summary = judge_report(report)
        report["judge"] = judge_summary

    counts = report["counts"]
    report["generated_in_seconds"] = round(elapsed, 1)
    args.json_out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    args.md_out.write_text(_render_markdown(report), encoding="utf-8")
    print(f"wrote {args.json_out}")
    print(f"wrote {args.md_out}")

    for row in report["rows"]:
        if row["severity"] != "pass":
            print(f"  [{row['severity'].upper()}] {row['question_id']}: {('; '.join(row['reasons']))[:160]}")
    if judge_summary:
        print(
            "judge:",
            f"enabled={judge_summary['judge_enabled']}",
            f"attempted={judge_summary['judge_attempted']}",
            f"used={judge_summary['judge_used']}",
            f"status_counts={judge_summary['status_counts']}",
        )

    verdict = "PASS" if report["critical_count"] == 0 else "FAIL"
    print(
        f"RESULT: {verdict} ({counts['pass']}/{report['total']} pass, "
        f"{counts['review']} review, {counts['fail']} fail-critical, {elapsed:.1f}s)"
    )
    if verdict == "FAIL" and args.check:
        return 1
    return 0


def _render_markdown(report: dict) -> str:
    counts = report["counts"]
    lines = [
        "# Out-of-set SOC corpus eval",
        "",
        f"- Total: **{report['total']}**",
        f"- PASS / REVIEW / FAIL: **{counts['pass']}** / **{counts['review']}** / **{counts['fail']}**",
        f"- Critical violations: **{report['critical_count']}**",
        "",
    ]
    judge = report.get("judge")
    if judge:
        lines += [
            "## LLM judge (offline, non-gating)",
            "",
            f"- enabled/attempted/used: {judge['judge_enabled']}/{judge['judge_attempted']}/{judge['judge_used']}",
            f"- status counts: {judge['status_counts']}",
            f"- provider: {judge.get('judge_provider')}",
            "",
        ]
    flagged = [row for row in report["rows"] if row["severity"] != "pass"]
    if flagged:
        lines.append("## Non-pass rows")
        lines.append("")
        for row in flagged:
            lines.append(f"- `{row['question_id']}` **{row['severity']}** — {('; '.join(row['reasons']))[:220]}")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
