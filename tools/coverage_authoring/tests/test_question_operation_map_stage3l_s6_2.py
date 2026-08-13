"""Stage 3L-S6.2 operation map report tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import question_runtime_map_builder as builder
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


def test_emit_maps_writes_both_artifacts(tmp_path) -> None:
    """Exercise the writer against disposable targets, never the committed artifacts.

    This test used to call `write_all_question_maps()` bare — writing the real
    `question_runtime_map_v1.json` and restoring it in a `finally`. An interrupted run left the
    regenerated file on disk, and a regeneration silently drops governed MITRE metadata and broadens
    analyst-visible technique claims on 11 questions (Plan 5 A1/A2). Snapshot-and-restore is not
    containment; not writing the file is.
    """
    runtime_target = tmp_path / "question_runtime_map_v1.json"
    report_target = tmp_path / "stage3l_s6_105_question_operation_map.json"
    committed_runtime_before = OUTPUT_PATH.read_bytes()

    write_all_question_maps(runtime_path=runtime_target, report_path=report_target)

    audit = audit_operation_map(runtime_path=runtime_target, report_path=report_target)
    assert audit["ok"], audit["errors"]
    payload = json.loads(report_target.read_text(encoding="utf-8"))
    assert payload["report_version"] == "stage3l_s6_2_v1"
    for entry in payload["entries"]:
        assert entry["provisional_status"].startswith("likely_")
        if not entry["promoted_to_manifest"]:
            assert "manifest_readiness" not in entry or entry.get("manifest_readiness") is None

    assert OUTPUT_PATH.read_bytes() == committed_runtime_before, (
        "the writer touched the committed runtime map despite being given an explicit target"
    )


def test_emit_maps_cannot_touch_committed_artifacts_when_it_fails(tmp_path, monkeypatch) -> None:
    """The containment property: a writer that dies mid-run leaves the committed map intact.

    Simulates the interrupted-run case the old snapshot/restore could not survive.
    """
    committed_runtime_before = OUTPUT_PATH.read_bytes()
    report_existed = OPERATION_REPORT_PATH.exists()
    committed_report_before = OPERATION_REPORT_PATH.read_bytes() if report_existed else None

    def _boom(*_args, **_kwargs):
        raise RuntimeError("simulated interruption partway through authoring")

    monkeypatch.setattr(builder, "write_operation_map_report", _boom)

    with pytest.raises(RuntimeError):
        write_all_question_maps(
            runtime_path=tmp_path / "runtime.json",
            report_path=tmp_path / "report.json",
        )

    assert OUTPUT_PATH.read_bytes() == committed_runtime_before
    assert OPERATION_REPORT_PATH.exists() == report_existed
    if committed_report_before is not None:
        assert OPERATION_REPORT_PATH.read_bytes() == committed_report_before


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
