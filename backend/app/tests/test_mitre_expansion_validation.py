"""Tests for the MITRE expansion-candidate extraction/validation (plan §15 G3)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parents[3]
    / "scripts"
    / "validate_mitre_expansion_candidates.py"
)
_spec = importlib.util.spec_from_file_location("validate_mitre_expansion_candidates", _SCRIPT)
assert _spec and _spec.loader
mev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mev)


def test_extraction_yields_97_out_of_subset_candidates():
    candidates, bundle = mev.extract_candidates()
    # The 13-technique local bundle is excluded; 97 out-of-subset proposals remain
    # (audit llm_invalid_ids union minus bundle). Stable input contract for G3.
    assert len(bundle) == 13
    assert len(candidates) == 97
    # No bundle ID leaks into the candidate set.
    assert not (set(candidates) & bundle)
    # Deterministic ordering (sorted).
    assert candidates == sorted(candidates)


def test_disposition_pending_when_resolver_absent():
    candidates, _ = mev.extract_candidates()
    rows = mev.disposition(candidates, resolver=None)
    assert len(rows) == len(candidates)
    assert all(r["disposition"] == "pending_bundle" for r in rows)
    assert all(r["detail"] is None for r in rows)


class _FakeResolver:
    operational = True

    def __init__(self, table):
        self._table = table

    def detail(self, tid):
        return self._table.get(tid)


def test_disposition_classifies_with_operational_resolver():
    table = {
        "T1003": {"name": "OS Credential Dumping", "deprecated": False, "revoked": False},
        "T1086": {"name": "PowerShell (deprecated)", "deprecated": True, "revoked": False},
        "T9999": None,  # not found
    }
    rows = mev.disposition(["T1003", "T1086", "T9999"], _FakeResolver(table))
    by_id = {r["technique_id"]: r["disposition"] for r in rows}
    assert by_id == {
        "T1003": "promote_candidate",
        "T1086": "deprecated",
        "T9999": "not_found",
    }
