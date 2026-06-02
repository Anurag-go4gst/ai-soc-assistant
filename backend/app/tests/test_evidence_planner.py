from __future__ import annotations

from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.query_understanding.parser import understand_query


def _plan(query: str):
    q2i = build_query_to_intent(query=query, query_understanding=understand_query(query))
    return plan_evidence(q2i.intent_classification, q2i.model_dump(), routed={})


def test_policy_knowledge_is_rag_only_with_policy_context_required() -> None:
    plan = _plan("What is the escalation policy for repeated failed login alerts?")
    assert plan.answer_mode == "rag_only"
    assert plan.policy_context_required is True
    assert plan.spl_allowed is False
    assert plan.mcp_allowed is False


def test_live_investigation_allows_spl_and_mcp() -> None:
    plan = _plan("Find failed-login users in the last 24 hours")
    assert plan.answer_mode == "live_investigation"
    assert plan.needs_spl is True
    assert plan.needs_mcp is True
    assert plan.spl_allowed is True
    assert plan.mcp_allowed is True


def test_spl_generation_allows_spl_but_not_mcp() -> None:
    plan = _plan("Generate SPL for failed logins")
    assert plan.needs_spl is True
    assert plan.needs_mcp is False
    assert plan.spl_allowed is True
    assert plan.mcp_allowed is False


def test_hybrid_recommends_policy_context_and_allows_live_path() -> None:
    plan = _plan(
        "Find accounts failing login in the last 24 hours, exclude service accounts, "
        "and tell me what analyst action I should take"
    )
    assert plan.answer_mode == "hybrid"
    assert plan.rag_phase == "pre_mcp"
    assert plan.policy_context_recommended is True
    assert plan.spl_allowed is True
    assert plan.mcp_allowed is True


def test_knowledge_only_uses_optional_rag_without_spl_or_mcp() -> None:
    plan = _plan("What is a DGA domain?")
    assert plan.answer_mode == "rag_only"
    assert plan.policy_context_required is False
    assert plan.policy_context_recommended is True
    assert plan.spl_allowed is False
    assert plan.mcp_allowed is False


def test_mitre_mapping_clarification_skips_spl_and_mcp() -> None:
    plan = _plan("Map this to MITRE")
    assert plan.answer_mode == "clarification"
    assert plan.requires_hil is True
    assert plan.spl_allowed is False
    assert plan.mcp_allowed is False
