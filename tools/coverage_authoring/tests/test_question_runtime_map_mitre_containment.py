"""Plan 5 A2 — regenerating the runtime map must not broaden analyst-visible MITRE claims.

A1 measured that the builder defect is not only a metadata loss. `registry_mitre_metadata_for_runtime`
takes the governed path only when a row carries a `mitre_registry` dict
(`backend/app/threat/mitre_registry_enrichment.py:280`). The builder drops that field, so a regenerated
map falls back to the draft/enrichment path, which does not apply the registry's suppression — and
the system starts asserting MITRE technique IDs on questions the governed registry deliberately
suppresses.

That is an unsupported-claim broadening, so these tests assert a **containment** property, not a
formatting one: for every one of the 105 rows, the MITRE metadata resolved from a freshly built row
must be identical to the metadata resolved from the committed governed row, and in particular must
introduce no technique ID that the committed row does not already claim.

The eleven rows pinned below are the ones A1 measured as broadening pre-fix. They are named
explicitly so that a future regression reports *which* governed suppression broke, not merely that a
count moved.

Nothing here writes the artifact — the map is built in memory only.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from question_runtime_map_builder import OUTPUT_PATH, build_question_runtime_map

import app.threat.mitre_registry_enrichment as mre

#: Measured at HEAD 2080420 (Plan 5 A1). Pre-fix, a rebuild made each row assert the listed
#: technique while the committed governed row asserts none.
BROADENED_PRE_FIX: dict[str, list[str]] = {
    "q0.q021": ["T1071"],
    "q0.q028": ["T1071"],
    "q0.q040": ["T1071"],
    "q0.q046": ["T1110"],
    "q0.q047": ["T1110"],
    "q0.q050": ["T1059.001"],
    "q0.q060": ["T1110"],
    "q0.q062": ["T1110"],
    "q0.q063": ["T1059.001"],
    "q0.q083": ["T1059.001"],
    "q0.q089": ["T1110"],
}


def _rows_by_ref(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(e["question_ref"]): e for e in payload["entries"]}


def _resolve_all(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Resolve every row through the real live lookup, with the map swapped for `rows`.

    `registry_mitre_metadata_for_runtime` is the function the live MITRE branch calls
    (`chat/mitre_branch.py:72`, `threat/mitre_decision.py:67`). Driving it — rather than
    `normalize_legacy_mitre_fields` directly — is what makes these tests observe the draft/enrichment
    fallback, which is where the broadening actually happens. Resolving through the normalizer alone
    silently passes and proves nothing.
    """
    with patch.object(mre, "_load_runtime_question_entries_by_ref", lambda: rows):
        return {ref: mre.registry_mitre_metadata_for_runtime(question_ref=ref) for ref in rows}


@pytest.fixture(scope="module")
def committed_rows() -> dict[str, dict[str, Any]]:
    return _rows_by_ref(json.loads(OUTPUT_PATH.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def rebuilt_rows() -> dict[str, dict[str, Any]]:
    return _rows_by_ref(build_question_runtime_map())


@pytest.fixture(scope="module")
def committed_meta(committed_rows) -> dict[str, Any]:
    return _resolve_all(committed_rows)


@pytest.fixture(scope="module")
def rebuilt_meta(rebuilt_rows) -> dict[str, Any]:
    return _resolve_all(rebuilt_rows)


def test_rebuild_introduces_no_new_technique_claim(committed_meta, rebuilt_meta) -> None:
    """The containment property: a rebuild may never widen the set of claimed techniques."""
    widened: dict[str, dict[str, list[str]]] = {}
    for ref, before in committed_meta.items():
        after = rebuilt_meta[ref]
        for field in ("mitre_permitted", "mitre_candidate"):
            new = [t for t in getattr(after, field) if t not in set(getattr(before, field))]
            if new:
                widened.setdefault(ref, {})[field] = new

    assert not widened, (
        "regenerating the runtime map asserts MITRE techniques the governed committed map "
        f"suppresses (question_ref -> field -> newly claimed): {widened}"
    )


@pytest.mark.parametrize("ref", sorted(BROADENED_PRE_FIX))
def test_named_broadening_rows_stay_suppressed(ref, committed_meta, rebuilt_meta) -> None:
    """Pin each row A1 measured as broadening, so a regression names the specific suppression."""
    before = committed_meta[ref]
    after = rebuilt_meta[ref]
    assert after.mitre_candidate == before.mitre_candidate, (
        f"{ref}: governed committed map claims {before.mitre_candidate}, rebuild claims "
        f"{after.mitre_candidate} (A1 forecast this row would broaden to "
        f"{BROADENED_PRE_FIX[ref]} when mitre_registry is dropped)"
    )


def test_governed_registry_block_survives_regeneration(committed_rows, rebuilt_rows) -> None:
    """The mechanism behind the containment property, asserted directly.

    `registry_mitre_metadata_for_runtime` only takes the governed branch when this field is a dict,
    so its absence is what silently re-routes a row to the unsuppressed fallback.
    """
    missing = [ref for ref, row in rebuilt_rows.items() if not isinstance(row.get("mitre_registry"), dict)]
    assert not missing, (
        "rows lost their governed `mitre_registry` block on rebuild, which re-routes the live "
        f"lookup to the unsuppressed draft fallback: {missing[:12]}{'…' if len(missing) > 12 else ''}"
    )


def test_all_105_rows_resolve_identically(committed_meta, rebuilt_meta) -> None:
    """Stronger than containment: the resolved metadata must be equal, not merely no wider."""
    differing = {
        ref: (before.model_dump(), rebuilt_meta[ref].model_dump())
        for ref, before in committed_meta.items()
        if before.model_dump() != rebuilt_meta[ref].model_dump()
    }
    assert not differing, (
        f"{len(differing)} row(s) resolve different MITRE metadata after rebuild: "
        f"{sorted(differing)[:12]}"
    )
