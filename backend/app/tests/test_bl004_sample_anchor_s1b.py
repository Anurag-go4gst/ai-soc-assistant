"""BL-004 S1b: sample detection-family anchors are matrix-only and non-routable."""

from __future__ import annotations

import json
from pathlib import Path

from app.use_cases.registry import match_use_cases

REPO_ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = REPO_ROOT / "backend" / "app" / "use_cases" / "catalog.json"
MATRIX_PATH = REPO_ROOT / "docs" / "evals" / "skill_coverage_matrix.json"
CURATED_MAP_PATH = REPO_ROOT / "docs" / "evals" / "question_use_case_map.json"

S1B_SAMPLE_ANCHORS = frozenset(
    {
        "sample_ioc_correlation_indicator_match",
        "sample_threshold_anomaly_volume_spike",
        "sample_powershell_suspicious_execution",
        "sample_dlp_exfiltration_volume",
    }
)

S1B_CURATED_QUESTIONS = frozenset(
    {
        "q0.q004",
        "q0.q013",
        "q0.q009",
        "q0.q051",
    }
)


def _load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def test_s1b_sample_anchors_are_sample_tier_with_no_intent_patterns() -> None:
    catalog = _load_json(CATALOG_PATH)
    by_id = {row["use_case_id"]: row for row in catalog["use_cases"]}
    for anchor_id in S1B_SAMPLE_ANCHORS:
        row = by_id[anchor_id]
        assert row["registry_tier"] == "sample"
        assert row["intent_patterns"] == []
        assert row["example_queries"] == []
        assert row["execution_eligible_default"] is False


def test_s1b_catalog_router_does_not_select_sample_anchors() -> None:
    probes = [
        "Which hosts contacted known malicious IPs today?",
        "Which systems generated large outbound data transfers?",
        "Which hosts communicated with many unique external IPs?",
        "What unusual processes ran on critical servers?",
    ]
    for query in probes:
        matches = match_use_cases(query)
        matched_ids = {item.use_case_id for item in matches}
        assert not matched_ids & S1B_SAMPLE_ANCHORS, (query, matched_ids)


def test_s1b_coverage_matrix_warnings_decreased_and_sample_mappings_present() -> None:
    matrix = _load_json(MATRIX_PATH)
    assert isinstance(matrix, list)
    mapped = [row for row in matrix if row["mapping_status"] != "missing_authoritative_mapping"]
    unmapped = [row for row in matrix if row["mapping_status"] == "missing_authoritative_mapping"]
    assert len(mapped) == 38
    assert len(unmapped) == 67

    sample_mapped = [row for row in mapped if row.get("use_case_id") in S1B_SAMPLE_ANCHORS]
    assert len(sample_mapped) == 30
    for row in sample_mapped:
        assert row["mapping_status"] == "curated_manual"
        assert row["mapping_confidence"] == "high"


def test_s1b_curated_mappings_skip_reviewed_unmapped_rows() -> None:
    curated = _load_json(CURATED_MAP_PATH)
    reviewed = {item["question_id"] for item in curated.get("reviewed_unmapped", [])}
    assert not reviewed & set(curated["mappings"].keys())
    for question_id in S1B_CURATED_QUESTIONS:
        assert question_id in curated["mappings"]
