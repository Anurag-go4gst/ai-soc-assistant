#!/usr/bin/env python3
"""Production dual-runtime parity evaluation — authoritative committed artifacts.

Full-corpus runs to ``docs/evals/langgraph_dual_parity_*`` compare the two real
production entry points (``imperative_canonical`` vs ``resource_planner_graph``)
and write through the artifact-safe writer (plan item 35).

Partial runs (``--limit``, ``--skip-105``, etc.) are refused when targeting
committed eval artifacts.
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

from app.evals.artifact_safe_writer import ArtifactWriteRefused, is_committed_eval_path
from app.evals.langgraph_dual_parity import (  # noqa: E402
    run_dual_parity_eval,
    validate_check_report,
    write_dual_parity_outputs,
)
from app.evals.production_runtime_parity import (  # noqa: E402
    RuntimeFallbackError,
    prepare_committed_report,
    run_production_parity,
    validate_report,
    write_production_parity_committed_artifacts,
)

DEFAULT_JSON = REPO_ROOT / "docs" / "evals" / "langgraph_dual_parity_report.json"
DEFAULT_MD = REPO_ROOT / "docs" / "evals" / "langgraph_dual_parity_summary.md"
DEFAULT_CSV = REPO_ROOT / "docs" / "evals" / "langgraph_dual_parity_report.csv"
DEFAULT_DETAILS_MD = REPO_ROOT / "docs" / "evals" / "langgraph_dual_parity_answers.md"


def _is_partial(include_105: bool, include_demo: bool, include_manual: bool, limit: int | None) -> bool:
    return limit is not None or not include_105 or not include_demo or not include_manual


def _targets_committed(*paths: Path) -> bool:
    return any(is_committed_eval_path(path) for path in paths)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail on corpus/metadata/critical mismatch")
    parser.add_argument("--emit-details", action="store_true", help="Write human-review parity details Markdown")
    parser.add_argument("--limit", type=int, default=None, help="Limit rows (dev/test only; refused for committed artifacts)")
    parser.add_argument("--skip-105", action="store_true", help="Skip 105-question map rows")
    parser.add_argument("--skip-demo", action="store_true", help="Skip demo scenario rows")
    parser.add_argument("--skip-manual", action="store_true", help="Skip manual scenario rows")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    parser.add_argument("--csv-out", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_DETAILS_MD)
    parser.add_argument("--no-csv", action="store_true")
    args = parser.parse_args(argv)

    include_105 = not args.skip_105
    include_demo = not args.skip_demo
    include_manual = not args.skip_manual
    partial = _is_partial(include_105, include_demo, include_manual, args.limit)
    csv_path = None if args.no_csv else args.csv_out
    output_paths = [args.json_out, args.md_out]
    if csv_path is not None:
        output_paths.append(csv_path)
    if args.emit_details:
        output_paths.append(args.output_md)
    committed = _targets_committed(*output_paths)

    command = " ".join(["python3", "scripts/run_langgraph_dual_parity_eval.py", *sys.argv[1:]])

    if committed and partial:
        print(
            "refusing partial run targeting committed eval artifacts "
            f"(limit={args.limit} skip_105={args.skip_105} skip_demo={args.skip_demo} skip_manual={args.skip_manual})",
            file=sys.stderr,
        )
        return 2

    if committed:
        rows = None
        if args.limit is not None:
            from app.evals.langgraph_dual_parity import load_eval_rows

            rows = load_eval_rows(
                include_105=include_105,
                include_demo=include_demo,
                include_manual=include_manual,
            )[: args.limit]
        try:
            report = run_production_parity(rows)
        except RuntimeFallbackError as exc:
            print(f"RUNTIME FALLBACK: {exc}", file=sys.stderr)
            return 3
        try:
            write_production_parity_committed_artifacts(
                report,
                json_path=args.json_out,
                markdown_path=args.md_out,
                csv_path=csv_path,
                command=command,
            )
        except ArtifactWriteRefused as exc:
            print(f"ARTIFACT_WRITE_REFUSED: {exc}", file=sys.stderr)
            return 4
        prepared = prepare_committed_report(report, command=command)
        summary = prepared.get("summary") or {}
        meta = prepared.get("metadata") or {}
        print(
            "dual_parity_eval:",
            f"total={meta.get('corpus_count')}",
            f"exact={summary.get('exact_match')}",
            f"approved={summary.get('approved_difference')}",
            f"critical={summary.get('critical_mismatch')}",
        )
        if args.check:
            failures = validate_report(prepared)
            for failure in failures:
                print(f"CHECK_FAIL:{failure}", file=sys.stderr)
            if failures:
                return 1
            print("--check ok")
        return 0

    # Scratch / dev path — legacy shadow-graph parity for phase-13 unit probes.
    result = run_dual_parity_eval(
        limit=args.limit,
        include_105=include_105,
        include_demo=include_demo,
        include_manual=include_manual,
    )
    write_dual_parity_outputs(
        result,
        json_path=args.json_out,
        markdown_path=args.md_out,
        csv_path=csv_path,
        details_markdown_path=args.output_md if args.emit_details else None,
        command=command,
    )
    summary = result.report.get("summary") or {}
    print(
        "dual_parity_eval:",
        f"total={summary.get('total')}",
        f"match={summary.get('exact_matches')}",
        f"acceptable={summary.get('acceptable_differences')}",
        f"mismatch={summary.get('mismatches')}",
    )
    if args.emit_details:
        print(f"details_md={args.output_md}")
    if args.check:
        if partial:
            print("CHECK_FAIL: partial run cannot satisfy --check", file=sys.stderr)
            return 1
        failures = validate_check_report(result.report)
        for failure in failures:
            print(f"CHECK_FAIL:{failure}", file=sys.stderr)
        if failures:
            return 1
        print("--check ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
