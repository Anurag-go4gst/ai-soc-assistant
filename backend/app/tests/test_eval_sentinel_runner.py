"""T-PRE.2 — sentinel runner determinism and baseline check/freeze cycle."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.evals.sentinel_eval import (
    SENTINEL_SET_PATH,
    capture_row,
    check_against_baseline,
    freeze_baseline,
    load_sentinel_rows,
)

CONTRACT_FIELDS = {
    "match_path",
    "selected_skill",
    "intent_family",
    "answer_mode",
    "severity_label",
    "execution_eligible",
    "enabled_sections",
    "analyst_enabled_sections",
    "draft_spl_present",
    "draft_status",
}


def test_baseline_freezes_smb_lab_draft() -> None:
    """q0.q010 must carry its lab draft in the analyst card (105 honoring)."""
    from app.evals.sentinel_eval import BASELINE_PATH

    rows = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))["rows"]
    smb = rows["q0.q010"]
    assert smb["draft_spl_present"] is True
    assert smb["draft_status"] == "draft_preview_not_governed"
    assert "draft_spl_preview" in smb["analyst_enabled_sections"]
    assert smb["intent_family"] == "spl_generation_only"
    assert smb["requires_clarification"] is False
    assert smb["severity_label"] == "Not assigned from this question alone"


def test_sentinel_set_loads_seventeen_rows() -> None:
    rows = load_sentinel_rows()
    assert len(rows) == 17
    keys = [row["key"] for row in rows]
    assert len(keys) == len(set(keys))
    assert "q0.q010" in keys


def test_capture_row_is_deterministic_across_runs() -> None:
    rows = load_sentinel_rows()
    samples = [rows[0], next(row for row in rows if row["source"] == "powergrid_question_bank")]
    for row in samples:
        first = capture_row(row["question"])
        second = capture_row(row["question"])
        assert first == second, f"unstable capture for {row['key']}"
        assert CONTRACT_FIELDS <= set(first), f"missing contract fields for {row['key']}"


def test_freeze_then_check_passes(tmp_path: Path) -> None:
    captures = {"q0.q010": {"match_path": "exact_105_question", "severity_label": "x"}}
    baseline = tmp_path / "baseline.json"
    assert freeze_baseline(captures, path=baseline) == []
    assert check_against_baseline(captures, path=baseline) == []


def test_freeze_refuses_error_rows(tmp_path: Path) -> None:
    captures = {"q0.q010": {"error": "RuntimeError: boom"}}
    baseline = tmp_path / "baseline.json"
    assert freeze_baseline(captures, path=baseline) == ["q0.q010"]
    assert not baseline.exists()


def test_check_reports_field_and_membership_diffs(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    frozen = {
        "q0.q010": {"match_path": "exact_105_question"},
        "q0.q002": {"match_path": "exact_105_question"},
    }
    assert freeze_baseline(frozen, path=baseline) == []

    drifted = {
        "q0.q010": {"match_path": "out_of_registry"},
        "pg.new.001": {"match_path": "use_case_catalog"},
    }
    diffs = check_against_baseline(drifted, path=baseline)
    assert any("q0.q010.match_path" in diff for diff in diffs)
    assert any("q0.q002" in diff and "missing from run" in diff for diff in diffs)
    assert any("pg.new.001" in diff and "not in baseline" in diff for diff in diffs)


def test_check_fails_on_missing_baseline(tmp_path: Path) -> None:
    diffs = check_against_baseline({}, path=tmp_path / "absent.json")
    assert len(diffs) == 1
    assert "baseline missing" in diffs[0]


def test_repo_baseline_matches_current_pipeline() -> None:
    """The committed fixture must stay green against the committed sentinel set."""
    if not SENTINEL_SET_PATH.exists():
        pytest.skip("sentinel set not built")
    rows = load_sentinel_rows()
    captures = {}
    for row in rows:
        captures[row["key"]] = capture_row(row["question"])
    assert check_against_baseline(captures) == []


def test_repo_baseline_has_no_executable_spl() -> None:
    """Safety invariant: frozen baseline never records execution_eligible=true."""
    from app.evals.sentinel_eval import BASELINE_PATH

    rows = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))["rows"]
    assert len(rows) == 17
    assert all(row.get("execution_eligible") is not True for row in rows.values())
