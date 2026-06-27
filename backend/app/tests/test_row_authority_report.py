from __future__ import annotations

import json
from pathlib import Path

from scripts.build_row_authority_report import (
    NEEDS_CLARIFICATION,
    UNSUPPORTED,
    WEAK_NEEDS_ENRICHMENT,
    build_report,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RUNTIME_MAP = _REPO_ROOT / "backend" / "app" / "coverage" / "question_runtime_map_v1.json"
_MANIFEST = _REPO_ROOT / "backend" / "app" / "coverage" / "pattern_coverage_v1.json"
_CATALOG = _REPO_ROOT / "backend" / "app" / "use_cases" / "catalog.json"
_REPORT_JSON = _REPO_ROOT / "docs" / "evals" / "row_authority_report.json"
_REPORT_MD = _REPO_ROOT / "docs" / "evals" / "row_authority_report.md"


def _report() -> dict:
    return build_report(
        json.loads(_RUNTIME_MAP.read_text(encoding="utf-8")),
        json.loads(_MANIFEST.read_text(encoding="utf-8")),
        json.loads(_CATALOG.read_text(encoding="utf-8")),
    )


def _row(report: dict, question_ref: str) -> dict:
    return next(row for row in report["rows"] if row["question_ref"] == question_ref)


def test_row_authority_report_has_all_105_rows_and_no_projection_mismatches() -> None:
    report = _report()

    assert report["question_105_count"] == 105
    assert report["catalog_count"] > 0
    assert report["projection_mismatches"] == []
    assert sum(report["status_counts"].values()) == report["row_count"]


def test_row_authority_report_maps_q046_to_exact_known_weak_needs_enrichment() -> None:
    row = _row(_report(), "q0.q046")

    assert row["row_authority_status"] == WEAK_NEEDS_ENRICHMENT
    assert row["s3_authority_ready"] is False
    assert row["may_skip_llm"] is False
    assert "coe_step3_implementation_not_approved" in row["blockers"]
    assert "operation_authoritative_enabled_defaults_false" in row["blockers"]
    assert "row_authority_not_ready" in row["projected_demotion_reasons"]


def test_row_authority_report_marks_q028_unsupported() -> None:
    row = _row(_report(), "q0.q028")

    assert row["row_authority_status"] == UNSUPPORTED
    assert row["s3_authority_ready"] is False
    assert row["route_blocked"] is True
    assert "route_blocked" in row["blockers"]


def test_row_authority_report_q045_uses_single_clarification_status() -> None:
    row = _row(_report(), "q0.q045")

    assert row["row_authority_status"] == NEEDS_CLARIFICATION
    assert row["s3_authority_ready"] is False
    assert row["may_skip_llm"] is False
    assert row["blockers"] == ["requires_clarification_or_case_context"]


def _rows_without_demotion_projection(report: dict) -> list[dict]:
    return [
        {key: value for key, value in row.items() if key != "projected_demotion_reasons"}
        for row in report["rows"]
    ]


def test_row_authority_report_artifacts_are_current() -> None:
    report = _report()
    on_disk = json.loads(_REPORT_JSON.read_text(encoding="utf-8"))

    assert on_disk["question_105_count"] == report["question_105_count"]
    assert on_disk["projection_mismatches"] == report["projection_mismatches"]
    assert _rows_without_demotion_projection(on_disk) == _rows_without_demotion_projection(report)
    assert "q0.q046" in _REPORT_MD.read_text(encoding="utf-8")
