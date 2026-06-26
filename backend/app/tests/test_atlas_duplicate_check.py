"""Unit tests for the ATLAS raw duplicate/multi-tactic gate (plan §7 E2)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "atlas_duplicate_check.py"
_spec = importlib.util.spec_from_file_location("atlas_duplicate_check", _SCRIPT)
assert _spec and _spec.loader
adc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(adc)


def test_cross_tactic_repeat_detected():
    rows = [
        {"techniqueID": "AML.T0001", "tactic": "reconnaissance"},
        {"techniqueID": "AML.T0001", "tactic": "discovery"},
        {"techniqueID": "AML.T0002", "tactic": "impact"},
    ]
    report = adc.analyze(rows)
    assert report["cross_tactic_repeat_count"] == 1
    assert report["cross_tactic_repeats"] == {"AML.T0001": ["discovery", "reconnaissance"]}
    assert report["distinct_technique_count"] == 2
    assert report["row_count"] == 3


def test_same_tactic_duplicate_detected():
    rows = [
        {"techniqueID": "AML.T0003", "tactic": "execution"},
        {"techniqueID": "AML.T0003", "tactic": "execution"},
    ]
    report = adc.analyze(rows)
    assert report["same_tactic_duplicate_count"] == 1
    assert report["same_tactic_duplicates"] == {"AML.T0003|execution": 2}
    assert report["cross_tactic_repeat_count"] == 0


def test_parent_sub_collision_detected():
    rows = [
        {"techniqueID": "AML.T0051", "tactic": "initial-access"},
        {"techniqueID": "AML.T0051.000", "tactic": "initial-access"},
        {"techniqueID": "AML.T0099.001", "tactic": "impact"},  # parent absent -> no collision
    ]
    report = adc.analyze(rows)
    assert report["parent_sub_collisions"] == {"AML.T0051.000": "AML.T0051"}
    assert report["parent_sub_collision_count"] == 1


def test_empty_and_blank_ids_ignored():
    rows = [{"techniqueID": "", "tactic": "x"}, {"tactic": "y"}]
    report = adc.analyze(rows)
    assert report["distinct_technique_count"] == 0
    assert report["row_count"] == 2  # row_count is raw rows, not distinct


def test_real_atlas_layer_shape():
    """Sanity-check against the staged raw layer: 170 distinct, 14 cross-tactic."""
    rows = adc._load_layer(adc.MATRIX_PATH)
    report = adc.analyze(rows)
    assert report["distinct_technique_count"] == 170
    assert report["cross_tactic_repeat_count"] == 14
    assert report["same_tactic_duplicate_count"] == 0
