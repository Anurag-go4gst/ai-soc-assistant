#!/usr/bin/env python3
"""Stage 3K-Q4A author-time coverage drafter CLI.

LLM assistance is candidate-only. Deterministic core owns validation, normalization,
binding, rendering, execution eligibility, and all blocking decisions. If LLM output
disagrees with deterministic validation, deterministic wins and the disagreement
is recorded.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _REPO_ROOT / "backend"
_TOOL_DIR = Path(__file__).resolve().parent
for _path in (str(_BACKEND), str(_TOOL_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from app.coverage.coverage_models import PatternCoverageEntry  # noqa: E402

from draft_schema import CoverageDraftDocument, GENERATED_BY  # noqa: E402
from deterministic import draft_entry_deterministic  # noqa: E402
from io_utils import (  # noqa: E402
    draft_output_path,
    load_draft_document,
    load_entry_json,
    resolve_draft_path,
    write_draft_document,
)
from llm_assist import assert_instruct_only, draft_entry_with_llm  # noqa: E402
from registries import load_registry_snapshot  # noqa: E402
from taxonomy_lookup import resolve_question_input  # noqa: E402
from validator import validate_draft_entry  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stage 3K-Q4A author-time coverage entry drafter (drafts only).",
    )
    parser.add_argument("--question", help="SOC question text")
    parser.add_argument("--question-ref", help="Taxonomy ref, e.g. q004 or q0.q004")
    parser.add_argument(
        "--entry-json",
        help="Manual mode: path to JSON with entry fields (validated, then written as draft)",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Request Instruct-only LLM assist (requires --llm-raw-file or env provider)",
    )
    parser.add_argument(
        "--llm-raw-file",
        help="Path to a file containing LLM JSON output (author-time testing; no live call)",
    )
    parser.add_argument("--llm-model-family", default="instruct", help="Must be instruct family")
    parser.add_argument("--llm-provider", default="manual", help="Provider label for audit")
    parser.add_argument(
        "--output",
        type=Path,
        help="Draft output path (must be under tools/coverage_authoring/drafts/)",
    )
    parser.add_argument(
        "--validate-draft",
        type=Path,
        help="Validate an existing draft JSON file and exit",
    )
    parser.add_argument(
        "--taxonomy",
        type=Path,
        help="Override path to docs/soc_question_taxonomy_stage3k_q0.md",
    )
    parser.add_argument(
        "--allow-validation-errors",
        action="store_true",
        help="Write draft even when validation errors exist (still records errors)",
    )
    return parser


def cmd_validate_draft(path: Path) -> int:
    document = load_draft_document(resolve_draft_path(path))
    snapshot = load_registry_snapshot()
    errors, warnings = validate_draft_entry(document.entry, snapshot)
    document.validation_errors = errors
    document.validation_warnings = warnings
    print(json.dumps(document.to_json_dict(), indent=2))
    return 1 if errors else 0


def cmd_write_draft(
    entry: PatternCoverageEntry,
    *,
    output: Path | None,
    allow_validation_errors: bool,
    extra_warnings: list[str] | None = None,
) -> int:
    snapshot = load_registry_snapshot()
    errors, warnings = validate_draft_entry(entry, snapshot)
    if extra_warnings:
        warnings.extend(extra_warnings)
    if errors and not allow_validation_errors:
        print("Validation failed:", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    document = CoverageDraftDocument(
        entry=entry,
        draft_only=True,
        generated_by=GENERATED_BY,
        requires_human_review=True,
        promoted_to_manifest=False,
        validation_errors=errors,
        validation_warnings=warnings,
    )
    target = output or draft_output_path(entry.question)
    written = write_draft_document(document, target)
    print(f"Wrote draft: {written}")
    if warnings:
        print("Warnings:")
        for item in warnings:
            print(f"  - {item}")
    if errors:
        print("Errors recorded in draft (not promoted):")
        for item in errors:
            print(f"  - {item}")
        return 1 if not allow_validation_errors else 0
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.validate_draft:
        return cmd_validate_draft(args.validate_draft)

    snapshot = load_registry_snapshot()

    if args.entry_json:
        entry = load_entry_json(Path(args.entry_json))
        return cmd_write_draft(entry, output=args.output, allow_validation_errors=args.allow_validation_errors)

    if not args.question and not args.question_ref:
        parser.error("Provide --question, --question-ref, --entry-json, or --validate-draft")

    question, question_ref, pattern_type = resolve_question_input(
        question=args.question,
        question_ref=args.question_ref,
        taxonomy_path=args.taxonomy,
    )

    extra_warnings: list[str] = []
    if args.use_llm:
        assert_instruct_only(model_family=args.llm_model_family, provider=args.llm_provider)
        if not args.llm_raw_file:
            print(
                "Error: --use-llm requires --llm-raw-file for offline authoring "
                "(no live LLM call is made by default).",
                file=sys.stderr,
            )
            return 2
        raw = Path(args.llm_raw_file).read_text(encoding="utf-8")

        def _provider() -> str:
            return raw

        entry, disagreements = draft_entry_with_llm(
            question,
            question_ref,
            pattern_type,
            snapshot,
            llm_raw_output_provider=_provider,
            model_family=args.llm_model_family,
            provider=args.llm_provider,
        )
        extra_warnings.extend(disagreements)
    else:
        entry = draft_entry_deterministic(question, question_ref, pattern_type, snapshot)

    return cmd_write_draft(
        entry,
        output=args.output,
        allow_validation_errors=args.allow_validation_errors,
        extra_warnings=extra_warnings,
    )


if __name__ == "__main__":
    raise SystemExit(main())
