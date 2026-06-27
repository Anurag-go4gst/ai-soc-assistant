#!/usr/bin/env python3
"""Apply or dry-run operator-reviewed promotion_status writes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.coverage.promotion_status_review import (  # noqa: E402
    PromotionStatusWriteRequest,
    ReviewedPromotionEvidence,
    apply_promotion_status_write,
    compute_row_revision,
)
from app.coverage.question_runtime_map import load_question_runtime_map  # noqa: E402


def _load_entry(question_ref: str) -> dict:
    for entry in load_question_runtime_map(reload=True).get("entries", []):
        if isinstance(entry, dict) and entry.get("question_ref") == question_ref:
            return entry
    raise SystemExit(f"unknown question_ref: {question_ref}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["promote", "demote"])
    parser.add_argument("question_ref", help="Runtime-map question_ref, e.g. q0.q046")
    parser.add_argument("--operator-id", required=True)
    parser.add_argument("--review-ticket", required=True)
    parser.add_argument("--row-revision", help="Required unless --show-revision is passed")
    parser.add_argument("--show-revision", action="store_true", help="Print current row revision and exit")
    parser.add_argument("--pack-id", help="Reviewed answer-pack id (promote)")
    parser.add_argument("--golden-passed", action="store_true", help="Operator attests golden gate passed")
    parser.add_argument("--golden-run-ref", help="Golden run id / CI ref (promote)")
    parser.add_argument("--reviewed-reason", help="Reviewed demotion reason (demote)")
    parser.add_argument("--apply", action="store_true", help="Persist write (default is dry-run)")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable result")
    args = parser.parse_args(argv)

    entry = _load_entry(args.question_ref)
    revision = compute_row_revision(entry)
    if args.show_revision:
        print(revision)
        return 0
    if not args.row_revision:
        parser.error("--row-revision is required (or pass --show-revision)")

    evidence = ReviewedPromotionEvidence(
        operator_id=args.operator_id,
        review_ticket=args.review_ticket,
        pack_id=args.pack_id,
        golden_passed=args.golden_passed,
        golden_run_ref=args.golden_run_ref,
        reviewed_reason=args.reviewed_reason,
    )
    request = PromotionStatusWriteRequest(
        action=args.action,
        question_ref=args.question_ref,
        row_revision=args.row_revision,
        reviewed_evidence=evidence,
        dry_run=not args.apply,
    )
    result = apply_promotion_status_write(request)
    payload = result.model_dump()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"action={result.action} question_ref={result.question_ref}")
        print(f"allowed={result.allowed} applied={result.applied} dry_run={result.dry_run}")
        print(f"before={result.before_status!r} after={result.after_status!r}")
        if result.blockers:
            print("blockers:")
            for blocker in result.blockers:
                print(f"  - {blocker}")
        if result.audit_record_id:
            print(f"audit_record_id={result.audit_record_id}")
    return 0 if result.allowed else 1


if __name__ == "__main__":
    raise SystemExit(main())
