"""Evaluator pins for the routing truth set (Plan 4 R1.4).

The evaluator's whole value rests on two properties: the route verdict and the
capability verdict must be independent, and `--check` must be no-regression
rather than identity. Both are pinned here.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "eval_routing_truth_set.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("eval_routing_truth_set", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


evaluator = _load_script()


def _result_row(**overrides):
    row = {
        "row_id": "r1",
        "quotas": ["hunt"],
        "ambiguous": False,
        "label_confidence": "high",
        "route_verdict": "route_ok",
        "capability_inconsistent": False,
        "denied_capabilities": [],
        "selected_skill": "attack_discovery",
        "acceptable_skills": ["attack_discovery"],
        "required_capabilities": ["spl"],
        "authority_source": "query_understanding_105",
        "match_path": "exact_105_question",
        "route_confidence": 0.75,
        "observed_intent_family": "spl_generation_only",
        "expected_intent_family": "spl_generation_only",
        "family_match": True,
        "observed_path_type": "spl_review",
        "observed_answer_mode": "live_investigation",
        "expected_answer_shape": "hunt",
        "needs_spl": True,
        "execution_enabled": False,
    }
    row.update(overrides)
    return row


# --------------------------------------------------------------------------- #
# The independence property, on a real routed query.
# --------------------------------------------------------------------------- #


def test_route_ok_and_capability_inconsistent_can_coexist() -> None:
    """A row may pass the route verdict and still fail the capability verdict.

    This is the D1 defect class. If the evaluator ever collapsed the two axes,
    these rows would score as clean passes and the benchmark would be blind to
    exactly the defect it was built to measure.
    """
    row = {
        "row_id": "synthetic.d1",
        "query": "Which hosts contacted suspicious external domains?",
        "acceptable_skills": ["knowledge_recall", "attack_discovery", "spl_generation"],
        "required_capabilities": ["spl"],
        "ambiguous": False,
        "label_confidence": "high",
        "expected_intent_family": "spl_generation_only",
        "expected_answer_shape": "hunt",
        "quotas": ["synthetic"],
    }

    result = evaluator.evaluate_row(row)

    assert result["selected_skill"] == "knowledge_recall"
    assert result["route_verdict"] == "route_ok", "knowledge_recall is in the acceptable set"
    assert result["capability_inconsistent"] is True
    assert result["denied_capabilities"] == ["spl"]


def test_a_capable_skill_clears_the_capability_verdict() -> None:
    row = {
        "row_id": "synthetic.hunt",
        "query": "Which hosts contacted known malicious IPs today?",
        "acceptable_skills": ["attack_discovery", "spl_generation"],
        "required_capabilities": ["spl"],
        "ambiguous": False,
        "label_confidence": "high",
        "expected_intent_family": "spl_generation_only",
        "expected_answer_shape": "hunt",
        "quotas": ["synthetic"],
    }
    result = evaluator.evaluate_row(row)
    assert result["route_verdict"] == "route_ok"
    assert result["capability_inconsistent"] is False


# --------------------------------------------------------------------------- #
# Family and shape are reported, never gated.
# --------------------------------------------------------------------------- #


def test_family_mismatch_does_not_affect_any_gating_number() -> None:
    """R1.3 measured 0 of 11 family disagreements crossing a capability boundary."""
    matched = evaluator.summarize([_result_row(family_match=True)])
    mismatched = evaluator.summarize([_result_row(family_match=False)])

    for key in ("route_ok", "route_wrong", "capability_inconsistent", "hunt_under_routing"):
        assert matched[key] == mismatched[key]
    assert matched["family_match_reported"] == 1
    assert mismatched["family_match_reported"] == 0


def test_ambiguous_rows_report_but_never_gate() -> None:
    summary = evaluator.summarize(
        [
            _result_row(row_id="a", ambiguous=True, route_verdict="route_wrong", capability_inconsistent=True),
            _result_row(row_id="b"),
        ]
    )
    assert summary["total_rows"] == 2
    assert summary["gating_rows"] == 1
    assert summary["ambiguous_rows"] == 1
    assert summary["route_wrong"] == 0
    assert summary["capability_inconsistent"] == 0


# --------------------------------------------------------------------------- #
# `--check` is no-regression, not identity.
# --------------------------------------------------------------------------- #


def test_improvement_against_baseline_passes() -> None:
    baseline = [_result_row(route_verdict="route_wrong", capability_inconsistent=True)]
    current = [_result_row(route_verdict="route_ok", capability_inconsistent=False)]
    assert evaluator.compare(current, baseline) == []


def test_route_regression_is_reported() -> None:
    baseline = [_result_row(route_verdict="route_ok")]
    current = [_result_row(route_verdict="route_wrong", selected_skill="knowledge_recall")]
    failures = evaluator.compare(current, baseline)
    assert len(failures) == 1
    assert "route regressed" in failures[0]


def test_new_capability_inconsistency_is_reported() -> None:
    baseline = [_result_row(capability_inconsistent=False)]
    current = [_result_row(capability_inconsistent=True, denied_capabilities=["spl"])]
    failures = evaluator.compare(current, baseline)
    assert len(failures) == 1
    assert "newly capability_inconsistent" in failures[0]


def test_a_dropped_row_is_a_regression() -> None:
    """Deleting an inconvenient row must not be a way to make the gate pass."""
    baseline = [_result_row(row_id="kept"), _result_row(row_id="dropped")]
    failures = evaluator.compare([_result_row(row_id="kept")], baseline)
    assert any("missing from this run" in f for f in failures)


def test_ambiguous_row_cannot_trigger_a_regression() -> None:
    baseline = [_result_row(route_verdict="route_ok")]
    current = [_result_row(route_verdict="route_wrong", ambiguous=True)]
    assert evaluator.compare(current, baseline) == []


# --------------------------------------------------------------------------- #
# Determinism, and the committed set.
# --------------------------------------------------------------------------- #


def test_evaluation_is_deterministic_on_the_committed_set() -> None:
    truth = json.loads((REPO_ROOT / "docs" / "evals" / "routing_truth_set_v1.json").read_text())
    sample = truth["rows"][:12]
    first = [evaluator.evaluate_row(r) for r in sample]
    second = [evaluator.evaluate_row(r) for r in sample]
    assert first == second


def test_unsafe_rows_stay_contained_on_the_committed_set() -> None:
    """Every clarification-labelled row must report execution disabled.

    This is a safety floor, not a quality metric: it must hold in every arm of
    every experiment this plan runs.
    """
    truth = json.loads((REPO_ROOT / "docs" / "evals" / "routing_truth_set_v1.json").read_text())
    unsafe = [r for r in truth["rows"] if r["expected_answer_shape"] == "clarification"]
    assert unsafe, "the corpus must contain clarification-labelled rows"
    for row in unsafe:
        result = evaluator.evaluate_row(row)
        assert result["execution_enabled"] is False, row["row_id"]


# --------------------------------------------------------------------------- #
# Live arm (Plan 4 D3.0): the production-final route, reported beside the floor.
# --------------------------------------------------------------------------- #


def test_live_arm_flags_a_capability_downgrade() -> None:
    """A downgrade is measured against the contracts, not against the label.

    `spl_generation -> knowledge_recall` loses SPL whatever the row is about, so
    the advisory swapping it in is reportable on its own terms.
    """
    row = {
        "row_id": "synthetic.ot",
        "query": "Flag any Modbus TCP traffic communicating on non-standard ports other than 502.",
        "acceptable_skills": ["attack_discovery", "spl_generation"],
        "required_capabilities": ["spl"],
        "ambiguous": False,
        "label_confidence": "high",
        "expected_intent_family": "spl_generation_only",
        "expected_answer_shape": "process_aware_ot",
        "quotas": ["synthetic"],
    }
    result = evaluator.evaluate_live_row(row, deterministic_skill="spl_generation")
    if result["live_skill"] == "spl_generation":
        pytest.skip("advisory did not diverge in this environment")
    assert result["live_capability_downgrade"] is True
    assert "spl" in result["live_capabilities_lost"]


def test_live_arm_delta_vocabulary_is_exhaustive() -> None:
    for skill, expected in [("attack_discovery", {"same", "improved", "lateral", "degraded"})]:
        row = {
            "row_id": "synthetic.delta",
            "query": "Which hosts contacted known malicious IPs today?",
            "acceptable_skills": [skill],
            "required_capabilities": ["spl"],
            "ambiguous": False,
            "label_confidence": "high",
            "expected_intent_family": "spl_generation_only",
            "expected_answer_shape": "hunt",
            "quotas": ["synthetic"],
        }
        result = evaluator.evaluate_live_row(row, deterministic_skill=skill)
        assert result["live_delta"] in expected
