"""Regression: out-of-registry security-log aggregation must not demote to alert_summary/rag_only."""

from __future__ import annotations

import pytest

from app.chat.contracts.llm_intent_advisory import LLMIntentAdvisory
from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.config import settings
from app.query_understanding.parser import understand_query
from app.routing.route_adjudication import adjudicate_route

_FIREWALL_COORDINATED_QUERY = (
    "We have more than 5,000 firewall blocks in the last hour and a successful breach "
    "on an internal server account — summarize top offenders and assess whether this "
    "looks coordinated."
)


@pytest.fixture(autouse=True)
def _enable_control_plane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_guided_hybrid_investigation_enabled", True)


def _pipeline(
    query: str,
    *,
    deterministic_route: str = "guided_investigation",
    llm_advisory: LLMIntentAdvisory | None = None,
):
    understanding = understand_query(query)
    qti = build_query_to_intent(
        query=query,
        query_understanding=understanding,
        routed_skill=deterministic_route,
        llm_intent_advisory=llm_advisory,
    )
    intent = qti.intent_classification
    plan = plan_evidence(
        intent_classification=intent,
        query_to_intent=qti.model_dump(),
        query_understanding=understanding,
        routed={"skill": deterministic_route},
    )
    adjudication = adjudicate_route(
        deterministic_route=deterministic_route,
        evidence_plan=plan,
        intent_classification=intent,
        query_understanding=understanding,
        query_to_intent=qti.model_dump(),
        message=query,
    )
    return understanding, qti, intent, plan, adjudication


def test_firewall_coordinated_query_preserves_guided_investigation() -> None:
    _, qti, intent, plan, adjudication = _pipeline(_FIREWALL_COORDINATED_QUERY)
    signals = qti.query_signals
    assert signals.get("security_log_aggregation_investigation") is True
    assert signals.get("firewall_block_or_deny") is True
    assert signals.get("top_offenders_aggregation") is True
    assert intent.intent_family == "guided_investigation"
    assert intent.requested_output_type == "INVESTIGATION"
    assert adjudication.final_route == "guided_investigation"
    assert plan.answer_mode == "guided_investigation"
    assert "alert_summary_no_spl" not in (plan.reasons or [])
    assert plan.needs_spl is False
    assert plan.spl_allowed is False
    assert plan.mcp_allowed is False
    assert plan.freeform_spl_execution_allowed is False
    assert plan.requires_hil is True


def test_llm_timeout_does_not_demote_firewall_coordinated_query() -> None:
    timed_out_advisory = LLMIntentAdvisory(
        adjudication_status="rejected",
        dropped_reasons=["llm_timed_out"],
        intent_family_candidate="alert_summary",
        primary_intent_candidate="alert_summary",
        requested_output_type_candidate="SUMMARY",
    )
    _, _, intent, plan, adjudication = _pipeline(
        _FIREWALL_COORDINATED_QUERY,
        llm_advisory=timed_out_advisory,
    )
    assert intent.intent_family == "guided_investigation"
    assert adjudication.final_route == "guided_investigation"
    assert plan.answer_mode == "guided_investigation"
    assert "alert_summary_no_spl" not in (plan.reasons or [])


def test_summarize_known_alert_still_alert_summary() -> None:
    query = "Summarize alert ALT-1234-5678 for shift handoff."
    _, _, intent, plan, adjudication = _pipeline(query, deterministic_route="alert_summary")
    assert intent.intent_family == "alert_summary"
    assert adjudication.final_route == "alert_summary"
    assert plan.answer_mode == "rag_only"
    assert "alert_summary_no_spl" in (plan.reasons or [])


def test_explain_firewall_deny_sop_stays_knowledge_recall() -> None:
    query = "Explain the firewall deny spike SOP for perimeter review."
    understanding = understand_query(query)
    qti = build_query_to_intent(query=query, query_understanding=understanding, routed_skill="knowledge_recall")
    intent = qti.intent_classification
    plan = plan_evidence(
        intent_classification=intent,
        query_to_intent=qti.model_dump(),
        query_understanding=understanding,
        routed={"skill": "knowledge_recall"},
    )
    adjudication = adjudicate_route(
        deterministic_route="knowledge_recall",
        evidence_plan=plan,
        intent_classification=intent,
        query_understanding=understanding,
        query_to_intent=qti.model_dump(),
        message=query,
    )
    assert intent.intent_family in {"sop_or_playbook", "knowledge_only", "policy_knowledge"}
    assert adjudication.final_route == "knowledge_recall"
    assert plan.answer_mode in {"rag_only", "knowledge_only", "clarification"}


def test_block_ip_stays_human_review() -> None:
    query = "Block this IP 203.0.113.50 on the perimeter firewall now."
    _, _, intent, _, adjudication = _pipeline(query, deterministic_route="knowledge_recall")
    assert intent.intent_family == "clarification_required"
    assert intent.primary_intent == "human_review"
    assert intent.requires_clarification is True
    assert adjudication.final_route == "knowledge_recall"
