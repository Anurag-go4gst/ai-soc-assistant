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


def test_extraction_yields_out_of_subset_candidates():
    candidates, bundle = mev.extract_candidates()
    # Post-G5 bulk promotion: 98-technique bundle (15 curated + 83 promoted). The
    # 83 promote_candidate IDs are now in-bundle, so the only out-of-subset proposals
    # left are the 13 dropped ones (ICS T08xx + deprecated/renumbered enterprise IDs).
    assert len(bundle) == 98
    assert len(candidates) == 13
    assert "T1071.004" not in candidates  # promoted earlier
    assert "T1003" not in candidates  # promoted by G5
    # Remaining are the genuinely-dropped IDs (ICS + deprecated/renumbered).
    assert {"T0819", "T1086", "T1043", "T1562.001"} <= set(candidates)
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


def test_disposition_classifies_attack_data_absent_as_deprecated():
    from app.threat.attack_data_resolver import AttackDataResolver

    candidates, _ = mev.extract_candidates()
    xlsx = Path(__file__).resolve().parents[3] / "docs" / "evals" / "enterprise-attack-v19.1.xlsx"
    atlas = Path(__file__).resolve().parents[3] / "docs" / "threat-intel" / "atlas" / "raw" / "ATLAS.yaml"
    resolver = AttackDataResolver(attack_xlsx_path=xlsx, atlas_yaml_path=atlas)
    rows = mev.disposition(["T1086", "T0819"], resolver)
    by_id = {r["technique_id"]: r["disposition"] for r in rows}
    assert by_id == {"T1086": "deprecated", "T0819": "not_found"}


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
