"""P5: MITRE candidate mapping tests.

Covers:
- Deterministic mitre_permitted builder (P5-6/P5-8): known use-case, status bridge,
  not_mapped when no use-case, not_applicable path
- Bundle expansion (T1110 parent + T1110.003 present)
- LLM sidecar mapper (P5-10): valid candidate, markdown-wrapped JSON repaired,
  unknown ID downgraded, weak rationale downgraded, parse failure, not_mapped fallback
- SOC review export (P5-9): report-only, soc_approved always False from builder
- Authority boundary: LLM cannot produce status=supported; no mitre_permitted[] write
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from app.threat.mitre_candidate_mapper import (
    MitreCandidateMapResult,
    run_mitre_candidate_mapping,
)
from app.threat.mitre_kb import load_mitre_techniques
from app.threat.mitre_permitted_builder import (
    STATUS_CANDIDATE,
    STATUS_NEEDS_REVIEW,
    STATUS_NOT_MAPPED,
    STATUS_SUPPORTED,
    build_mitre_permitted_for_question,
    bridge_mitre_status,
    technique_in_local_bundle,
)
from app.threat.mitre_soc_review_export import build_soc_review_record


# ---------------------------------------------------------------------------
# Bundle expansion (P5 prerequisite)
# ---------------------------------------------------------------------------


def test_bundle_contains_t1110_parent() -> None:
    techniques = {t.technique_id for t in load_mitre_techniques()}
    assert "T1110" in techniques, "T1110 parent must be in local bundle for P5 eval targets"


def test_bundle_contains_t1110_003() -> None:
    techniques = {t.technique_id for t in load_mitre_techniques()}
    assert "T1110.003" in techniques, "T1110.003 Password Spraying must be in local bundle"


def test_bundle_contains_t1110_001() -> None:
    assert technique_in_local_bundle("T1110.001")


def test_bundle_contains_t1078() -> None:
    assert technique_in_local_bundle("T1078")


def test_unknown_id_not_in_bundle() -> None:
    assert not technique_in_local_bundle("T9999"), "T9999 must not be in local bundle for unknown-ID downgrade tests"


# ---------------------------------------------------------------------------
# Status bridge (P5-8)
# ---------------------------------------------------------------------------


def test_bridge_confirmed_to_supported() -> None:
    assert bridge_mitre_status("confirmed") == STATUS_SUPPORTED


def test_bridge_supported_stays_supported() -> None:
    assert bridge_mitre_status("supported") == STATUS_SUPPORTED


def test_bridge_candidate_stays_candidate() -> None:
    assert bridge_mitre_status("candidate") == STATUS_CANDIDATE


def test_bridge_requires_validation_to_needs_review() -> None:
    assert bridge_mitre_status("requires_validation") == STATUS_NEEDS_REVIEW


def test_bridge_analyst_review_to_needs_review() -> None:
    assert bridge_mitre_status("analyst_review") == STATUS_NEEDS_REVIEW


def test_bridge_unknown_to_needs_review() -> None:
    assert bridge_mitre_status("bogus_status") == STATUS_NEEDS_REVIEW


# ---------------------------------------------------------------------------
# Deterministic mitre_permitted builder (P5-6)
# ---------------------------------------------------------------------------


def test_builder_known_use_case_returns_entries() -> None:
    result = build_mitre_permitted_for_question("q0.q001", use_case_id="auth_failed_login_spike")
    assert result.use_case_id == "auth_failed_login_spike"
    assert len(result.entries) > 0
    technique_ids = {e.technique_id for e in result.entries}
    assert "T1110.001" in technique_ids


def test_builder_t1110_001_is_supported_for_auth_failed_login_spike() -> None:
    result = build_mitre_permitted_for_question("q0.q001", use_case_id="auth_failed_login_spike")
    entry = next((e for e in result.entries if e.technique_id == "T1110.001"), None)
    assert entry is not None
    assert entry.status == STATUS_SUPPORTED


def test_builder_t1110_001_needs_review_for_success_after_failure() -> None:
    """P5 report builder must not upgrade beyond live mitre_kb default status."""
    result = build_mitre_permitted_for_question("q0.q060", use_case_id="auth_success_after_failure")
    entry = next((e for e in result.entries if e.technique_id == "T1110.001"), None)
    assert entry is not None
    assert entry.status == STATUS_NEEDS_REVIEW
    assert entry.requires_soc_review is True


def test_builder_soc_approved_always_false() -> None:
    """Builder never marks soc_approved=True — report-only."""
    result = build_mitre_permitted_for_question("q0.q001", use_case_id="auth_failed_login_spike")
    for entry in result.entries:
        assert entry.soc_approved is False, "soc_approved must always be False from deterministic builder"


def test_builder_no_use_case_returns_not_mapped() -> None:
    result = build_mitre_permitted_for_question("q0.q099")
    assert result.overall_status == STATUS_NOT_MAPPED
    assert result.entries == []


def test_builder_unknown_use_case_id_returns_not_mapped() -> None:
    result = build_mitre_permitted_for_question("q0.q001", use_case_id="nonexistent_use_case_xyz")
    assert result.overall_status == STATUS_NOT_MAPPED


def test_builder_query_text_resolves_use_case() -> None:
    result = build_mitre_permitted_for_question("q0.q001", query_text="failed login spike last hour")
    assert result.use_case_id is not None
    assert len(result.entries) > 0


def test_builder_entries_have_in_local_bundle_true_for_valid_ids() -> None:
    result = build_mitre_permitted_for_question("q0.q001", use_case_id="auth_failed_login_spike")
    for entry in result.entries:
        assert entry.in_local_bundle is True


# ---------------------------------------------------------------------------
# SOC review export (P5-9)
# ---------------------------------------------------------------------------


def test_soc_review_record_soc_approved_empty() -> None:
    result = build_mitre_permitted_for_question("q0.q001", use_case_id="auth_failed_login_spike")
    record = build_soc_review_record(result, coverage_id="cov.q001", primary_operation="aggregate_and_rank")
    assert record["soc_approved_mitre_ids"] == [], "SOC-approved IDs must be empty in report-only export"


def test_soc_review_record_has_required_fields() -> None:
    result = build_mitre_permitted_for_question("q0.q001", use_case_id="auth_failed_login_spike")
    record = build_soc_review_record(result)
    for key in ("question_ref", "candidate_mitre_ids", "soc_approved_mitre_ids", "status", "entries"):
        assert key in record


def test_soc_review_record_export_note_present() -> None:
    result = build_mitre_permitted_for_question("q0.q001", use_case_id="auth_failed_login_spike")
    record = build_soc_review_record(result)
    assert "report-only" in record["export_note"].lower() or "soc_approved" in record["export_note"]


# ---------------------------------------------------------------------------
# LLM candidate mapper sidecar (P5-10)
# ---------------------------------------------------------------------------


def _llm_provider(raw: str):
    return lambda: raw


def _valid_t1110_llm_output() -> str:
    return json.dumps({
        "primary_techniques": [
            {"technique_id": "T1110", "technique_name": "Brute Force", "confidence": "high", "reason": "repeated auth failures"}
        ],
        "secondary_techniques": [
            {"technique_id": "T1110.001", "technique_name": "Password Guessing", "confidence": "medium", "reason": "sub-technique pattern"}
        ],
        "not_applicable_reason": None,
        "assumptions": ["failed login data available"],
    })


def test_mapper_deterministic_only_when_llm_disabled() -> None:
    """When config gate is off, deterministic runs and LLM is skipped."""
    with patch("app.config.settings.ai_soc_llm_mitre_candidate_mapping_enabled", False):
        result = run_mitre_candidate_mapping(
            "q0.q001",
            use_case_id="auth_failed_login_spike",
            llm_raw_output_provider=_llm_provider(_valid_t1110_llm_output()),
        )
    assert result.llm_mitre_candidate_used is False
    assert result.llm_mitre_parse_status == "not_run"
    assert len(result.merged_entries) > 0


def test_mapper_valid_t1110_candidate_accepted() -> None:
    """Valid T1110-family candidate from LLM → status=candidate (not supported)."""
    with (
        patch("app.config.settings.ai_soc_llm_mitre_candidate_mapping_enabled", True),
        patch("app.config.settings.ai_soc_llm_enabled", True),
        patch("app.config.settings.ai_soc_llm_mode", "mock"),
    ):
        result = run_mitre_candidate_mapping(
            "q0.q001",
            use_case_id="auth_failed_login_spike",
            llm_raw_output_provider=_llm_provider(_valid_t1110_llm_output()),
        )
    assert result.llm_mitre_candidate_used is True
    assert result.llm_mitre_parse_status in ("valid", "repaired")
    assert result.llm_mitre_candidate_validation in ("valid", "unknown_id", "weak_rationale")
    # LLM output never produces supported
    for entry in result.llm_candidate_entries:
        assert entry["status"] != STATUS_SUPPORTED, "LLM output must never produce status=supported"
    # SOC review required
    assert result.requires_soc_review is True


def test_mapper_markdown_wrapped_json_repaired() -> None:
    """Markdown-fenced JSON → parse_repaired=True; content still accepted."""
    wrapped = "```json\n" + _valid_t1110_llm_output() + "\n```"
    with (
        patch("app.config.settings.ai_soc_llm_mitre_candidate_mapping_enabled", True),
        patch("app.config.settings.ai_soc_llm_enabled", True),
        patch("app.config.settings.ai_soc_llm_mode", "mock"),
    ):
        result = run_mitre_candidate_mapping(
            "q0.q001",
            use_case_id="auth_failed_login_spike",
            llm_raw_output_provider=_llm_provider(wrapped),
        )
    assert result.llm_mitre_parse_repaired is True
    assert result.llm_mitre_parse_status == "repaired"
    assert result.llm_mitre_candidate_used is True


def test_mapper_unknown_id_downgraded_to_needs_review() -> None:
    """T9999 (not in bundle) → status=needs_review, validation=unknown_id."""
    unknown_output = json.dumps({
        "primary_techniques": [
            {"technique_id": "T9999", "technique_name": "Invented Technique", "confidence": "high", "reason": "made up"}
        ],
        "secondary_techniques": [],
        "not_applicable_reason": None,
        "assumptions": [],
    })
    with (
        patch("app.config.settings.ai_soc_llm_mitre_candidate_mapping_enabled", True),
        patch("app.config.settings.ai_soc_llm_enabled", True),
        patch("app.config.settings.ai_soc_llm_mode", "mock"),
    ):
        result = run_mitre_candidate_mapping(
            "q0.q001",
            use_case_id="auth_failed_login_spike",
            llm_raw_output_provider=_llm_provider(unknown_output),
        )
    assert result.llm_mitre_candidate_used is True
    assert result.llm_mitre_candidate_validation == "unknown_id"
    unknown_entries = [e for e in result.llm_candidate_entries if e["technique_id"] == "T9999"]
    assert len(unknown_entries) == 1
    assert unknown_entries[0]["status"] == STATUS_NEEDS_REVIEW
    assert unknown_entries[0]["in_local_bundle"] is False


def test_mapper_weak_rationale_secondary_downgraded() -> None:
    """Secondary technique with confidence=low → status=needs_review."""
    weak_output = json.dumps({
        "primary_techniques": [
            {"technique_id": "T1110", "technique_name": "Brute Force", "confidence": "high", "reason": "clear pattern"}
        ],
        "secondary_techniques": [
            {"technique_id": "T1078", "technique_name": "Valid Accounts", "confidence": "low", "reason": "vague"}
        ],
        "not_applicable_reason": None,
        "assumptions": [],
    })
    with (
        patch("app.config.settings.ai_soc_llm_mitre_candidate_mapping_enabled", True),
        patch("app.config.settings.ai_soc_llm_enabled", True),
        patch("app.config.settings.ai_soc_llm_mode", "mock"),
    ):
        result = run_mitre_candidate_mapping(
            "q0.q001",
            use_case_id="auth_failed_login_spike",
            llm_raw_output_provider=_llm_provider(weak_output),
        )
    weak_entries = [e for e in result.llm_candidate_entries if e["technique_id"] == "T1078" and not e["is_primary"]]
    assert len(weak_entries) == 1, "T1078 secondary with confidence=low must appear in llm_candidate_entries"
    assert weak_entries[0]["status"] == STATUS_NEEDS_REVIEW, "low-confidence secondary must be downgraded to needs_review"
    assert result.llm_mitre_candidate_validation in ("weak_rationale", "valid")


def test_mapper_parse_failure_recorded_deterministic_survives() -> None:
    """Unrecoverable JSON → parse_failed recorded; deterministic entries survive."""
    broken = "this is not json at all {{"
    with (
        patch("app.config.settings.ai_soc_llm_mitre_candidate_mapping_enabled", True),
        patch("app.config.settings.ai_soc_llm_enabled", True),
        patch("app.config.settings.ai_soc_llm_mode", "mock"),
    ):
        result = run_mitre_candidate_mapping(
            "q0.q001",
            use_case_id="auth_failed_login_spike",
            llm_raw_output_provider=_llm_provider(broken),
        )
    assert result.llm_mitre_parse_status == "failed"
    assert result.llm_mitre_candidate_validation == "parse_failed"
    assert result.llm_mitre_candidate_used is False
    # Deterministic entries still present in merged
    deterministic_ids = {e.technique_id for e in result.deterministic_entries}
    merged_ids = {e.get("technique_id") for e in result.merged_entries}
    assert deterministic_ids <= merged_ids


def test_mapper_not_mapped_when_no_use_case() -> None:
    """No use-case match → not_mapped overall; no entries."""
    with patch("app.config.settings.ai_soc_llm_mitre_candidate_mapping_enabled", False):
        result = run_mitre_candidate_mapping("q0.q099")
    assert result.overall_status == STATUS_NOT_MAPPED
    assert result.merged_entries == []


def test_mapper_no_provider_callable_skips_llm() -> None:
    """None provider → LLM not called even when config gate is on."""
    with patch("app.config.settings.ai_soc_llm_mitre_candidate_mapping_enabled", True):
        result = run_mitre_candidate_mapping(
            "q0.q001",
            use_case_id="auth_failed_login_spike",
            llm_raw_output_provider=None,
        )
    assert result.llm_mitre_candidate_used is False
    assert result.llm_mitre_parse_status == "not_run"


# ---------------------------------------------------------------------------
# Authority boundary — hard constraints
# ---------------------------------------------------------------------------


def test_llm_output_never_produces_supported_status() -> None:
    """No matter what LLM returns for a technique, status must not be supported."""
    output = json.dumps({
        "primary_techniques": [
            {"technique_id": "T1110.001", "technique_name": "Password Guessing", "confidence": "high", "reason": "repeated failures"}
        ],
        "secondary_techniques": [],
        "not_applicable_reason": None,
        "assumptions": [],
    })
    with (
        patch("app.config.settings.ai_soc_llm_mitre_candidate_mapping_enabled", True),
        patch("app.config.settings.ai_soc_llm_enabled", True),
        patch("app.config.settings.ai_soc_llm_mode", "mock"),
    ):
        result = run_mitre_candidate_mapping(
            "q0.q001",
            use_case_id="auth_failed_login_spike",
            llm_raw_output_provider=_llm_provider(output),
        )
    for entry in result.llm_candidate_entries:
        assert entry["status"] != STATUS_SUPPORTED, (
            f"LLM entry {entry['technique_id']} must not have status=supported"
        )


def test_llm_disabled_mode_blocks_mapper_even_with_flag_on() -> None:
    """ai_soc_llm_mode=disabled must block LLM even when mapping flag=True and provider given."""
    with (
        patch("app.config.settings.ai_soc_llm_mitre_candidate_mapping_enabled", True),
        patch("app.config.settings.ai_soc_llm_enabled", True),
        patch("app.config.settings.ai_soc_llm_mode", "disabled"),
    ):
        result = run_mitre_candidate_mapping(
            "q0.q001",
            use_case_id="auth_failed_login_spike",
            llm_raw_output_provider=_llm_provider(_valid_t1110_llm_output()),
        )
    assert result.llm_mitre_candidate_used is False
    assert result.llm_mitre_parse_status == "not_run"


def test_all_entries_require_soc_review() -> None:
    """requires_soc_review must always be True in builder and mapper output."""
    result = build_mitre_permitted_for_question("q0.q001", use_case_id="auth_success_after_failure")
    for entry in result.entries:
        if entry.status != STATUS_SUPPORTED:
            assert entry.requires_soc_review is True


# ---------------------------------------------------------------------------
# Captured live Foundation-sec-8B-Instruct payload (real model output)
# ---------------------------------------------------------------------------

# Verbatim raw output from Foundation-sec-8B-Instruct (HuggingFace) for the
# question "Which users had excessive failed login attempts in the last hour?".
# Note: the model returned a valid JSON object followed by a prose paragraph,
# and hallucinated T1110.002 ("Password Cracking" in real ATT&CK) labelled as
# "Password Guessing" at high confidence. This fixture locks the adapter's
# behaviour against a REAL model error, not a synthetic one.
CAPTURED_FOUNDATION_SEC_INSTRUCT_OUTPUT = """{
  "primary_techniques": [
    {
      "technique_id": "T1110",
      "technique_name": "Brute Force",
      "confidence": "high",
      "reason": "Directly related to the question as it involves attempting multiple login attempts to gain access."
    }
  ],
  "secondary_techniques": [
    {
      "technique_id": "T1110.002",
      "technique_name": "Password Guessing",
      "confidence": "high",
      "reason": "A common method used in brute force attacks, especially when targeting valid accounts."
    },
    {
      "technique_id": "T1110.003",
      "technique_name": "Password Spraying",
      "confidence": "high",
      "reason": "A specific type of brute force attack where the attacker tries a small number of common passwords against many accounts."
    }
  ],
  "not_applicable_reason": null,
  "assumptions": []
}This JSON output maps the SOC analyst question to relevant MITRE ATT&CK techniques that are associated with brute force attacks."""


def _run_captured_payload():
    with (
        patch("app.config.settings.ai_soc_llm_mitre_candidate_mapping_enabled", True),
        patch("app.config.settings.ai_soc_llm_enabled", True),
        patch("app.config.settings.ai_soc_llm_mode", "mock"),
    ):
        return run_mitre_candidate_mapping(
            "q0.q001",
            use_case_id="auth_failed_login_spike",
            llm_raw_output_provider=_llm_provider(CAPTURED_FOUNDATION_SEC_INSTRUCT_OUTPUT),
        )


def test_captured_payload_parses_despite_trailing_prose() -> None:
    """Real model appended prose after the JSON object; extractor must still parse."""
    result = _run_captured_payload()
    assert result.llm_mitre_candidate_used is True
    assert result.llm_mitre_parse_status in ("valid", "repaired")
    ids = {e["technique_id"] for e in result.llm_candidate_entries}
    assert ids == {"T1110", "T1110.002", "T1110.003"}


def test_captured_payload_t1110_002_in_bundle_post_g5_promotion() -> None:
    """T1110.002 (Brute Force: Password Cracking) was promoted into the local bundle
    by G5, so it is now an in-bundle candidate, not an unknown_id downgrade.

    The unknown-id catch path stays covered by ``test_unknown_id_not_in_bundle`` (T9999)
    and ``test_mapper_unknown_id_downgraded_to_needs_review``.
    """
    result = _run_captured_payload()
    entry = next(e for e in result.llm_candidate_entries if e["technique_id"] == "T1110.002")
    assert entry["in_local_bundle"] is True
    assert entry["status"] == STATUS_CANDIDATE  # in-bundle LLM candidate, never supported


def test_captured_payload_valid_ids_capped_at_candidate() -> None:
    """In-bundle T1110 / T1110.003 must be candidate, never supported from LLM."""
    result = _run_captured_payload()
    for tid in ("T1110", "T1110.003"):
        entry = next(e for e in result.llm_candidate_entries if e["technique_id"] == tid)
        assert entry["in_local_bundle"] is True
        assert entry["status"] == STATUS_CANDIDATE


def test_captured_payload_name_authoritative_from_bundle() -> None:
    """T1110.003 model name happens to match; T1110 name comes from bundle, not LLM trust."""
    result = _run_captured_payload()
    t1110 = next(e for e in result.llm_candidate_entries if e["technique_id"] == "T1110")
    assert t1110["technique_name"] == "Brute Force"  # bundle canonical
    assert t1110["tactic"] == "Credential Access"  # filled from bundle, not "unknown"


def test_captured_payload_no_supported_anywhere() -> None:
    """Authority boundary: no LLM-derived entry reaches supported."""
    result = _run_captured_payload()
    for entry in result.llm_candidate_entries:
        assert entry["status"] != STATUS_SUPPORTED
    assert result.requires_soc_review is True


def test_name_override_flagged_when_valid_id_wrong_name() -> None:
    """Valid in-bundle ID + wrong LLM name → name overridden from bundle + mismatch note.

    Guards the future case where the bundle expands to include T1110.002: a wrong
    name paired with a now-valid ID must still be corrected, not silently trusted.
    """
    wrong_name = json.dumps({
        "primary_techniques": [
            {"technique_id": "T1110.001", "technique_name": "Totally Wrong Name", "confidence": "high", "reason": "x"}
        ],
        "secondary_techniques": [],
        "not_applicable_reason": None,
        "assumptions": [],
    })
    with (
        patch("app.config.settings.ai_soc_llm_mitre_candidate_mapping_enabled", True),
        patch("app.config.settings.ai_soc_llm_enabled", True),
        patch("app.config.settings.ai_soc_llm_mode", "mock"),
    ):
        result = run_mitre_candidate_mapping(
            "q0.q001",
            use_case_id="auth_failed_login_spike",
            llm_raw_output_provider=_llm_provider(wrong_name),
        )
    entry = next(e for e in result.llm_candidate_entries if e["technique_id"] == "T1110.001")
    assert entry["technique_name"] == "Password Guessing"  # bundle canonical, not LLM
    assert entry["llm_supplied_name"] == "Totally Wrong Name"
    assert any(n.startswith("llm_name_overridden:") for n in entry["notes"])
