"""L2 bank — manifest integrity and anti-accident guards.

This file is the reason the bank can be trusted as *architecture* rather than as a
pile of tests. It enforces, mechanically:

* one row, one invariant — duplicated invariants are rejected;
* every active row is bound to a test that really exists, in both directions;
* the P0 13 are still present and still owned by their original invariants;
* a reserved row cannot accidentally execute, and cannot name a field whose
  contract has not merged.

That last guard is the important one. "Do not invent expected fields for a contract
another workstream still owns" is a rule that decays the moment it depends on review
attention. Requiring ``expected_stable_oracle_fields`` to be empty for every reserved
row turns it into a failing test instead.
"""

from __future__ import annotations

import importlib
from collections import Counter
from pathlib import Path

import pytest

from app.tests.support.l2_bank_manifest import (
    ACTIVE_STATUSES,
    CASES,
    NEW_ACTIVE_CASES,
    P0_CASES,
    RESERVED_STATUSES,
    active_cases,
    cases_by_status,
    reserved_cases,
)

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_JOURNEY_MODULE = "app.tests.test_l2_bank_journeys"
_P0_MODULE = "app.tests.test_p0_l2_production_chat_harness"


def _split_node_id(node_id: str) -> tuple[str, str]:
    path, _, function = node_id.partition("::")
    return path, function


# ---------------------------------------------------------------------------
# Structural integrity
# ---------------------------------------------------------------------------


def test_case_ids_are_unique() -> None:
    duplicates = [item for item, count in Counter(c.case_id for c in CASES).items() if count > 1]
    assert not duplicates, f"duplicate case_id(s): {duplicates}"


def test_every_row_owns_a_distinct_invariant() -> None:
    """The whole point of the bank: no two rows may prove the same thing."""
    duplicates = [
        item for item, count in Counter(c.invariant_owner for c in CASES).items() if count > 1
    ]
    assert not duplicates, f"duplicate invariant_owner(s): {duplicates}"


def test_required_prose_fields_are_populated() -> None:
    """A row without intent or rationale is a row nobody can adjudicate later."""
    incomplete = [
        c.case_id
        for c in CASES
        if not c.title.strip()
        or not c.user_intent.strip()
        or not c.why_this_case_exists.strip()
        or not c.expected_analyst_visible_result.strip()
        or not c.invariant_owner.strip()
    ]
    assert not incomplete, f"rows missing required prose: {incomplete}"


def test_every_row_declares_prohibited_outputs() -> None:
    """What must *not* appear is the half of an L2 row that catches regressions."""
    missing = [c.case_id for c in CASES if not c.prohibited_outputs]
    assert not missing, f"rows with no prohibited_outputs: {missing}"


def test_statuses_are_known() -> None:
    known = ACTIVE_STATUSES | RESERVED_STATUSES
    unknown = sorted({c.current_status for c in CASES} - known)
    assert not unknown, f"unknown status value(s): {unknown}"


# ---------------------------------------------------------------------------
# Active rows are really bound to really-existing tests
# ---------------------------------------------------------------------------


def test_active_rows_declare_a_bound_test() -> None:
    unbound = [c.case_id for c in active_cases() if not c.bound_test]
    assert not unbound, f"ACTIVE rows without bound_test: {unbound}"


def test_bound_test_files_exist() -> None:
    missing = []
    for case in active_cases():
        assert case.bound_test is not None
        path, _ = _split_node_id(case.bound_test)
        if not (_BACKEND_ROOT / path).is_file():
            missing.append((case.case_id, path))
    assert not missing, f"bound_test points at a missing file: {missing}"


@pytest.mark.parametrize(
    "case_id,node_id",
    [(c.case_id, c.bound_test) for c in active_cases()],
    ids=[c.case_id for c in active_cases()],
)
def test_each_active_row_resolves_to_a_real_test_function(case_id: str, node_id: str) -> None:
    """A manifest row that points at a test which no longer exists is a silent hole."""
    path, function = _split_node_id(node_id)
    module_name = path.removesuffix(".py").replace("/", ".")
    module = importlib.import_module(module_name)
    resolved = getattr(module, function, None)
    assert callable(resolved), f"{case_id}: {node_id} does not resolve to a test function"


def test_journey_module_has_no_unregistered_tests() -> None:
    """The reverse direction: a test here without a manifest row is untracked coverage."""
    module = importlib.import_module(_JOURNEY_MODULE)
    defined = {
        name
        for name in vars(module)
        if name.startswith("test_") and callable(getattr(module, name))
    }
    registered = {
        _split_node_id(c.bound_test)[1]
        for c in CASES
        if c.bound_test and _split_node_id(c.bound_test)[0].endswith("test_l2_bank_journeys.py")
    }
    assert defined == registered, (
        f"journey tests not in manifest: {sorted(defined - registered)}; "
        f"manifest rows with no such test: {sorted(registered - defined)}"
    )


# ---------------------------------------------------------------------------
# The P0 13 are preserved, not rewritten
# ---------------------------------------------------------------------------


def test_p0_block_still_has_exactly_thirteen_rows() -> None:
    assert len(P0_CASES) == 13


def test_p0_rows_all_point_at_the_untouched_p0_harness() -> None:
    stray = [
        c.case_id
        for c in P0_CASES
        if not (c.bound_test or "").startswith("app/tests/test_p0_l2_production_chat_harness.py::")
    ]
    assert not stray, f"P0 rows must stay bound to the P0 harness file: {stray}"


def test_p0_harness_still_defines_exactly_the_registered_thirteen() -> None:
    """Guards against a P0 test being renamed, removed, or quietly added to."""
    module = importlib.import_module(_P0_MODULE)
    defined = {
        name
        for name in vars(module)
        if name.startswith("test_") and callable(getattr(module, name))
    }
    registered = {_split_node_id(c.bound_test or "")[1] for c in P0_CASES}
    assert defined == registered, (
        f"P0 harness drifted from the manifest. only-in-file: {sorted(defined - registered)}; "
        f"only-in-manifest: {sorted(registered - defined)}"
    )


# ---------------------------------------------------------------------------
# Reserved rows cannot accidentally execute or speculate
# ---------------------------------------------------------------------------


def test_reserved_rows_have_no_bound_test() -> None:
    """A reserved row with a bound test would run before its contract exists."""
    bound = [(c.case_id, c.bound_test) for c in reserved_cases() if c.bound_test]
    assert not bound, f"reserved rows must not bind a test: {bound}"


def test_reserved_rows_declare_no_speculative_oracle_fields() -> None:
    """Anti-speculation guard.

    P1/P2/P4 own these field names and have not published them. A reserved row states
    its invariant in prose; naming a field here would pin a contract that does not
    exist yet and would have to be rewritten on merge.
    """
    speculative = [
        (c.case_id, c.expected_stable_oracle_fields)
        for c in reserved_cases()
        if c.expected_stable_oracle_fields
    ]
    assert not speculative, f"reserved rows must not name oracle fields yet: {speculative}"


def test_active_rows_do_declare_oracle_fields() -> None:
    """The converse: an active row asserting nothing stable is not carrying its weight."""
    empty = [c.case_id for c in active_cases() if not c.expected_stable_oracle_fields]
    assert not empty, f"ACTIVE rows must declare their stable oracle fields: {empty}"


def test_pending_rows_name_the_phase_that_unblocks_them() -> None:
    pending = [c for c in CASES if c.current_status.startswith("PENDING_CONTRACT_")]
    mismatched = [
        c.case_id
        for c in pending
        if c.dependency_phase not in c.current_status.removeprefix("PENDING_CONTRACT_")
    ]
    assert not mismatched, f"pending rows whose dependency_phase disagrees with status: {mismatched}"
    assert pending, "the bank should still be reserving contract-dependent rows"


# ---------------------------------------------------------------------------
# Gaps stay visible; deferrals stay evidenced
# ---------------------------------------------------------------------------


def test_product_gaps_are_not_quietly_resolved() -> None:
    """A PRODUCT_GAP must carry an explicit, unresolved disposition placeholder.

    Choosing SUPPORTED_NOW here requires evidence and an operator decision, neither of
    which P3 has. Leaving it UNDECIDED is the honest state, and this test stops the
    placeholder from being filled in by momentum.
    """
    gaps = cases_by_status("PRODUCT_GAP")
    assert gaps, "the known product gaps must stay catalogued"
    resolved_without_evidence = [
        c.case_id for c in gaps if c.future_disposition != "UNDECIDED" and not c.support_evidence
    ]
    assert not resolved_without_evidence, (
        f"PRODUCT_GAP rows resolved without recorded evidence: {resolved_without_evidence}"
    )


def test_deferred_rows_record_why_they_are_believed_supported() -> None:
    deferred = cases_by_status("DEFERRED")
    unevidenced = [c.case_id for c in deferred if not c.support_evidence.strip()]
    assert not unevidenced, f"DEFERRED rows must record their probe evidence: {unevidenced}"


def test_known_findings_are_represented_in_the_bank() -> None:
    """The gaps this plan explicitly told P3 to keep visible must each own a row."""
    covered = {finding for case in CASES for finding in case.findings}
    for required in ("H-FOLLOW-03", "H-FOLLOW-04", "H-EVID-02", "H-REM-03", "H-MCP-10"):
        assert required in covered, f"{required} lost its L2 row"


# ---------------------------------------------------------------------------
# Bank shape
# ---------------------------------------------------------------------------


def test_active_bank_is_p0_plus_supported_contract_rows() -> None:
    """First E1 bank was ~23. After P1/P2/P4/P5 activation the count is the real manifest."""
    count = len(active_cases())
    assert len(P0_CASES) == 13
    assert count == len([c for c in CASES if c.current_status == "ACTIVE_GREEN"])
    assert count >= 23
    pending_p5 = cases_by_status("PENDING_CONTRACT_P5")
    assert pending_p5, (
        "H-FOLLOW-05 rows stay reserved: production has no rejected-conclusion "
        "or analyst-supplied SourceEvidence intake contract"
    )
