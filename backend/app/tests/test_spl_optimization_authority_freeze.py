"""OPTIONAL_PHASE_S S0 — authority freeze identity / one-way eligibility."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
FREEZE_PATH = REPO / "docs/evals/spl_optimization/authority_baseline_v1.json"
FREEZE_SCRIPT = REPO / "scripts/freeze_spl_optimization_authority.py"


@pytest.fixture(scope="module")
def freeze() -> dict:
    assert FREEZE_PATH.is_file(), f"missing freeze artifact {FREEZE_PATH}"
    return json.loads(FREEZE_PATH.read_text(encoding="utf-8"))


def test_freeze_regenerates_byte_identical_or_authority_identical() -> None:
    proc = subprocess.run(
        [sys.executable, str(FREEZE_SCRIPT), "--check"],
        cwd=REPO,
        capture_output=True,
        text=True,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONPATH": f"{REPO / 'backend'}:{REPO}"},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "byte-identical" in proc.stdout or "authority-identical" in proc.stdout


def test_freeze_covers_both_banks(freeze: dict) -> None:
    banks = {row["bank"] for row in freeze["rows"]}
    assert banks == {"spl_golden", "convergence"}
    assert freeze["row_count"] == len(freeze["rows"])
    assert freeze["row_count"] >= 40


def test_approved_identical_contract_fields_present(freeze: dict) -> None:
    for row in freeze["rows"]:
        assert "approved" in row
        assert "normalized_spl" in row
        assert "execution_eligible" in row
        assert isinstance(row["approved"], bool)
        assert isinstance(row["execution_eligible"], bool)


def test_execution_eligible_never_rises_above_freeze(freeze: dict) -> None:
    """Ceiling: observed eligible must not become true when freeze says false.

    This test pins the freeze itself as the ceiling document — later phase tests
    compare live observations against these values and must fail on false→true.
    """
    for row in freeze["rows"]:
        # At S0 baseline every row is non-eligible; keep the hard pin so a
        # future accidental true in the freeze fails closed.
        if row["execution_eligible"] is True:
            pytest.fail(
                f"freeze row {row['row_id']} has execution_eligible=true — "
                "S0 ceiling must not invent eligibility"
            )


def authority_regression_vs_freeze(observed_rows: list[dict], freeze: dict) -> list[str]:
    """Helper used by later items: return violation messages.

    - approved must equal freeze
    - execution_eligible must not rise (false→true forbidden)
    - normalized_spl identity enforced by caller for PASS/NO_SAFE_OPTIMIZATION
    """
    by_id = {r["row_id"]: r for r in freeze["rows"]}
    violations: list[str] = []
    for obs in observed_rows:
        row_id = obs["row_id"]
        base = by_id[row_id]
        if bool(obs.get("approved")) != bool(base["approved"]):
            violations.append(f"{row_id}: approved changed {base['approved']}→{obs.get('approved')}")
        base_elig = bool(base["execution_eligible"])
        obs_elig = bool(obs.get("execution_eligible"))
        if (not base_elig) and obs_elig:
            violations.append(f"{row_id}: execution_eligible false→true forbidden")
    return violations


def test_authority_helper_rejects_false_to_true(freeze: dict) -> None:
    sample = freeze["rows"][0]
    bad = {
        "row_id": sample["row_id"],
        "approved": sample["approved"],
        "execution_eligible": True,
        "normalized_spl": sample["normalized_spl"],
    }
    violations = authority_regression_vs_freeze([bad], freeze)
    assert any("false→true" in v for v in violations)
