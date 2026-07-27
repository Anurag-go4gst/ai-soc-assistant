"""Item 31 — parity projection and classification contract.

Three classifications, exhaustive and mutually exclusive. Governance fields can never be
approved into `approved_difference`, and no behavioural field may hide in the exclusion list.
"""

from __future__ import annotations

import pytest

from app.evals.production_runtime_parity import (
    APPROVAL_INELIGIBLE_FIELDS,
    APPROVED_DIFFERENCES,
    COMPARISON_FIELDS,
    EXCLUDED_FIELDS,
    classify_row,
)

_CLASSIFICATIONS = {"exact_match", "approved_difference", "critical_mismatch"}

_COMPLETE_APPROVAL = {
    "field": "placeholder",
    "runtime_a_value": "a",
    "runtime_b_value": "b",
    "reason": "documented runtime divergence",
    "contract_owner": "app/evals/production_runtime_parity.py",
    "approval_ref": "plan item 31",
}


def _base() -> dict[str, object]:
    return {field: "same" for field in COMPARISON_FIELDS}


def test_classifications_are_exhaustive_and_mutually_exclusive() -> None:
    base = _base()
    seen = {classify_row(base, dict(base))[0]}
    seen.add(classify_row(base, dict(base, hil_required="other"))[0])
    assert seen <= _CLASSIFICATIONS
    assert "exact_match" in seen and "critical_mismatch" in seen


@pytest.mark.parametrize("field", sorted(APPROVAL_INELIGIBLE_FIELDS))
def test_governance_fields_cannot_be_approved(field: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Even a complete six-part record must not soften a governance difference."""
    monkeypatch.setitem(APPROVED_DIFFERENCES, field, dict(_COMPLETE_APPROVAL, field=field))
    base = _base()
    classification, diffs = classify_row(base, dict(base, **{field: "diverged"}))
    assert classification == "critical_mismatch"
    record = next(d for d in diffs if d["field"] == field)
    assert record["approval_eligible"] is False
    assert record["approved"] is False


def test_every_compared_field_is_currently_approval_ineligible() -> None:
    """No field in the projection is approvable today.

    Adding one must be a deliberate act: a new comparison field that is not listed as
    ineligible fails here until someone justifies why it may be approved.
    """
    approvable = set(COMPARISON_FIELDS) - APPROVAL_INELIGIBLE_FIELDS
    assert approvable == set(), f"unclassified approvable fields: {sorted(approvable)}"


def test_ineligible_list_does_not_name_unknown_fields() -> None:
    unknown = APPROVAL_INELIGIBLE_FIELDS - set(COMPARISON_FIELDS)
    assert unknown == set(), f"ineligible list names fields that are not compared: {sorted(unknown)}"


def test_no_behavioural_field_hides_in_the_exclusion_list() -> None:
    overlap = set(EXCLUDED_FIELDS) & set(COMPARISON_FIELDS)
    assert overlap == set(), f"fields both compared and excluded: {sorted(overlap)}"
    for field, justification in EXCLUDED_FIELDS.items():
        assert justification.strip(), f"{field} excluded without justification"


def test_dead_acceptable_diff_tolerance_list_is_gone() -> None:
    """Item 31: dead tolerance configuration is deleted, not left as decoration."""
    import app.evals.langgraph_dual_parity as legacy

    assert not hasattr(legacy, "_ACCEPTABLE_DIFF_FIELDS")


def test_legacy_classifier_still_reports_any_difference() -> None:
    """Removing the dead list must not change legacy behaviour."""
    from app.evals.langgraph_dual_parity import classify_parity_row

    same = {"path_type": "spl_review", "branches": ["spl"]}
    assert classify_parity_row(dict(same), dict(same))[0] == "match"
    category, diffs, _ = classify_parity_row(dict(same), dict(same, path_type="rag_only"))
    assert category == "acceptable_diff"
    assert "path_type" in diffs
