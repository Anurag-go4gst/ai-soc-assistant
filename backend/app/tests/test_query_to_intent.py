from __future__ import annotations

import pytest

from app.chat.intent_classifier import build_query_to_intent
from app.query_understanding.parser import understand_query


def _result(query: str):
    qu = understand_query(query)
    return build_query_to_intent(query=query, query_understanding=qu)


def test_escalation_policy_failed_login_is_policy_knowledge_not_live_investigation() -> None:
    result = _result("What is the escalation policy for repeated failed login alerts?")
    intent = result.intent_classification
    assert intent.intent_family == "policy_knowledge"
    assert "policy_citation" in intent.answer_goal
    assert "live_results" not in intent.answer_goal
    assert intent.intent_family != "live_investigation"


def test_find_failed_login_users_last_24h_is_live_investigation() -> None:
    result = _result("Find failed-login users in the last 24 hours")
    intent = result.intent_classification
    assert intent.intent_family == "live_investigation"
    assert "live_results" in intent.answer_goal


def test_generate_spl_for_failed_logins_is_spl_generation_only() -> None:
    result = _result("Generate SPL for failed logins")
    intent = result.intent_classification
    assert intent.intent_family == "spl_generation_only"
    assert "spl_artifact" in intent.answer_goal
    assert result.query_signals["projected_needs_mcp"] is False


def test_generate_spl_and_run_without_scope_is_generation_and_execution() -> None:
    result = _result("Generate SPL for successful login after failures and run")
    intent = result.intent_classification
    assert intent.intent_family == "spl_generation_and_run"
    assert result.query_signals["projected_needs_mcp"] is True


def test_generate_spl_and_run_with_scope_is_generation_and_execution() -> None:
    result = _result(
        "Generate SPL for successful login after failures and run on host APP-01 "
        "in index pgcil_soc sourcetype pgcil:auth for the last 60 minutes"
    )
    intent = result.intent_classification
    assert intent.intent_family == "spl_generation_and_run"
    assert "spl_artifact" in intent.answer_goal
    assert "live_results" in intent.answer_goal
    assert result.query_signals["projected_needs_mcp"] is True


def test_failed_login_plus_analyst_action_is_hybrid() -> None:
    result = _result(
        "Find accounts failing login in the last 24 hours, exclude service accounts, "
        "and tell me what analyst action I should take"
    )
    intent = result.intent_classification
    assert intent.intent_family == "hybrid_investigation_plus_policy"
    assert "live_results" in intent.answer_goal
    assert "analyst_action_guidance" in intent.answer_goal


def test_map_this_to_mitre_requires_clarification() -> None:
    result = _result("Map this to MITRE")
    intent = result.intent_classification
    assert intent.intent_family == "mitre_mapping"
    assert intent.requires_clarification is True


def test_alt_alert_success_after_failure_is_hybrid_alert_review() -> None:
    result = _result(
        "For alert ALT-2024-0891 (failed logins followed by a successful login from the same user "
        "in the last hour), what's the severity, MITRE mapping with status, and a governed SPL "
        "I can review—but not execute"
    )
    intent = result.intent_classification
    assert intent.intent_family == "hybrid_alert_review"
    assert intent.action_mode == "recommend_only"
    assert "severity_assessment" in intent.answer_goal
    assert "mitre_mapping" in intent.answer_goal
    assert "spl_artifact" in intent.answer_goal
    assert result.query_signals["success_after_failure"] is True
    assert result.query_signals["review_only_spl"] is True


def test_explain_mitre_technique_is_mitre_explanation() -> None:
    result = _result("Explain MITRE T1110")
    intent = result.intent_classification
    assert intent.intent_family == "mitre_explanation"
    assert "mitre_explanation" in intent.answer_goal


def test_paraphrased_105_near_or_llm_assist() -> None:
    result = _result("Which users have excessive failed logins?")
    near_or_exact = result.candidate_mappings["match_path"] in {
        "near_105_question",
        "exact_105_question",
        "exact_105_plus_use_case_catalog",
    }
    llm_assist = result.llm_intent_assist_status in {"accepted", "attempted", "corrected"}
    assert near_or_exact or llm_assist


def test_implicit_policy_escalation_without_policy_word() -> None:
    result = _result("When should repeated failed login alerts be escalated?")
    intent = result.intent_classification
    assert intent.intent_family in {"policy_knowledge", "sop_or_playbook"}
    assert "policy" not in result.query_signals["normalized_query"] or intent.intent_family == "policy_knowledge"


def test_investigate_repeated_failed_logins_24h_is_live_investigation() -> None:
    result = _result("Investigate repeated failed logins in the last 24 hours")
    intent = result.intent_classification
    assert intent.intent_family == "live_investigation"
    assert result.query_signals["projected_needs_spl"] is True
    assert result.query_signals["projected_needs_mcp"] is True


def test_dga_domain_definition_is_knowledge_only() -> None:
    result = _result("What is a DGA domain?")
    intent = result.intent_classification
    assert intent.intent_family == "knowledge_only"


def test_investigate_dga_alerts_plus_playbook_is_hybrid_with_rag() -> None:
    result = _result("Investigate DGA alerts and show playbook next steps")
    intent = result.intent_classification
    assert intent.intent_family == "hybrid_investigation_plus_policy"
    assert result.query_signals["projected_needs_rag"] is True


def test_block_ips_from_failed_login_search_requires_hil_recommend_only() -> None:
    result = _result("Block all suspicious IPs from failed login search")
    intent = result.intent_classification
    assert result.query_signals["requires_hil"] is True
    assert result.query_signals["projected_action_mode"] == "recommend_only"
    assert intent.requires_hil is True
    assert intent.action_mode == "recommend_only"
    assert intent.intent_family == "clarification_required"
    assert intent.requires_clarification is True


def test_block_ips_plus_generate_spl_action_precedence_over_spl() -> None:
    result = _result("Block all suspicious IPs from failed login search and generate SPL")
    intent = result.intent_classification
    assert intent.intent_family != "spl_generation_only"
    assert intent.requires_hil is True
    assert intent.action_mode == "recommend_only"
    assert "spl_artifact" not in intent.answer_goal


def test_explain_dga_investigation_steps_is_procedural_knowledge() -> None:
    result = _result("Explain investigation steps for DGA detection")
    intent = result.intent_classification
    assert intent.intent_family == "knowledge_only"
    assert "procedural_steps" in intent.answer_goal
    assert intent.requires_clarification is False
    assert intent.primary_intent == "knowledge_recall"


def test_query_to_intent_envelope_fields_present() -> None:
    result = _result("Generate SPL for failed logins")
    payload = result.model_dump()
    for key in (
        "query_signals",
        "candidate_mappings",
        "intent_classification",
        "intent_conflicts",
        "llm_intent_assist_status",
    ):
        assert key in payload
    intent = payload["intent_classification"]
    for field in (
        "intent_family",
        "primary_intent",
        "secondary_intents",
        "query_type",
        "answer_goal",
        "confidence",
        "confidence_band",
        "requires_clarification",
        "requires_hil",
        "action_mode",
        "reason",
    ):
        assert field in intent


@pytest.mark.parametrize(
    "query",
    [
        "Show me vacation policy accrual rules for new hires",
        "What is the HR vacation policy?",
        "Show me the payroll expense reimbursement policy",
    ],
)
def test_non_soc_show_me_does_not_draft_spl(query: str) -> None:
    result = _result(query)
    intent = result.intent_classification
    assert result.query_signals["non_soc_or_out_of_scope"] is True
    assert intent.intent_family == "clarification_required"
    assert intent.intent_family != "spl_generation_only"
    assert intent.requires_clarification is True
    assert "out of soc scope" in intent.reason.lower()


def test_non_soc_does_not_trigger_explicit_search_spl_path() -> None:
    query = "Show me vacation policy accrual rules for new hires"
    result = _result(query)
    assert result.query_signals["explicit_search_intent"] is True
    assert result.intent_classification.intent_family == "clarification_required"
