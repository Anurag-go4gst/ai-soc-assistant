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
from promotion_candidate import build_promotion_candidate, write_promotion_candidate  # noqa: E402
from promotion_gates import evaluate_promotion_gates  # noqa: E402
from question_runtime_map_builder import (  # noqa: E402
    write_all_question_maps,
    write_operation_map_report,
    write_question_runtime_map,
)
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
    parser.add_argument(
        "--check-promotion",
        action="store_true",
        help="Evaluate S5 promotion gates for --entry-json or draft from question; prints JSON and exits",
    )
    parser.add_argument(
        "--emit-runtime-map",
        action="store_true",
        help="Regenerate backend/app/coverage/question_runtime_map_v1.json (S6) and exit",
    )
    parser.add_argument(
        "--emit-operation-map",
        action="store_true",
        help="Regenerate docs/stage3l_s6_105_question_operation_map.json (S6.2 report) and exit",
    )
    parser.add_argument(
        "--emit-maps",
        action="store_true",
        help="Regenerate S6.1 runtime map and S6.2 operation report from one builder pass",
    )
    parser.add_argument(
        "--append-supplemental",
        type=Path,
        help="Merge JSON {entries:[{question_ref, question, pattern_type, ...}]} into supplemental_taxonomy_rows.json before --emit-maps",
    )
    parser.add_argument(
        "--promotion-candidate",
        action="store_true",
        help="Emit S5.2 human-review promotion artifact (single-entry patch hint only; no manifest write)",
    )
    parser.add_argument(
        "--promotion-candidate-output",
        type=Path,
        help="Optional path under tools/coverage_authoring/promotion_candidates/",
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


def cmd_check_promotion(entry: PatternCoverageEntry) -> int:
    result = evaluate_promotion_gates(entry)
    print(json.dumps(result.model_dump(), indent=2))
    return 0 if result.manifest_copy_ready else 1


def cmd_promotion_candidate(
    entry: PatternCoverageEntry,
    *,
    output: Path | None,
    print_json: bool,
) -> int:
    if print_json and output is None:
        payload = build_promotion_candidate(entry)
        print(json.dumps(payload, indent=2))
        return 0 if payload["promotion_gate_result"]["manifest_copy_ready"] else 1
    written = write_promotion_candidate(entry, output)
    print(f"Wrote promotion candidate: {written}")
    payload = json.loads(written.read_text(encoding="utf-8"))
    return 0 if payload["promotion_gate_result"]["manifest_copy_ready"] else 1


def cmd_emit_runtime_map() -> int:
    written = write_question_runtime_map()
    print(f"Wrote question runtime map: {written}")
    return 0


def cmd_emit_operation_map() -> int:
    written = write_operation_map_report()
    print(f"Wrote operation map report: {written}")
    return 0


def cmd_emit_maps() -> int:
    runtime_path, report_path = write_all_question_maps()
    print(f"Wrote question runtime map: {runtime_path}")
    print(f"Wrote operation map report: {report_path}")
    return 0


def cmd_append_supplemental(path: Path) -> int:
    from question_runtime_map_builder import SUPPLEMENTAL_TAXONOMY_PATH

    incoming = json.loads(path.read_text(encoding="utf-8"))
    new_entries = incoming.get("entries", incoming if isinstance(incoming, list) else [])
    if not isinstance(new_entries, list):
        raise SystemExit("Supplemental file must contain entries[] list")

    existing_payload: dict = {"entries": []}
    if SUPPLEMENTAL_TAXONOMY_PATH.is_file():
        existing_payload = json.loads(SUPPLEMENTAL_TAXONOMY_PATH.read_text(encoding="utf-8"))
    by_ref = {
        str(item["question_ref"]).lower(): item
        for item in existing_payload.get("entries", [])
        if isinstance(item, dict) and item.get("question_ref")
    }
    for item in new_entries:
        if not isinstance(item, dict) or not item.get("question_ref"):
            continue
        by_ref[str(item["question_ref"]).lower()] = item
    merged = {
        "schema_version": "supplemental_taxonomy_v1",
        "description": existing_payload.get("description") or SUPPLEMENTAL_TAXONOMY_PATH.name,
        "entries": sorted(by_ref.values(), key=lambda row: str(row["question_ref"])),
    }
    SUPPLEMENTAL_TAXONOMY_PATH.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote supplemental taxonomy ({len(merged['entries'])} rows): {SUPPLEMENTAL_TAXONOMY_PATH}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.append_supplemental:
        return cmd_append_supplemental(args.append_supplemental)
    if args.emit_maps:
        return cmd_emit_maps()
    if args.emit_runtime_map:
        return cmd_emit_runtime_map()
    if args.emit_operation_map:
        return cmd_emit_operation_map()

    if args.validate_draft:
        return cmd_validate_draft(args.validate_draft)

    snapshot = load_registry_snapshot()

    if args.entry_json:
        entry = load_entry_json(Path(args.entry_json))
        if args.promotion_candidate:
            return cmd_promotion_candidate(
                entry,
                output=args.promotion_candidate_output,
                print_json=args.promotion_candidate_output is None and args.output is None,
            )
        if args.check_promotion:
            return cmd_check_promotion(entry)
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

    if args.promotion_candidate:
        return cmd_promotion_candidate(
            entry,
            output=args.promotion_candidate_output,
            print_json=args.promotion_candidate_output is None and args.output is None,
        )

    if args.check_promotion:
        return cmd_check_promotion(entry)

    return cmd_write_draft(
        entry,
        output=args.output,
        allow_validation_errors=args.allow_validation_errors,
        extra_warnings=extra_warnings,
    )


if __name__ == "__main__":
    raise SystemExit(main())
