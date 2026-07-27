"""Stage 3L-S3 Step 7: cov.q046 observation window closure tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.api.routes_scenarios import run_demo_scenario_fixture
from app.observation.cov_q046_observation import (
    FIXTURE_PATH,
    load_observation_fixture,
    run_observation_window,
)
from app.routing.route_authority_allowlist import COV_Q046_PILOT_COVERAGE_ID
from app.routing.route_authority_gate import FALLBACK_GLOBAL_KILL_SWITCH_DISABLED

_REPO = Path(__file__).resolve().parents[3]


def test_fixture_meets_minimum_input_variety() -> None:
    fixture = load_observation_fixture()
    cases = fixture["cases"]
    by_type: dict[str, int] = {}
    for case in cases:
        by_type[case["input_type"]] = by_type.get(case["input_type"], 0) + 1
    assert by_type.get("in_pattern", 0) >= 12
    assert by_type.get("near_miss", 0) >= 5
    assert by_type.get("missing_slot", 0) >= 3


def test_cov_q046_observation_window_closes_with_zero_unexpected(monkeypatch: pytest.MonkeyPatch) -> None:
    result = run_observation_window(monkeypatch, include_baselines=True)
    assert result.unexpected_disagreement_count == 0, result.blockers
    assert result.status == "closed"
    assert result.authority_eligible is True
    assert result.closure_reason == "zero_unexpected_disagreements"
    assert len(result.rows) == len(load_observation_fixture()["cases"]) * 2


def test_prod_defaults_kill_switch_on_all_varied_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    result = run_observation_window(monkeypatch, include_baselines=False)
    prod_rows = [row for row in result.rows if row.run_mode == "prod_defaults"]
    assert len(prod_rows) >= 20
    for row in prod_rows:
        assert row.operation_authoritative_applied is False
        assert row.authority_fallback_reason == FALLBACK_GLOBAL_KILL_SWITCH_DISABLED


def test_in_pattern_lab_authority_applies_with_slots(monkeypatch: pytest.MonkeyPatch) -> None:
    result = run_observation_window(monkeypatch, include_baselines=False)
    lab_in = [
        row
        for row in result.rows
        if row.run_mode == "lab_pilot" and row.input_type == "in_pattern"
    ]
    assert len(lab_in) >= 12
    for row in lab_in:
        assert row.operation_authoritative_applied is True, row.case_id
        assert row.coverage_id == COV_Q046_PILOT_COVERAGE_ID
        assert row.selected_skill in {"attack_discovery", "spl_generation"}
        assert row.planning_primary_skill == "aggregate_and_rank"
        assert row.disagreement_class in {"none", "expected"}


def test_near_miss_never_claims_cov_q046_in_lab(monkeypatch: pytest.MonkeyPatch) -> None:
    result = run_observation_window(monkeypatch, include_baselines=False)
    lab_near = [
        row
        for row in result.rows
        if row.run_mode == "lab_pilot" and row.input_type == "near_miss"
    ]
    for row in lab_near:
        assert row.coverage_id != COV_Q046_PILOT_COVERAGE_ID, row.case_id
        assert row.operation_authoritative_applied is False


def test_missing_slot_lab_never_applies_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    result = run_observation_window(monkeypatch, include_baselines=False)
    lab_miss = [
        row
        for row in result.rows
        if row.run_mode == "lab_pilot" and row.input_type == "missing_slot"
    ]
    for row in lab_miss:
        assert row.operation_authoritative_applied is False


def test_experience_center_route_plan_shadow_still_null() -> None:
    response = run_demo_scenario_fixture("failed_login_spike_app01")
    assert response.route_plan_shadow is None
    assert response.demo_mode is True


def test_baseline_scenarios_still_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    result = run_observation_window(monkeypatch, include_baselines=True)
    names = {item["scenario"] for item in result.baseline_scenarios}
    assert "default_production_safe_fallback" in names
    assert "lab_pilot_happy_path" in names
    assert "lab_pilot_missing_threshold_fallback" in names


def test_write_observation_artifacts_when_env_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Optional local artifact generation (skipped in CI unless UPDATE_OBSERVATION_ARTIFACTS=1)."""
    import os

    if os.environ.get("UPDATE_OBSERVATION_ARTIFACTS") != "1":
        pytest.skip("set UPDATE_OBSERVATION_ARTIFACTS=1 to refresh docs artifacts")

    result = run_observation_window(monkeypatch, include_baselines=True)
    jsonl_path = _REPO / "docs" / "stage3l_s3_cov_q046_observation_runs.jsonl"
    with jsonl_path.open("a", encoding="utf-8") as handle:
        for row in result.rows:
            handle.write(json.dumps(row.to_jsonl_record()) + "\n")

    summary_path = tmp_path / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "status": result.status,
                "unexpected": result.unexpected_disagreement_count,
            }
        ),
        encoding="utf-8",
    )
