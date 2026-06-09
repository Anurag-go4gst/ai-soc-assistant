"""Focused tests for remaining PowerGrid REVIEW rows (no full 50-question eval)."""

from __future__ import annotations

from pathlib import Path

from app.chat.guidance_templates import (
    build_investigation_triage_guidance,
    build_mitre_evidence_threshold_guidance,
    is_mitre_evidence_threshold_query,
    scrub_blocked_context_display_phrasing,
    should_skip_llm_composer,
)
from app.chat.intent_classifier import build_candidate_mappings, classify_intent
from app.chat.query_signals import extract_query_signals
from app.evals.powergrid_soc_question_eval import classify_powergrid_response, load_question_bank
from app.synthesis.governed_answer_composer import validate_composed_prose
from app.chat.contracts.answer_contract import AnswerContract

BANK_PATH = Path(__file__).resolve().parents[3] / "docs" / "evals" / "powergrid_soc_question_bank.json"


def _question(question_id: str) -> dict:
    return next(row for row in load_question_bank(BANK_PATH) if row["question_id"] == question_id)


def test_pg_auth_006_routes_to_guidance_not_clarification() -> None:
    query = _question("pg.auth.006")["question"]
    signals = extract_query_signals(query)
    intent = classify_intent(query=query, signals=signals, candidate_mappings=build_candidate_mappings(None))
    assert signals["investigation_triage_guidance"] is True
    assert signals["use_case_review_guidance"] is True
    assert intent.intent_family == "hybrid_alert_review"
    assert intent.requires_clarification is False


def test_pg_ep_006_routes_to_guidance_not_clarification() -> None:
    query = _question("pg.ep.006")["question"]
    signals = extract_query_signals(query)
    intent = classify_intent(query=query, signals=signals, candidate_mappings=build_candidate_mappings(None))
    assert signals["investigation_triage_guidance"] is True
    assert signals["use_case_review_guidance"] is True
    assert intent.intent_family == "hybrid_alert_review"


def test_pg_auth_006_triage_guidance_passes_eval_classifier() -> None:
    question = _question("pg.auth.006")
    answer = build_investigation_triage_guidance(question["question"])
    record = {
        "answer_text": answer,
        "execution_status": "skipped",
        "execution_executed": False,
        "draft_spl_text": "",
    }
    severity, violations = classify_powergrid_response(question, record, mcp_execution_enabled=False)
    assert severity == "pass"
    assert not violations


def test_pg_ep_006_triage_guidance_passes_eval_classifier() -> None:
    question = _question("pg.ep.006")
    answer = build_investigation_triage_guidance(question["question"])
    record = {
        "answer_text": answer,
        "execution_status": "skipped",
        "execution_executed": False,
        "draft_spl_text": "",
    }
    severity, violations = classify_powergrid_response(question, record, mcp_execution_enabled=False)
    assert severity == "pass"
    assert not violations


def test_pg_dns_009_evidence_threshold_not_conceptual_confirm() -> None:
    query = _question("pg.dns.009")["question"]
    assert is_mitre_evidence_threshold_query(query) is True
    signals = extract_query_signals(query)
    intent = classify_intent(query=query, signals=signals, candidate_mappings=build_candidate_mappings(None))
    assert signals["mitre_evidence_threshold"] is True
    assert signals["use_case_review_guidance"] is True
    assert intent.intent_family == "hybrid_alert_review"
    skip, reason = should_skip_llm_composer(query=query, path_type="generic_soc_guidance", intent_family=intent.intent_family)
    assert skip is True
    assert "threshold" in reason


def test_pg_dns_009_scrubbed_enrichment_actions_pass_eval() -> None:
    question = _question("pg.dns.009")
    answer = build_mitre_evidence_threshold_guidance(question["question"])
    answer += "\n" + scrub_blocked_context_display_phrasing(
        "P2 — Escalate from candidate to evidence-supported only when multiple signals align."
    )
    record = {
        "answer_text": answer,
        "execution_status": "skipped",
        "execution_executed": False,
        "mitre_evidence_supported_techniques": [],
        "mitre_branch_evidence_supported": [],
        "draft_spl_text": "",
    }
    severity, violations = classify_powergrid_response(question, record, mcp_execution_enabled=False)
    assert severity == "pass"
    assert not any(v["category"] == "evidence_supported_mitre_with_blocked_context" for v in violations)


def test_pg_sop_001_routes_to_sop_playbook_not_spl() -> None:
    query = _question("pg.sop.001")["question"]
    signals = extract_query_signals(query)
    intent = classify_intent(query=query, signals=signals, candidate_mappings=build_candidate_mappings(None))
    assert signals["sop_show_request"] is True
    assert signals["spl_generation"] is False
    assert intent.intent_family == "sop_or_playbook"
    skip, _ = should_skip_llm_composer(query=query, path_type="rag_only", intent_family=intent.intent_family)
    assert skip is True


def test_pg_sop_001_composer_blocks_evidence_supported_negation() -> None:
    contract = AnswerContract(
        evidence_supported_mitre=[],
        candidate_mitre=["T1078"],
        execution_status_label="blocked_approval_required",
        spl_status="not_required",
    )
    passed, reason = validate_composed_prose(
        "We must not conclude any MITRE technique as evidence-supported without further review.",
        contract,
    )
    assert passed is False
    assert reason is not None
    assert "evidence-supported" in reason.lower()


def test_explicit_search_intent_preserved_for_log_search_prompt() -> None:
    query = "Search firewall logs for denied outbound connections in the last 24 hours."
    signals = extract_query_signals(query)
    assert signals["explicit_search_intent"] is True
    assert signals["spl_generation"] is True
