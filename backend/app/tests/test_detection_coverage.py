from __future__ import annotations

from app.knowledge.mapping_exports import build_atlas_coverage_gap, build_detection_coverage


def test_detection_coverage_shape_and_counts() -> None:
    payload = build_detection_coverage()
    assert payload["schema_role"] == "detection_coverage_v1"
    assert payload["technique_count"] == len(payload["techniques"])
    assert payload["covered_count"] + payload["gap_count"] == payload["technique_count"]
    # Every gap technique has no covering use case; every covered one has >=1.
    gap_ids = {g["technique_id"] for g in payload["gaps"]}
    for row in payload["techniques"]:
        if row["technique_id"] in gap_ids:
            assert row["covered"] is False
            assert row["covering_use_cases"] == []
        else:
            assert row["covered"] is True
            assert row["covering_use_cases"]


def test_detection_coverage_inverted_index_matches_rows() -> None:
    payload = build_detection_coverage()
    coverage = payload["coverage"]
    for tech_id, use_cases in coverage.items():
        assert use_cases == sorted(use_cases)  # rules_coverage_map sorts
        row = next(r for r in payload["techniques"] if r["technique_id"] == tech_id)
        assert row["covering_use_cases"] == use_cases


def test_atlas_coverage_gap_shape() -> None:
    payload = build_atlas_coverage_gap()
    assert payload["schema_role"] == "atlas_coverage_gap_v1"
    # ATLAS is onboarded as raw in-repo; enterprise covers none of the AML taxonomy.
    assert payload["atlas_source_status"] == "onboarded_raw_layer"
    assert payload["technique_count"] > 0
    assert payload["covered_count"] == 0
    assert payload["gap_count"] == payload["technique_count"]
    # AI-only tactics have no enterprise analogue and must be surfaced as the gap.
    assert "ai-model-access" in payload["ai_only_tactics"]
    assert "ai-attack-staging" in payload["ai_only_tactics"]
    # Frequency ranking is descending by case-study score.
    scores = [row["score"] for row in payload["top_techniques_by_case_study_frequency"]]
    assert scores == sorted(scores, reverse=True)
