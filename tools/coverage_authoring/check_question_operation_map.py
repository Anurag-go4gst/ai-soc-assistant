#!/usr/bin/env python3
"""Audit S6.2 operation map report vs committed S6.1 runtime map (drift must fail)."""

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

from app.routing.route_plan_models import RuntimeSkill  # noqa: E402
from registries import MANIFEST_PATH, REPO_ROOT  # noqa: E402

RUNTIME_MAP_PATH = REPO_ROOT / "backend" / "app" / "coverage" / "question_runtime_map_v1.json"
REPORT_PATH = REPO_ROOT / "docs" / "stage3l_s6_105_question_operation_map.json"

PROVISIONAL_STATUSES = frozenset(
    {
        "likely_routable",
        "likely_needs_lookup",
        "likely_needs_detection",
        "likely_needs_context",
        "likely_multi_signal",
        "likely_unsupported",
        "likely_needs_review",
    }
)
DEPENDENCY_TYPES = frozenset(
    {"template", "lookup", "detection", "context", "multi_signal", "unsupported", "unknown"}
)
Q4_READINESS_LABELS = frozenset(
    {
        "coe_synthetic_fixture",
        "source_ready",
        "ioc_dependent",
        "detection_dependent",
        "dependency_missing",
        "blocked_missing_context",
    }
)
RUNTIME_SKILLS = frozenset(skill.value for skill in RuntimeSkill)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest_coverage_ids() -> frozenset[str]:
    payload = _load_json(MANIFEST_PATH)
    return frozenset(str(item["coverage_id"]) for item in payload.get("entries", []))


def audit_operation_map(
    *,
    runtime_path: Path = RUNTIME_MAP_PATH,
    report_path: Path = REPORT_PATH,
) -> dict:
    errors: list[str] = []
    runtime = _load_json(runtime_path)
    report = _load_json(report_path)
    runtime_by_ref = {str(row["question_ref"]): row for row in runtime.get("entries", [])}
    report_entries = report.get("entries", [])
    manifest_ids = _manifest_coverage_ids()

    if runtime.get("question_count") != 105:
        errors.append(f"runtime map question_count={runtime.get('question_count')} expected 105")
    if len(report_entries) != 105:
        errors.append(f"report entries={len(report_entries)} expected 105")
    if report.get("question_count") != 105:
        errors.append(f"report question_count={report.get('question_count')} expected 105")

    refs = [str(item["question_ref"]) for item in report_entries]
    if len(refs) != len(frozenset(refs)):
        errors.append("duplicate question_ref in report")

    for entry in report_entries:
        ref = str(entry["question_ref"])
        runtime_row = runtime_by_ref.get(ref)
        if runtime_row is None:
            errors.append(f"missing runtime row for {ref}")
            continue

        likely_op = entry.get("likely_runtime_operation")
        if likely_op is not None and likely_op not in RUNTIME_SKILLS:
            errors.append(f"{ref}: invalid likely_runtime_operation={likely_op!r}")

        dep_type = entry.get("dependency_type")
        if dep_type not in DEPENDENCY_TYPES:
            errors.append(f"{ref}: invalid dependency_type={dep_type!r}")

        prov = entry.get("provisional_status")
        if prov not in PROVISIONAL_STATUSES:
            errors.append(f"{ref}: invalid provisional_status={prov!r}")

        promoted = bool(entry.get("promoted_to_manifest"))
        if promoted != (runtime_row.get("promotion_status") == "in_manifest"):
            errors.append(f"{ref}: promoted_to_manifest drift vs runtime promotion_status")

        if likely_op != runtime_row.get("proposed_primary_skill"):
            errors.append(
                f"{ref}: likely_runtime_operation {likely_op!r} != "
                f"runtime proposed_primary_skill {runtime_row.get('proposed_primary_skill')!r}",
            )

        candidate_id = entry.get("candidate_coverage_id")
        if candidate_id != runtime_row.get("manifest_coverage_id"):
            errors.append(f"{ref}: candidate_coverage_id drift vs runtime manifest_coverage_id")

        if not promoted:
            for label in Q4_READINESS_LABELS:
                if label in entry and entry.get("manifest_readiness") is None and label == entry.get(label):
                    errors.append(f"{ref}: Q4 readiness label {label!r} on non-promoted row")
            if entry.get("manifest_readiness") is not None:
                errors.append(f"{ref}: manifest_readiness on non-promoted row")
        else:
            cov_id = entry.get("candidate_coverage_id")
            if cov_id not in manifest_ids:
                errors.append(f"{ref}: promoted candidate_coverage_id {cov_id!r} not in manifest")

    runtime_refs = frozenset(runtime_by_ref)
    report_refs = frozenset(refs)
    if runtime_refs != report_refs:
        errors.append(f"question_ref set mismatch runtime={len(runtime_refs)} report={len(report_refs)}")

    return {
        "ok": not errors,
        "error_count": len(errors),
        "errors": errors,
        "runtime_map": str(runtime_path),
        "report": str(report_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit S6.2 report vs S6.1 runtime map.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = audit_operation_map()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["ok"]:
            print("operation_map_audit ok entries=105 drift=0")
        else:
            print(f"operation_map_audit FAILED errors={result['error_count']}", file=sys.stderr)
            for item in result["errors"][:20]:
                print(f"  - {item}", file=sys.stderr)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
