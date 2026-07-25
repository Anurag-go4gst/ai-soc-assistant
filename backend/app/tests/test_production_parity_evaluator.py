"""Guards for the production dual-runtime parity evaluator.

The evaluator is the loop's scorer, so its failure modes matter more than its happy path:
a scorer that silently accepts a partial corpus, a wrong runtime, or an incomplete approval
record would report green while measuring nothing.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from app.evals.production_runtime_parity import (
    COMPARISON_FIELDS,
    EXCLUDED_FIELDS,
    EXPECTED_BASE_105,
    EXPECTED_CORPUS_COUNT,
    RUNTIME_A,
    RUNTIME_B,
    RuntimeFallbackError,
    _forbid_shadow_graph,
    approval_is_complete,
    classify_row,
    first_divergence,
    validate_report,
)

REPO_ROOT = Path(__file__).resolve().parents[3]

_COMPLETE_APPROVAL = {
    "field": "example_field",
    "runtime_a_value": "a",
    "runtime_b_value": "b",
    "reason": "runtimes cannot agree because …",
    "contract_owner": "app/chat/example.py",
    "approval_ref": "plan item 31 §example",
}


def _report(**overrides: Any) -> dict[str, Any]:
    metadata = {
        "runtime_a": RUNTIME_A,
        "runtime_b": RUNTIME_B,
        "corpus_count": EXPECTED_CORPUS_COUNT,
        "base_105_loaded": EXPECTED_BASE_105,
        "commit_sha": "deadbeef",
        "command": "pytest",
    }
    metadata.update(overrides.pop("metadata", {}))
    summary = {"exact_match": 120, "approved_difference": 0, "critical_mismatch": 0}
    summary.update(overrides.pop("summary", {}))
    return {"metadata": metadata, "summary": summary, "rows": []}


# --- classification -------------------------------------------------------------------


def test_identical_projections_are_exact_match() -> None:
    projection = {field: "same" for field in COMPARISON_FIELDS}
    classification, diffs = classify_row(dict(projection), dict(projection))
    assert classification == "exact_match"
    assert diffs == []


def test_unapproved_difference_is_critical_mismatch() -> None:
    a = {field: "same" for field in COMPARISON_FIELDS}
    b = dict(a, hil_required=True)
    classification, diffs = classify_row(a, b)
    assert classification == "critical_mismatch"
    assert [d["field"] for d in diffs] == ["hil_required"]
    assert diffs[0]["approved"] is False


def test_approved_difference_requires_all_six_parts() -> None:
    assert approval_is_complete(_COMPLETE_APPROVAL) is True
    for missing in _COMPLETE_APPROVAL:
        partial = {k: v for k, v in _COMPLETE_APPROVAL.items() if k != missing}
        assert approval_is_complete(partial) is False, f"{missing} must be required"
    for blank in _COMPLETE_APPROVAL:
        blanked = dict(_COMPLETE_APPROVAL, **{blank: "   "})
        assert approval_is_complete(blanked) is False, f"blank {blank} must not count"
    assert approval_is_complete(None) is False


def test_incomplete_approval_record_downgrades_to_critical_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """A half-filled approval must never soften a mismatch."""
    import app.evals.production_runtime_parity as parity

    monkeypatch.setitem(parity.APPROVED_DIFFERENCES, "hil_required", {"field": "hil_required"})
    a = {field: "same" for field in COMPARISON_FIELDS}
    classification, _ = classify_row(a, dict(a, hil_required=True))
    assert classification == "critical_mismatch"


def test_approval_registry_is_empty_by_default() -> None:
    """Nothing is pre-approved; every difference starts critical."""
    import app.evals.production_runtime_parity as parity

    assert parity.APPROVED_DIFFERENCES == {}


def test_first_divergence_follows_declared_field_order() -> None:
    a = {field: "same" for field in COMPARISON_FIELDS}
    b = dict(a, hil_required=True, match_path="other")
    assert first_divergence(a, b) == "match_path"
    assert first_divergence(a, dict(a)) is None


# --- projection integrity -------------------------------------------------------------


def test_runtime_metadata_is_excluded_and_behaviour_is_not() -> None:
    for excluded, justification in EXCLUDED_FIELDS.items():
        assert excluded not in COMPARISON_FIELDS, f"{excluded} is both compared and excluded"
        assert justification.strip(), f"{excluded} needs a documented justification"
    for governance_field in (
        "hil_required",
        "human_review_required",
        "unsafe_blocked",
        "execution_status",
        "executed_spl_present",
        "resource_plan_committed",
        "draft_spl_present",
    ):
        assert governance_field in COMPARISON_FIELDS
        assert governance_field not in EXCLUDED_FIELDS


# --- corpus and runtime integrity -----------------------------------------------------


def test_validate_report_accepts_a_complete_clean_run() -> None:
    assert validate_report(_report()) == []


@pytest.mark.parametrize(
    "overrides,expected_fragment",
    [
        ({"metadata": {"corpus_count": 8}}, "corpus_count"),
        ({"metadata": {"base_105_loaded": 0}}, "base_105_loaded"),
        ({"metadata": {"runtime_b": "planner_led_shadow_graph"}}, "runtime_b"),
        ({"metadata": {"runtime_a": "something_else"}}, "runtime_a"),
        ({"summary": {"critical_mismatch": 7}}, "critical_mismatch"),
    ],
)
def test_validate_report_rejects_partial_or_wrong_runs(overrides: dict, expected_fragment: str) -> None:
    failures = validate_report(_report(**overrides))
    assert any(expected_fragment in failure for failure in failures), failures


# --- negative controls ----------------------------------------------------------------


def test_shadow_graph_tripwire_fires_and_restores() -> None:
    """Runtime B must never silently delegate to the legacy shadow graph."""
    import app.graph.planner_led_shadow_graph as shadow

    original = shadow.run_planner_led_shadow_graph
    with pytest.raises(RuntimeFallbackError):
        with _forbid_shadow_graph():
            shadow.run_planner_led_shadow_graph(object())
    assert shadow.run_planner_led_shadow_graph is original


def test_runner_refuses_to_write_into_docs_evals() -> None:
    """Scratch-only until plan item 35."""
    result = subprocess.run(
        [sys.executable, "scripts/run_production_parity_eval.py", "--out-dir", "docs/evals"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": "backend:.", "PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 2, result.stderr
    assert "refusing to write" in result.stderr
