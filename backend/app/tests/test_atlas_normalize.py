"""WS-E E3: ATLAS raw → normalized canonical layer tests."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "atlas_normalize.py"
_spec = importlib.util.spec_from_file_location("atlas_normalize", _SCRIPT)
assert _spec and _spec.loader
an = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(an)


def test_collapses_multi_tactic_into_one_row():
    matrix = [
        {"techniqueID": "AML.T0001", "tactic": "reconnaissance", "score": 5},
        {"techniqueID": "AML.T0001", "tactic": "discovery", "score": 3},
        {"techniqueID": "AML.T0002", "tactic": "impact"},
    ]
    freq = [{"techniqueID": "AML.T0001", "score": 9}]
    result = an.normalize(matrix, freq)
    assert result["technique_count"] == 2
    row = next(r for r in result["techniques"] if r["technique_id"] == "AML.T0001")
    assert row["tactics"] == ["discovery", "reconnaissance"]
    assert row["per_tactic_score"] == {"discovery": 3, "reconnaissance": 5}
    assert row["case_study_score"] == 9


def test_real_layer_170_canonical_and_provenance():
    report = an.build_report()
    assert report["technique_count"] == 170
    assert report["provenance"]["raw_row_count"] == 185
    # source_sha256 ties the normalized output to the immutable raw artifact.
    assert len(report["provenance"]["source_sha256"]) == 64
    assert report["normalization_rules_version"] == an.NORMALIZATION_RULES_VERSION
