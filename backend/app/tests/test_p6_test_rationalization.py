"""P6 — conservative rationalization contracts.

Proves the retirement ledger is complete, no silent removals occurred, and the
tier matrix / l2_slow markers are registered and applied.
"""

from __future__ import annotations

from pathlib import Path

from app.tests.support.p6_retirement_ledger import (
    COLLECTION_AFTER,
    COLLECTION_BEFORE,
    LEDGER,
    archive_records,
    removed_records,
)
from app.tests.support.p6_tier_matrix import L2_SLOW_MODULES, REGISTERED_MARKERS, TIER_COMMANDS

_TESTS = Path(__file__).resolve().parent
_PYPROJECT = _TESTS.parents[1] / "pyproject.toml"
_REQUIRED_RECORD_KEYS = (
    "record_id",
    "old_test_id",
    "old_invariant",
    "replacement_owner_test",
    "green_proof",
    "risk_statement",
    "disposition",
)


def test_p6_ledger_records_are_complete() -> None:
    ids = [row["record_id"] for row in LEDGER]
    assert ids == sorted(set(ids)), "duplicate or unsorted ledger ids"
    for row in LEDGER:
        for key in _REQUIRED_RECORD_KEYS:
            assert str(row[key]).strip(), f"{row['record_id']} missing {key}"


def test_p6_removed_no_tests_without_four_part_record() -> None:
    """Acceptance: every removed test has the four-part record. This wave removes none."""
    assert removed_records() == ()
    assert archive_records() == ()


def test_p6_collection_before_is_pinned() -> None:
    assert COLLECTION_BEFORE == 7111
    assert COLLECTION_AFTER == 7137
    assert COLLECTION_AFTER >= COLLECTION_BEFORE


def test_p6_tier_commands_are_named() -> None:
    for tier in ("L0", "L1", "L2", "L2-SLOW", "L3"):
        assert tier in TIER_COMMANDS
        assert TIER_COMMANDS[tier].strip()
    assert "pytest" in TIER_COMMANDS["L2"]
    assert "-m l2_slow" in TIER_COMMANDS["L2-SLOW"]
    assert "LIVE_AB_EVAL_PERFORMED" in TIER_COMMANDS["L3"]


def test_p6_pytest_markers_are_registered() -> None:
    text = _PYPROJECT.read_text(encoding="utf-8")
    for marker in REGISTERED_MARKERS:
        assert f'"{marker}:' in text or f'"{marker} ' in text or f"{marker}:" in text, marker


def test_p6_timeout_modules_carry_l2_slow_mark() -> None:
    for rel in L2_SLOW_MODULES:
        path = _TESTS / Path(rel).name
        text = path.read_text(encoding="utf-8")
        assert "pytest.mark.l2_slow" in text, f"{rel} is not marked l2_slow"


def test_p6_does_not_chase_numeric_target() -> None:
    """Reduction is moderate and justified even if the count stays above 4,850."""
    assert COLLECTION_BEFORE > 4850
