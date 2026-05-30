#!/usr/bin/env python3
"""Audit committed pattern_coverage_v1.json against S5 promotion gates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "backend"))

from app.coverage.manifest_promotion_audit import audit_committed_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit full audit JSON to stdout",
    )
    parser.add_argument(
        "--no-coe-signoff",
        action="store_true",
        help="Treat COE Step 3 sign-off as not recorded (draft authority checks)",
    )
    args = parser.parse_args()

    report = audit_committed_manifest(coe_signoff_recorded=not args.no_coe_signoff)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(
            f"entries={report['entry_count']} "
            f"s5_ok={report['all_manifest_integrity_ok']} "
            f"s7_align_ok={report.get('all_precondition_alignment_ok', False)}"
        )
        for item in report["entries"]:
            status = "OK" if item["manifest_integrity_ok"] else "FAIL"
            align = item.get("precondition_alignment") or {}
            align_tag = align.get("alignment_status", "n/a")
            print(
                f"  [{status}] {item['coverage_id']} ({item['question_ref']}) "
                f"s7={align.get('precondition_route_status')} align={align_tag}"
            )
            if not item["manifest_integrity_ok"]:
                failed = [c for c in item["checks"] if not c["passed"]]
                for check in failed[:5]:
                    print(f"       - {check['gate_id']}: {check['detail']}")
            if align_tag == "drift":
                for note in (align.get("alignment_notes") or [])[:3]:
                    print(f"       ! {note}")

    s5_ok = report["all_manifest_integrity_ok"]
    s7_ok = report.get("all_precondition_alignment_ok", True)
    return 0 if s5_ok and s7_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
