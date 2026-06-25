"""Unit tests for the cross-stream FinalEvidenceGate (Phase 1).

Covers the 8 classification/permission cases from plan Phase 1.4, plus
collected-evidence-count parity with the documented raw-input rules and the
review-only SPL invariant (count==0, no results table).
"""

from __future__ import annotations

from typing import Any

from app.evidence.final_evidence_gate import (
    EvidenceClass,
    GatedEvidenceState,
    apply_final_evidence_gate,
    classify_source_record,
    count_collected_evidence,
)


def _record(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "evidence_id": "ev_test",
        "trace_id": "t1",
        "source_type": "splunk_mcp",
        "source_name": "mcp_splunk",
        "collection_status": "collected",
        "result_count": 0,
    }
    base.update(overrides)
    return base


def _gate(**overrides: Any) -> GatedEvidenceState:
    kwargs: dict[str, Any] = {
        "source_evidence": [],
        "execution": {"status": "skipped"},
        "soc_kb_retrieval": None,
        "mcp_evidence": None,
        "evidence_plan": {},
        "intent": {},
        "spl_validation": None,
    }
    kwargs.update(overrides)
    return apply_final_evidence_gate(**kwargs)


# --------------------------------------------------------------------------
# Classification cases (plan Phase 1.4)
# --------------------------------------------------------------------------


def test_spl_draft_record_is_review_artifact() -> None:
    # SPL drafts/validations are passed as candidate_spl/spl_validation, not as
    # source_evidence records. A skipped manual placeholder is the closest
    # packaged form and must classify as review_artifact.
    record = _record(source_type="manual", source_name="analyst_query", collection_status="skipped")
    assert classify_source_record(record) is EvidenceClass.REVIEW_ARTIFACT


def test_saia_candidate_spl_is_review_artifact() -> None:
    record = _record(
        source_type="splunk_mcp_saia",
        source_name="splunk_ai_assistant",
        collection_status="collected",
        output_type="candidate_spl",
        result_count=1,
    )
    assert classify_source_record(record) is EvidenceClass.REVIEW_ARTIFACT


def test_cve_snapshot_is_source_backed_reference() -> None:
    record = _record(source_type="cve_snapshot", source_name="cisa_kev", collection_status="collected", result_count=1)
    assert classify_source_record(record) is EvidenceClass.SOURCE_BACKED_REFERENCE


def test_rag_hit_is_source_backed_reference() -> None:
    record = _record(source_type="rag", source_name="soc_kb", collection_status="collected", result_count=3)
    assert classify_source_record(record) is EvidenceClass.SOURCE_BACKED_REFERENCE


def test_executed_splunk_rows_are_collected_evidence() -> None:
    record = _record(source_type="splunk_mcp", collection_status="collected", result_count=12)
    assert classify_source_record(record) is EvidenceClass.COLLECTED_EVIDENCE


def test_blocked_record_is_review_artifact() -> None:
    record = _record(source_type="splunk_mcp", collection_status="blocked")
    assert classify_source_record(record) is EvidenceClass.REVIEW_ARTIFACT


def test_unknown_record_fails_safe_to_review_artifact() -> None:
    assert classify_source_record({"source_type": "weird"}) is EvidenceClass.REVIEW_ARTIFACT
    assert classify_source_record({}) is EvidenceClass.REVIEW_ARTIFACT


# --------------------------------------------------------------------------
# Permission cases (plan Phase 1.4)
# --------------------------------------------------------------------------


def test_non_executed_path_has_no_table_or_live_language() -> None:
    state = _gate(execution={"status": "skipped"})
    assert state.collected_evidence_count == 0
    assert state.allow_results_table is False
    assert state.allow_live_result_language is False
    assert state.allow_environment_fact_claims is False
    assert state.source_evidence_status == "none"


def test_reference_only_path_has_no_environment_fact_permission() -> None:
    # A retrieved RAG record: source-backed reference, counts toward collected
    # (per documented parity), but execution is not authorized -> no env facts.
    rag_record = _record(source_type="rag", source_name="soc_kb", collection_status="collected", result_count=2)
    state = _gate(
        source_evidence=[rag_record],
        execution={"status": "skipped"},
        soc_kb_retrieval={"retrieval_status": "retrieved"},
    )
    assert state.source_backed_reference_count == 1
    assert state.allow_environment_fact_claims is False
    assert state.allow_results_table is False
    assert state.allow_live_result_language is False
    assert state.environment_evidence_count == 0
    # RAG retrieval counts toward collected per documented run_contract parity.
    assert state.collected_evidence_count == 1


def test_reference_only_path_cannot_enable_severity_or_mitre() -> None:
    rag_record = _record(source_type="rag", source_name="soc_kb", collection_status="collected", result_count=2)
    state = _gate(
        source_evidence=[rag_record],
        execution={"status": "skipped"},
        soc_kb_retrieval={"retrieval_status": "retrieved"},
        evidence_plan={"needs_mitre": True},
        intent={"intent_family": "mitre_explanation"},
        severity_label="P3 Medium",
        mitre_visibility="evidence_supported",
    )
    assert state.collected_evidence_count == 1
    assert state.environment_evidence_count == 0
    assert state.allow_severity_assessment is False
    assert state.severity_label is None
    assert state.allow_mitre_mapping is False
    assert state.mitre_visibility == "candidate"


# --------------------------------------------------------------------------
# collected_evidence_count parity with raw-input rules
# --------------------------------------------------------------------------


def test_count_parity_rag_retrieved() -> None:
    assert (
        count_collected_evidence(
            execution={"status": "skipped"},
            soc_kb_retrieval={"retrieval_status": "retrieved"},
            mcp_evidence=None,
        )
        == 1
    )


def test_count_parity_executed_plus_broaden() -> None:
    execution = {
        "status": "executed",
        "mcp_orchestration": {
            "recipe_id": "broaden_scope_on_empty",
            "calls": [{"outcome": "empty"}, {"outcome": "ok"}],
        },
    }
    # +1 executed, +1 broaden primary empty.
    assert count_collected_evidence(execution=execution, soc_kb_retrieval=None, mcp_evidence=None) == 2


def test_count_parity_mcp_evidence_items() -> None:
    mcp_evidence = [
        {"collection_status": "collected"},
        {"collection_status": "planned"},
        {"collection_status": "collected"},
    ]
    assert count_collected_evidence(execution={}, soc_kb_retrieval=None, mcp_evidence=mcp_evidence) == 2


def test_count_parity_skipped_execution_is_zero() -> None:
    assert count_collected_evidence(execution={"status": "skipped"}, soc_kb_retrieval=None, mcp_evidence=None) == 0


# --------------------------------------------------------------------------
# Review-only SPL invariant + executed-path permissions
# --------------------------------------------------------------------------


def test_review_only_spl_yields_zero_count_and_no_table() -> None:
    # Review-only SPL: a draft + validation exist but nothing executed.
    state = _gate(
        execution={"status": "skipped"},
        candidate_spl={"candidate_spl": "index=main ...", "generation_mode": "template"},
        spl_validation={"approved": True, "normalized_spl": "index=main ..."},
        spl_draft_preview={"draft_spl": "index=main ...", "template_match_strength": "strong"},
        route_live_data_request=True,
    )
    assert state.collected_evidence_count == 0
    assert state.allow_results_table is False
    assert state.allow_live_result_language is False
    # live request without execution must force HIL.
    assert state.effective_hil_required is True


def test_executed_path_with_rows_allows_table_and_env_facts() -> None:
    executed_record = _record(source_type="splunk_mcp", collection_status="collected", result_count=10)
    state = _gate(
        source_evidence=[executed_record],
        execution={"status": "executed"},
    )
    assert state.collected_evidence_count == 1
    assert state.allow_results_table is True
    assert state.allow_live_result_language is True
    assert state.allow_environment_fact_claims is True
    assert state.source_evidence_status == "collected"
    assert state.collected_evidence_refs == ["ev_test"]
    assert executed_record in state.gated_source_evidence


# --------------------------------------------------------------------------
# MITRE / severity permission rules
# --------------------------------------------------------------------------


def test_mitre_mapping_requires_needs_mitre_and_evidence_or_policy() -> None:
    # needs_mitre but no evidence and not policy-backed -> disallowed.
    state = _gate(evidence_plan={"needs_mitre": True})
    assert state.allow_mitre_mapping is False
    # policy-backed unlocks it.
    state2 = _gate(evidence_plan={"needs_mitre": True}, policy_backed=True)
    assert state2.allow_mitre_mapping is True


def test_mitre_evidence_supported_downgraded_when_mapping_disallowed() -> None:
    state = _gate(evidence_plan={"needs_mitre": True}, mitre_visibility="evidence_supported")
    assert state.allow_mitre_mapping is False
    assert state.mitre_visibility == "candidate"


def test_mitre_evidence_supported_kept_when_mapping_allowed() -> None:
    executed_record = _record(source_type="splunk_mcp", collection_status="collected", result_count=4)
    state = _gate(
        source_evidence=[executed_record],
        execution={"status": "executed"},
        evidence_plan={"needs_mitre": True},
        mitre_visibility="evidence_supported",
    )
    assert state.allow_mitre_mapping is True
    assert state.mitre_visibility == "evidence_supported"


def test_severity_disallowed_for_live_request_without_execution() -> None:
    state = _gate(
        intent={"intent_family": "live_investigation"},
        execution={"status": "skipped"},
        route_live_data_request=True,
        severity_label="P2",
    )
    assert state.allow_severity_assessment is False
    assert state.severity_label is None


def test_severity_allowed_when_policy_backed_family() -> None:
    state = _gate(
        intent={"intent_family": "alert_summary"},
        policy_backed=True,
        severity_label="P1",
    )
    assert state.allow_severity_assessment is True
    assert state.severity_label == "P1"


def test_severity_knowledge_family_not_assessed_without_evidence() -> None:
    state = _gate(intent={"intent_family": "knowledge_only"}, severity_label="P3")
    assert state.allow_severity_assessment is False
    assert state.severity_label is None


# --------------------------------------------------------------------------
# to_dict serialization
# --------------------------------------------------------------------------


def test_to_dict_is_json_safe() -> None:
    import json

    state = _gate(execution={"status": "executed"}, source_evidence=[_record(collection_status="collected", result_count=1)])
    payload = state.to_dict()
    # round-trips through json without error
    json.loads(json.dumps(payload))
    assert payload["collected_evidence_count"] == 1
    assert payload["environment_evidence_count"] == 1
    assert payload["allow_results_table"] is True
    # Debug payload carries refs only, never full filtered records.
    assert isinstance(payload["gated_source_evidence_refs"], list)
    assert "gated_source_evidence" not in payload
