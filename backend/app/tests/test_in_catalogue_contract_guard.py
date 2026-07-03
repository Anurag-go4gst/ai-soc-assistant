"""Plan 0.3 — in-catalogue contract guard (105 + Cisco 50)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.evals.in_catalogue_contract import (
    BASELINE_PATH,
    capture_all,
    check_against_baseline,
    compare_row,
    iter_in_catalogue_entries,
    load_baseline,
)

MAX_SPOT_CHECK = 12


def test_baseline_fixture_present_and_covers_catalogue() -> None:
    assert BASELINE_PATH.is_file(), f"missing baseline: run scripts/capture_in_catalogue_contract_fixtures.py --freeze"
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    entries = iter_in_catalogue_entries()
    assert payload["question_count"] == len(entries)
    assert len(payload["rows"]) == len(entries)


@pytest.mark.parametrize("entry", iter_in_catalogue_entries()[:MAX_SPOT_CHECK])
def test_spot_check_matches_baseline(entry: dict) -> None:
    key = f"{entry['catalogue']}:{entry['question_ref']}"
    expected = load_baseline()[key]
    actual = capture_all([entry])[key]
    diffs = compare_row(key, expected, actual)
    assert not diffs, "; ".join(diffs)


def test_full_guard_passes_against_baseline() -> None:
    rows = capture_all()
    diffs = check_against_baseline(rows)
    assert not diffs, "\n".join(diffs[:10])


def test_corrupt_fixture_fact_fails_guard(tmp_path: Path) -> None:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    first_key = sorted(baseline["rows"])[0]
    corrupted = json.loads(json.dumps(baseline))
    corrupted["rows"][first_key]["route"] = "__corrupted__"
    corrupt_path = tmp_path / "corrupt.json"
    corrupt_path.write_text(json.dumps(corrupted), encoding="utf-8")

    rows = capture_all()
    diffs = check_against_baseline(rows, path=corrupt_path)
    assert any(first_key in diff and "route" in diff for diff in diffs)
