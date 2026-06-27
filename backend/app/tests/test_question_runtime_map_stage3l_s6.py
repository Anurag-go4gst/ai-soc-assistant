"""Stage 3L-S6: 105-question runtime operation mapping registry."""

from __future__ import annotations

from app.coverage.question_runtime_map import (
    list_question_runtime_entries,
    load_question_runtime_map,
    manifest_coverage_ids_from_map,
    question_runtime_entry,
)


def test_map_has_105_questions() -> None:
    payload = load_question_runtime_map()
    entries = list_question_runtime_entries()
    assert payload["question_count"] == 105
    assert len(entries) == 105
    assert payload["map_version"] == "stage3l_s6_v1"


def test_manifest_rows_linked() -> None:
    payload = load_question_runtime_map()
    assert payload["manifest_row_count"] == 11
    in_manifest = [e for e in list_question_runtime_entries() if e["promotion_status"] == "in_manifest"]
    assert len(in_manifest) == 11
    assert manifest_coverage_ids_from_map() == frozenset(
        e["manifest_coverage_id"] for e in in_manifest if e.get("manifest_coverage_id")
    )


def test_q046_authority_pilot_metadata() -> None:
    entry = question_runtime_entry("q046")
    assert entry is not None
    assert entry["authority_pilot_candidate"] is True
    assert entry["manifest_coverage_id"] == "cov.q046.excessive_failed_logins_sample"
    assert entry["skill_drift"] is True
    assert entry["s3_authority_ready"] is False
    assert "coe_step3_implementation_not_approved" in entry["s3_authority_blockers"]


def test_all_pattern_types_mapped() -> None:
    entries = list_question_runtime_entries()
    pattern_types = {e["pattern_type"] for e in entries}
    assert "top_n_aggregation" in pattern_types
    assert "threshold_anomaly" in pattern_types
    assert "other_or_unclear" in pattern_types
    blocked = [e for e in entries if e.get("route_blocked")]
    assert any(e["pattern_type"] == "other_or_unclear" for e in blocked)
