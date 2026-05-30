"""Stage 3L-S6.2 operation map report tests."""

from __future__ import annotations

import json
from pathlib import Path

from check_question_operation_map import audit_operation_map
from question_runtime_map_builder import (
    OPERATION_REPORT_PATH,
    OUTPUT_PATH,
    build_operation_map_report,
    build_question_runtime_map,
    write_all_question_maps,
)
from registries import MANIFEST_PATH, REPO_ROOT

Q4_READINESS = frozenset(
    {
        "coe_synthetic_fixture",
        "source_ready",
        "ioc_dependent",
        "detection_dependent",
        "dependency_missing",
        "blocked_missing_context",
    }
)


def test_build_report_has_105_entries() -> None:
    runtime = build_question_runtime_map()
    report = build_operation_map_report(runtime_payload=runtime)
    assert report["question_count"] == 105
    assert len(report["entries"]) == 105


def test_emit_maps_writes_both_artifacts() -> None:
    before_runtime = OUTPUT_PATH.read_text(encoding="utf-8")
    report_existed = OPERATION_REPORT_PATH.exists()
    before_report = OPERATION_REPORT_PATH.read_text(encoding="utf-8") if report_existed else None
    write_all_question_maps()
    try:
        audit = audit_operation_map()
        assert audit["ok"], audit["errors"]
        payload = json.loads(OPERATION_REPORT_PATH.read_text(encoding="utf-8"))
        assert payload["report_version"] == "stage3l_s6_2_v1"
        for entry in payload["entries"]:
            assert entry["provisional_status"].startswith("likely_")
            if not entry["promoted_to_manifest"]:
                assert "manifest_readiness" not in entry or entry.get("manifest_readiness") is None
    finally:
        OUTPUT_PATH.write_text(before_runtime, encoding="utf-8")
        if before_report is not None:
            OPERATION_REPORT_PATH.write_text(before_report, encoding="utf-8")
        elif OPERATION_REPORT_PATH.exists() and not report_existed:
            OPERATION_REPORT_PATH.unlink(missing_ok=True)


def test_promoted_rows_reference_manifest() -> None:
    manifest_ids = {
        str(row["coverage_id"]) for row in json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["entries"]
    }
    report = build_operation_map_report()
    for entry in report["entries"]:
        if entry["promoted_to_manifest"]:
            assert entry["candidate_coverage_id"] in manifest_ids
            if "manifest_readiness" in entry:
                assert entry["manifest_readiness"] in Q4_READINESS


def test_non_promoted_rows_have_no_q4_readiness() -> None:
    report = build_operation_map_report()
    for entry in report["entries"]:
        if not entry["promoted_to_manifest"]:
            assert entry.get("manifest_readiness") is None


def test_audit_fails_on_drift(tmp_path: Path) -> None:
    runtime = build_question_runtime_map()
    report = build_operation_map_report(runtime_payload=runtime)
    report["entries"][0]["likely_runtime_operation"] = "entity_timeline"
    bad_report = tmp_path / "bad_report.json"
    bad_report.write_text(json.dumps(report), encoding="utf-8")
    runtime_path = tmp_path / "runtime.json"
    runtime_path.write_text(json.dumps(runtime), encoding="utf-8")
    result = audit_operation_map(runtime_path=runtime_path, report_path=bad_report)
    assert not result["ok"]
    assert any("likely_runtime_operation" in err for err in result["errors"])
