"""T5.1 — Tier-D answer-quality checks: one passing and one failing case per check."""

from __future__ import annotations

from typing import Any

from app.quality.answer_quality_checks import run_answer_quality_checks


def _payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "message": "Review-only investigation prepared.",
        "severity_decision": {"severity_label": "P3 Medium"},
        "candidate_spl": {"candidate_spl": "search index=x", "execution_eligible": False},
        "execution": {"status": "skipped"},
        "answer_contract": {
            "mitre_technique_ids": ["T1110"],
            "candidate_mitre": ["T1110"],
            "evidence_supported_mitre": [],
        },
        "mitre_mappings": [],
        "analyst_response": {
            "render_sections": {"limitations": True, "analyst_action_guidance": True},
            "limitations": ["Telemetry alone does not establish validity."],
            "recommended_actions": ["P2 — Correlate failures and successes for the user."],
            "severity_rationale": "Severity P3 by default policy; no escalation evidence.",
            "mitre_status_summary": "T1110 is a candidate only.",
            "execution_status_label": "Review only — not executed",
            "spl_draft_preview": {"draft_spl": "search ...", "draft_status": "draft_preview_not_governed"},
        },
    }
    base.update(overrides)
    return base


def _result(payload: dict[str, Any], check_id: str):
    results = {item.check_id: item for item in run_answer_quality_checks(payload)}
    return results[check_id]


def test_all_checks_pass_on_clean_answer() -> None:
    assert all(item.passed for item in run_answer_quality_checks(_payload()))


def test_grounding_passes_with_action_priority_prefixes() -> None:
    # "P2 — ..." inside recommended_actions is a priority label, not a severity claim.
    assert _result(_payload(), "grounding_no_orphan_claims").passed


def test_grounding_fails_on_severity_mismatch_in_prose() -> None:
    payload = _payload()
    payload["analyst_response"]["severity_rationale"] = "This is a P1 incident."
    assert not _result(payload, "grounding_no_orphan_claims").passed


def test_grounding_allows_why_not_higher_severity_in_rationale() -> None:
    payload = _payload()
    payload["analyst_response"]["severity_rationale"] = (
        "Why not higher: P1 requires confirmed success evidence."
    )
    assert _result(payload, "grounding_no_orphan_claims").passed


def test_grounding_fails_on_orphan_mitre_id() -> None:
    payload = _payload()
    payload["analyst_response"]["mitre_status_summary"] = "Maps to T1566.001."
    assert not _result(payload, "grounding_no_orphan_claims").passed


def test_completeness_fails_on_enabled_section_without_content() -> None:
    payload = _payload()
    payload["analyst_response"]["limitations"] = []
    assert not _result(payload, "completeness_sections").passed


def test_completeness_accepts_review_notice_as_action_guidance() -> None:
    payload = _payload()
    payload["analyst_response"]["recommended_actions"] = []
    payload["analyst_response"]["review_notice"] = "No containment action was performed."
    assert _result(payload, "completeness_sections").passed


def test_actionability_fails_when_high_severity_has_no_actions() -> None:
    payload = _payload(severity_decision={"severity_label": "P1 Critical"})
    payload["analyst_response"]["recommended_actions"] = []
    payload["analyst_response"]["review_notice"] = "covers guidance section"
    assert not _result(payload, "actionability_priorities").passed


def test_actionability_passes_with_actions_present() -> None:
    payload = _payload(severity_decision={"severity_label": "P1 Critical"})
    assert _result(payload, "actionability_priorities").passed


def test_honesty_fails_on_executed_claim_without_execution() -> None:
    payload = _payload()
    payload["analyst_response"]["evidence_summary"] = "The SPL was executed in Splunk."
    assert not _result(payload, "honesty_limitations").passed


def test_honesty_fails_on_execution_eligible_true() -> None:
    payload = _payload()
    payload["candidate_spl"]["execution_eligible"] = True
    assert not _result(payload, "honesty_limitations").passed


def test_honesty_fails_when_spl_artifact_has_no_disclosure() -> None:
    payload = _payload()
    payload["analyst_response"]["limitations"] = []
    payload["analyst_response"]["execution_status_label"] = None
    payload["analyst_response"]["spl_draft_preview"] = {}
    payload["analyst_response"]["render_sections"] = {}
    assert not _result(payload, "honesty_limitations").passed


def test_honesty_vacuous_for_pure_knowledge_answer() -> None:
    payload = _payload()
    payload["candidate_spl"] = {}
    payload["analyst_response"].update(
        {"spl_draft_preview": {}, "limitations": [], "execution_status_label": None, "render_sections": {}}
    )
    assert _result(payload, "honesty_limitations").passed


def test_forbidden_fails_on_unnegated_compromise_claim() -> None:
    payload = _payload()
    payload["analyst_response"]["evidence_summary"] = "Account compromise confirmed."
    assert not _result(payload, "no_forbidden_claims").passed


def test_forbidden_passes_on_negated_compromise_framing() -> None:
    payload = _payload()
    payload["analyst_response"]["evidence_summary"] = (
        "Account compromise is not confirmed; candidate only."
    )
    assert _result(payload, "no_forbidden_claims").passed


def test_forbidden_fails_on_github_marker() -> None:
    payload = _payload()
    payload["analyst_response"]["sop_guidance"] = "See github.com/example for steps."
    assert not _result(payload, "no_forbidden_claims").passed


def test_forbidden_fails_on_unbacked_evidence_supported_claim() -> None:
    payload = _payload()
    payload["analyst_response"]["mitre_status_summary"] = "T1110 is evidence-supported."
    assert not _result(payload, "no_forbidden_claims").passed


def test_forbidden_passes_on_instructional_evidence_supported_checklist_line() -> None:
    payload = _payload()
    payload["analyst_response"]["direct_answer_summary"] = (
        "Governed SPL draft for review only.\n\n"
        "SOC review checklist:\n"
        "- Confirm threshold evidence before labeling brute-force activity evidence-supported."
    )
    assert _result(payload, "no_forbidden_claims").passed


def test_forbidden_allows_instructional_evidence_supported_in_steps() -> None:
    payload = _payload()
    payload["analyst_response"]["investigation_steps"] = [
        "Confirm threshold evidence before labeling brute-force activity evidence-supported."
    ]
    assert _result(payload, "no_forbidden_claims").passed


def test_forbidden_allows_instructional_phrasing_in_direct_summary() -> None:
    payload = _payload()
    payload["analyst_response"]["direct_answer_summary"] = (
        "Review checklist:\n"
        "- Confirm threshold evidence before labeling brute-force activity evidence-supported."
    )
    assert _result(payload, "no_forbidden_claims").passed
