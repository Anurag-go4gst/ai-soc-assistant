from __future__ import annotations

import pytest

from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.config import settings
from app.query_understanding.parser import understand_query
from app.routing.llm_plan_validator import (
    build_advisory_plan_from_context,
    should_validate_llm_advisory_plan,
    validate_llm_advisory_plan,
)


def _intent_and_evidence(query: str) -> tuple[dict, dict]:
    qu = understand_query(query)
    q2i = build_query_to_intent(query=query, query_understanding=qu)
    intent = q2i.intent_classification.model_dump()
    evidence = plan_evidence(intent, query_to_intent=q2i.model_dump()).model_dump()
    return intent, evidence


def test_deterministic_only_skips_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "routing_mode", "deterministic_only")
    assert should_validate_llm_advisory_plan() is False
    result = validate_llm_advisory_plan(
        {"skill": "attack_discovery", "needs_spl": True},
        routing_mode="deterministic_only",
    )
    assert result.status == "skipped"


def test_rejects_needs_spl_without_mcp_for_live_investigation() -> None:
    intent, evidence = _intent_and_evidence(
        "Find accounts failing login in the last 24 hours, exclude service accounts"
    )
    advisory = {"skill": "attack_discovery", "needs_spl": True, "needs_mcp": False}
    result = validate_llm_advisory_plan(
        advisory,
        evidence_plan=evidence,
        intent_classification=intent,
        routing_mode="llm_assisted_semantic",
    )
    assert result.status == "rejected"
    assert "needs_spl_without_mcp_for_live_investigation" in result.reasons


def test_rejects_unknown_skill() -> None:
    result = validate_llm_advisory_plan(
        {"skill": "Security Incident Response", "needs_spl": False, "needs_mcp": False},
        routing_mode="llm_assisted_semantic",
    )
    assert result.status == "rejected"
    assert any("unknown_skill_rejected" in item for item in result.reasons)


def test_rejects_mitre_visibility_during_clarification_intent() -> None:
    intent, evidence = _intent_and_evidence("Map this to MITRE")
    result = validate_llm_advisory_plan(
        {
            "skill": "knowledge_recall",
            "needs_spl": False,
            "needs_mcp": False,
            "mitre_answer_visible": True,
        },
        evidence_plan=evidence,
        intent_classification=intent,
        routing_mode="llm_assisted_semantic",
    )
    assert result.status == "rejected"
    assert "mitre_visibility_conflicts_with_clarification_intent" in result.reasons


def test_accepts_corrected_advisory_plan_with_normalized_skill() -> None:
    intent, evidence = _intent_and_evidence("Generate SPL for failed logins")
    result = validate_llm_advisory_plan(
        {
            "skill": "spl_generation",
            "needs_spl": True,
            "needs_mcp": False,
            "mcp_execution_allowed": False,
        },
        evidence_plan=evidence,
        intent_classification=intent,
        routing_mode="llm_assisted_semantic",
    )
    assert result.status == "accepted"
    assert result.mcp_execution_allowed is False


def test_rejects_needs_mcp_when_evidence_plan_blocks_mcp() -> None:
    intent, evidence = _intent_and_evidence(
        "What is the escalation policy for repeated failed login alerts?"
    )
    result = validate_llm_advisory_plan(
        {"skill": "knowledge_recall", "needs_spl": False, "needs_mcp": True},
        evidence_plan=evidence,
        intent_classification=intent,
        routing_mode="llm_assisted_semantic",
    )
    assert result.status == "rejected"
    assert "needs_mcp_conflicts_with_evidence_plan_mcp_allowed_false" in result.reasons


def test_build_advisory_plan_from_comparison_llm_shadow() -> None:
    comparison = {
        "llm_shadow": {
            "skill": "attack_discovery",
            "confidence": 0.9,
            "metadata": {"needs_spl": True, "needs_mcp": True},
        }
    }
    plan = build_advisory_plan_from_context(comparison=comparison)
    assert plan["skill"] == "attack_discovery"
    assert plan["needs_spl"] is True
    assert plan["needs_mcp"] is True
