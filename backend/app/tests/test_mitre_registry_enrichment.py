from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.threat.mitre_decision import resolve_mitre_decision
from app.threat.mitre_registry_enrichment import (
    clear_mitre_enrichment_cache,
    load_mitre_enrichment_drafts,
    normalize_legacy_mitre_fields,
    registry_mitre_metadata,
)
from app.threat.mitre_registry_schema import (
    MitreRegistryMetadata,
    MitreVisibilityPolicy,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_QUESTION_DRAFT = _REPO_ROOT / "docs/input/mitre_enrichment/question_105_for_mitre_enrichment.DRAFT.json"
_USE_CASE_DRAFT = _REPO_ROOT / "docs/input/mitre_enrichment/use_case_42_for_mitre_enrichment.DRAFT.json"


@pytest.fixture(autouse=True)
def _clear_caches() -> None:
    clear_mitre_enrichment_cache()
    yield
    clear_mitre_enrichment_cache()


def test_draft_files_load_as_valid_json() -> None:
    q = json.loads(_QUESTION_DRAFT.read_text(encoding="utf-8"))
    u = json.loads(_USE_CASE_DRAFT.read_text(encoding="utf-8"))
    assert q["item_count"] == 105
    assert u["item_count"] == 42
    assert len(q["items"]) == 105
    assert len(u["items"]) == 42


def test_every_105_and_42_item_resolves_to_metadata() -> None:
    drafts = load_mitre_enrichment_drafts()
    assert drafts["question_count"] == 105
    assert drafts["use_case_count"] == 42
    for question_ref, item in drafts["questions_by_id"].items():
        meta = registry_mitre_metadata(question_ref=question_ref)
        assert meta is not None, question_ref
        assert meta.schema_version == "2026-06-control-plane-v1"
        assert meta.registry_role == "metadata_not_evidence"
    for use_case_id, item in drafts["use_cases_by_id"].items():
        meta = registry_mitre_metadata(use_case_id=use_case_id)
        assert meta is not None, use_case_id


def test_q046_brute_force_related_metadata() -> None:
    meta = registry_mitre_metadata(question_ref="q0.q046")
    assert meta is not None
    mapped = set(meta.all_mapped_technique_ids())
    assert "T1110.001" in mapped
    assert "T1078" in meta.mitre_blocked
    assert "T1003" in meta.mitre_blocked
    assert "T1562.001" in meta.mitre_blocked


def test_auth_failed_login_spike_blocks_and_maps_brute_force_family() -> None:
    meta = registry_mitre_metadata(use_case_id="auth_failed_login_spike")
    assert meta is not None
    mapped = set(meta.all_mapped_technique_ids())
    assert "T1110.001" in mapped
    assert "T1003" in meta.mitre_blocked
    assert "T1078" in meta.mitre_blocked
    assert "T1562.001" in meta.mitre_blocked
    assert "T1078" not in meta.mitre_permitted
    assert "T1078" not in meta.mitre_candidate


def test_auth_success_after_failure_may_include_t1078_as_candidate() -> None:
    meta = registry_mitre_metadata(use_case_id="auth_success_after_failure")
    assert meta is not None
    candidates = set(meta.mitre_candidate) | set(meta.mitre_permitted)
    assert "T1078" in candidates
    assert "T1110.001" in candidates
    assert "T1003" in meta.mitre_blocked


def test_policy_sop_rows_use_trace_only_or_answer_if_requested() -> None:
    meta = registry_mitre_metadata(use_case_id="soc_show_sop")
    assert meta is not None
    assert meta.mitre_visibility_policy in (
        MitreVisibilityPolicy.trace_only,
        MitreVisibilityPolicy.answer_if_requested,
    )


def test_blocked_and_permitted_overlap_fails_validation() -> None:
    with pytest.raises(ValueError, match="mitre_permitted overlaps mitre_blocked"):
        MitreRegistryMetadata(
            mitre_permitted=["T1110.001"],
            mitre_blocked=["T1110.001"],
        )


def test_blocked_not_in_attack_subset_allowed() -> None:
    meta = MitreRegistryMetadata(
        mitre_blocked=["T1562.001", "T1003"],
    )
    assert "T1562.001" in meta.mitre_blocked
    missing = meta.blocked_missing_from_attack_subset({"T1110.001", "T1078"})
    assert "T1562.001" in missing
    assert "T1003" in missing


def test_permitted_missing_from_attack_subset_is_warning_not_schema_failure() -> None:
    meta = MitreRegistryMetadata(mitre_permitted=["T9999.999"])
    missing = meta.techniques_missing_from_attack_subset({"T1110.001"})
    assert missing == ["T9999.999"]


def test_resolve_mitre_decision_defaults_to_safe_non_visible_runtime_decision() -> None:
    decision = resolve_mitre_decision(question_ref="q0.q046")
    assert decision.mitre_status in {"requires_alert_context", "not_answer_visible"}
    assert decision.answer_visible is False
    assert decision.registry_metadata is not None
    assert "T1110.001" in decision.registry_candidates


def test_registry_reads_promoted_runtime_question_row() -> None:
    from app.coverage.question_runtime_map import question_runtime_entry

    entry = question_runtime_entry("q0.q046", reload=True)
    assert entry is not None
    assert isinstance(entry.get("mitre_registry"), dict)
    meta = registry_mitre_metadata(question_ref="q0.q046")
    assert meta is not None
    assert "T1110.001" in meta.all_mapped_technique_ids()


def test_normalize_legacy_preserves_legacy_field_merge() -> None:
    item = {
        "mitre_registry": {
            "permitted": ["T1110.001"],
            "candidate": [],
            "blocked": ["T1003"],
            "requires_evidence": True,
            "requires_alert_context": False,
            "default_visibility": "trace_only",
            "answer_visibility_policy": "do_not_show_unless_user_asks_mitre",
        },
        "mitre_permitted": ["T1110"],
        "mitre_candidates": ["T1110.003"],
    }
    meta = normalize_legacy_mitre_fields(item, use_case_id="test_uc")
    assert "T1110.001" in meta.mitre_permitted
    assert "T1110" in meta.mitre_permitted
    assert "T1110.003" in meta.mitre_candidate
    assert meta.mitre_visibility_policy == MitreVisibilityPolicy.answer_if_requested
