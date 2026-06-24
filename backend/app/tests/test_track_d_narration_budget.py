"""Track D: weak-case composition eligibility and deterministic cross-skill stitch."""

from __future__ import annotations

from app.chat.contracts.answer_contract import AnswerContract
from app.chat.intent_classifier import build_query_to_intent
from app.chat.query_signals import is_cross_skill_investigation_query, is_github_investigation_query
from app.llm.turn_llm_budget import TurnLlmBudget
from app.query_understanding.parser import understand_query
from app.synthesis.composition_confidence import qualifies_for_weak_case_composition
from app.synthesis.deterministic_prose_stitch import (
    apply_deterministic_prose_enhancements,
    build_cross_skill_stitch_block,
)
from app.synthesis.governed_answer_composer import composer_is_enabled

CROSS_SKILL_QUERY = (
    "Cross-skill check: combine CVE context, MITRE candidate mapping, and GitHub commit "
    "timeline into one review-only investigation plan."
)


def test_alert_summary_qualifies_for_weak_case_composition() -> None:
    contract = AnswerContract(intent_family="alert_summary", answer_mode="hybrid_alert_review")
    assert qualifies_for_weak_case_composition(contract, intent_family="alert_summary") is True


def test_github_investigation_qualifies_for_weak_case_composition() -> None:
    contract = AnswerContract(intent_family="github_investigation", answer_mode="guided_investigation")
    assert qualifies_for_weak_case_composition(contract, intent_family="github_investigation") is True


def test_cross_skill_stitch_has_three_legs() -> None:
    block = build_cross_skill_stitch_block(CROSS_SKILL_QUERY)
    lowered = block.lower()
    assert "cve leg" in lowered
    assert "mitre leg" in lowered
    assert "github leg" in lowered
    assert "no splunk search or mcp execution was performed" in lowered


def test_cross_skill_intent_beats_github_only() -> None:
    understanding = understand_query(CROSS_SKILL_QUERY)
    qti = build_query_to_intent(query=CROSS_SKILL_QUERY, query_understanding=understanding)
    assert qti.intent_classification.primary_intent == "cross_skill_investigation"


def test_pat_substring_compatible_not_github() -> None:
    assert is_github_investigation_query("Is this firmware compatible with our OT gateway?") is False


def test_narration_budget_exhausted_blocks_second_hop() -> None:
    budget = TurnLlmBudget()
    budget.record_narration(provider_label="local_primary", outcome="completed")
    assert budget.narration_budget_exhausted() is True
    assert budget.narration_hop_blocked(reserve_seconds=30.0) is not None


def test_deterministic_stitch_idempotent() -> None:
    first = apply_deterministic_prose_enhancements(
        "base",
        user_query=CROSS_SKILL_QUERY,
        primary_intent="cross_skill_investigation",
    )
    second = apply_deterministic_prose_enhancements(
        first,
        user_query=CROSS_SKILL_QUERY,
        primary_intent="cross_skill_investigation",
    )
    assert first == second
    assert is_cross_skill_investigation_query(CROSS_SKILL_QUERY) is True


def test_composer_disabled_by_default_posture() -> None:
    """Track D narration path stays off unless existing synthesis flags are enabled."""
    assert composer_is_enabled() is False
