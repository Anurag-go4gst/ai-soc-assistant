"""Cross-stream A-H regressions for the FinalEvidenceGate (plan Phase 5).

Each scenario asserts the gate's classification + permission invariants for a
distinct stream shape, locking the "no live execution, but answer sounds
confirmed" class of bugs across SPL, CVE, MITRE, severity, guided
investigation, RAG, GitHub/source-reference, and live-MCP paths.

These exercise the pure gate (``apply_final_evidence_gate``) directly so the
invariants are asserted independent of the full pipeline; the projection into
RunContract is covered by the run_contract tests.
"""

from __future__ import annotations

from typing import Any

from app.evidence.final_evidence_gate import (
    EvidenceClass,
    apply_final_evidence_gate,
    classify_source_record,
)


def _spl_review_record() -> dict[str, Any]:
    return {
        "evidence_id": "ev_spl_review",
        "source_type": "splunk_mcp",
        "source_name": "splunk",
        "collection_status": "skipped",
        "result_count": 0,
    }


def _cve_record() -> dict[str, Any]:
    return {
        "evidence_id": "ev_cve",
        "source_type": "cve_snapshot",
        "source_name": "cve_vendored",
        "collection_status": "collected",
        "result_count": 1,
    }


def _rag_record(status: str = "collected", result_count: int = 1) -> dict[str, Any]:
    return {
        "evidence_id": "ev_rag",
        "source_type": "rag",
        "source_name": "soc_kb",
        "collection_status": status,
        "result_count": result_count,
    }


def _executed_splunk_record() -> dict[str, Any]:
    return {
        "evidence_id": "ev_live",
        "source_type": "splunk_mcp",
        "source_name": "splunk",
        "collection_status": "collected",
        "result_count": 12,
        "provenance": "ai_soc_validated_execution_gate",
    }


# A. Review-only SPL, no execution ------------------------------------------
def test_a_review_only_spl_no_execution() -> None:
    gate = apply_final_evidence_gate(
        source_evidence=[_spl_review_record()],
        execution={"status": "skipped"},
        soc_kb_retrieval=None,
        mcp_evidence=None,
        evidence_plan={"needs_mitre": False, "spl_allowed": True},
        intent={"intent_family": "spl_generation_only", "requires_hil": True},
        spl_validation={"approved": False, "review_required": True},
        route_live_data_request=True,
        effective_hil_required=True,
    )
    assert gate.collected_evidence_count == 0
    assert gate.allow_results_table is False
    assert gate.allow_live_result_language is False
    assert gate.allow_severity_assessment is False  # spl_generation_only + 0 evidence
    assert gate.allow_mitre_mapping is False  # needs_mitre False
    assert gate.source_evidence_status == "metadata_only"
    assert gate.effective_hil_required is True
    assert classify_source_record(_spl_review_record()) is EvidenceClass.REVIEW_ARTIFACT


# B. CVE review-only, no live scan ------------------------------------------
def test_b_cve_review_only_no_scan() -> None:
    gate = apply_final_evidence_gate(
        source_evidence=[_cve_record()],
        execution={"status": "skipped"},
        soc_kb_retrieval=None,
        mcp_evidence=None,
        evidence_plan={"needs_mitre": False},
        intent={"intent_family": "knowledge_only"},
        spl_validation=None,
    )
    assert classify_source_record(_cve_record()) is EvidenceClass.SOURCE_BACKED_REFERENCE
    assert gate.source_backed_reference_count == 1
    assert gate.collected_evidence_count == 0  # CVE snapshot is not collected env evidence
    assert gate.allow_results_table is False
    assert gate.allow_vulnerability_confirmed is False
    assert gate.allow_severity_assessment is False
    assert gate.allow_environment_fact_claims is False


# C. MITRE candidate, no behavior evidence ----------------------------------
def test_c_mitre_candidate_no_behavior_evidence() -> None:
    gate = apply_final_evidence_gate(
        source_evidence=[],
        execution={"status": "skipped"},
        soc_kb_retrieval=None,
        mcp_evidence=None,
        evidence_plan={"needs_mitre": True},
        intent={"intent_family": "mitre_explanation"},
        spl_validation=None,
        mitre_visibility="evidence_supported",
        policy_backed=False,
    )
    assert gate.allow_mitre_mapping is False  # no collected evidence, not policy-backed
    # An incoming "evidence_supported" posture is capped to candidate.
    assert gate.mitre_visibility == "candidate"


# D. severity.allowed=false --------------------------------------------------
def test_d_severity_disallowed_no_default_p3() -> None:
    gate = apply_final_evidence_gate(
        source_evidence=[],
        execution={"status": "skipped"},
        soc_kb_retrieval=None,
        mcp_evidence=None,
        evidence_plan={},
        intent={"intent_family": "guided_investigation"},
        spl_validation=None,
        severity_label="P3",
        policy_backed=False,
    )
    assert gate.allow_severity_assessment is False
    assert gate.severity_label is None  # disallowed severity is gated to None, not P3


# E. Guided investigation, no collected evidence ----------------------------
def test_e_guided_investigation_no_collected_evidence() -> None:
    metadata_record = {
        "evidence_id": "ev_meta",
        "source_type": "manual",
        "source_name": "investigation_plan",
        "collection_status": "skipped",
        "result_count": 0,
    }
    gate = apply_final_evidence_gate(
        source_evidence=[metadata_record],
        execution={"status": "skipped"},
        soc_kb_retrieval=None,
        mcp_evidence=None,
        evidence_plan={"needs_mitre": False},
        intent={"intent_family": "guided_investigation"},
        spl_validation=None,
    )
    assert gate.collected_evidence_count == 0
    assert gate.source_evidence_status == "metadata_only"
    assert gate.allow_live_result_language is False
    assert gate.allow_environment_fact_claims is False


# F. RAG no-match general guidance ------------------------------------------
def test_f_rag_no_match_general_guidance() -> None:
    gate = apply_final_evidence_gate(
        source_evidence=[],
        execution={"status": "skipped"},
        soc_kb_retrieval={"retrieval_status": "no_match"},
        mcp_evidence=None,
        evidence_plan={"needs_mitre": False},
        intent={"intent_family": "knowledge_only"},
        spl_validation=None,
    )
    assert gate.collected_evidence_count == 0  # no_match RAG is not collected
    assert gate.source_backed_reference_count == 0
    assert gate.allow_results_table is False
    assert gate.source_evidence_status == "none"


# G. GitHub / source-reference advisory-only --------------------------------
def test_g_github_source_reference_advisory_only() -> None:
    github_record = {
        "evidence_id": "ev_gh",
        "source_type": "github",
        "source_name": "owner/repo#42",
        "collection_status": "collected",
        "result_count": 1,
    }
    assert classify_source_record(github_record) is EvidenceClass.SOURCE_BACKED_REFERENCE
    gate = apply_final_evidence_gate(
        source_evidence=[github_record],
        execution={"status": "skipped"},
        soc_kb_retrieval=None,
        mcp_evidence=None,
        evidence_plan={"needs_mitre": True},
        intent={"intent_family": "mitre_explanation"},
        spl_validation=None,
        mitre_visibility="evidence_supported",
    )
    assert gate.source_backed_reference_count == 1
    assert gate.collected_evidence_count == 0  # reference, not environment execution
    assert gate.allow_environment_fact_claims is False
    assert gate.allow_severity_assessment is False
    assert gate.allow_mitre_mapping is False  # reference alone cannot confirm MITRE
    assert gate.mitre_visibility == "candidate"


# H. Live MCP executed fixture ----------------------------------------------
def test_h_live_mcp_executed_fixture() -> None:
    gate = apply_final_evidence_gate(
        source_evidence=[_executed_splunk_record()],
        execution={"status": "executed"},
        soc_kb_retrieval=None,
        mcp_evidence=[{"collection_status": "collected"}],
        evidence_plan={"needs_mitre": True},
        intent={"intent_family": "live_investigation"},
        spl_validation=None,
        execution_authorized=True,
        policy_backed=True,
    )
    assert gate.collected_evidence_count > 0
    assert gate.allow_results_table is True  # execution provenance + collected rows
    assert gate.allow_live_result_language is True
    assert gate.allow_environment_fact_claims is True
    assert classify_source_record(_executed_splunk_record()) is EvidenceClass.COLLECTED_EVIDENCE


def test_h_live_results_table_blocked_without_execution_authorization() -> None:
    # Collected packaged rows but execution NOT authorized -> no results table.
    gate = apply_final_evidence_gate(
        source_evidence=[_executed_splunk_record()],
        execution={"status": "skipped"},
        soc_kb_retrieval=None,
        mcp_evidence=None,
        evidence_plan={"needs_mitre": True},
        intent={"intent_family": "live_investigation"},
        spl_validation=None,
        execution_authorized=False,
    )
    assert gate.collected_evidence_count == 0
    assert gate.allow_results_table is False
