"""Canonical answer-mode policy precedence and fail-closed contradictions."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.chat.canonical_answer_mode_policy import (
    CANONICAL_ANSWER_MODE_POLICY,
    CanonicalAnswerModePolicyError,
    resolve_canonical_answer_mode,
)
from app.chat.canonical_handoff_builder import build_canonical_planning_input
from app.chat.canonical_handoff_store import clear_all_handoffs_for_tests
from app.chat.canonical_planning_orchestrator import graph_node_lane_and_canonical_planning
from app.query_understanding.parser import understand_query


@pytest.fixture(autouse=True)
def _clear_handoffs() -> None:
    clear_all_handoffs_for_tests()


def _canonical(*, lane: str, goal: str, family: str, clarification: bool = False):
    query = "Summarize alert ALT-1234-5678 for shift handoff."
    understanding = understand_query(query)
    intent = {
        "intent_family": family,
        "primary_intent": "alert_summary",
        "answer_goal_primary": goal,
        "answer_goal": [goal],
        "requires_clarification": clarification,
        "requires_hil": False,
    }
    canonical = build_canonical_planning_input(
        query=query,
        query_understanding=understanding,
        routed={"skill": "alert_summary", "reasons": ["policy_test"]},
        intent_classification=intent,
        resolved_tier="T4",
        processing_lane=lane,
        handoff_id=f"cpi:answer-mode:{lane}:{goal}:{family}",
    )
    if clarification:
        canonical = canonical.model_copy(
            update={
                "guided_resolution": canonical.guided_resolution.model_copy(
                    update={"clarification_required": True}
                )
            }
        )
    return canonical


def test_policy_is_ordered_inspectable_and_covers_all_routing_dimensions() -> None:
    assert [rule.name for rule in CANONICAL_ANSWER_MODE_POLICY] == [
        "clarification",
        "alert_summary_spl_contradiction",
        "reference_or_knowledge",
        "spl",
        "guided",
        "alert_summary",
        "planner_decides",
    ]
    assert {dimension for rule in CANONICAL_ANSWER_MODE_POLICY for dimension in rule.dimensions} >= {
        "processing_lane",
        "answer_goal",
        "intent_family",
    }


@pytest.mark.parametrize(
    ("lane", "goal", "family", "clarification", "expected_rule", "expected_mode"),
    [
        ("clarification", "spl_artifact", "alert_summary", True, "clarification", "clarification"),
        ("knowledge_short_circuit", "reference_explanation", "reference_knowledge", False, "reference_or_knowledge", "rag_only"),
        ("guided", "spl_artifact", "spl_generation_only", False, "spl", "live_investigation"),
        ("guided", "guided_investigation", "guided_investigation", False, "guided", "guided_investigation"),
        ("guided", "live_investigation", "alert_summary", False, "alert_summary", "rag_only"),
        ("known", "live_investigation", "hybrid_alert_review", False, "planner_decides", None),
    ],
)
def test_policy_matrix_preserves_precedence(
    lane: str,
    goal: str,
    family: str,
    clarification: bool,
    expected_rule: str,
    expected_mode: str | None,
) -> None:
    decision = resolve_canonical_answer_mode(
        _canonical(lane=lane, goal=goal, family=family, clarification=clarification)
    )
    assert decision.rule_name == expected_rule
    assert decision.answer_mode == expected_mode


def test_alert_summary_spl_goal_is_a_typed_policy_error() -> None:
    canonical = _canonical(lane="guided", goal="spl_artifact", family="alert_summary")
    with pytest.raises(CanonicalAnswerModePolicyError) as exc_info:
        resolve_canonical_answer_mode(canonical)
    assert exc_info.value.reason == "contradictory_alert_summary_spl_goal"
    assert exc_info.value.category == "answer_mode_policy"


def test_orchestrator_converts_policy_error_to_non_executable_typed_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _contradiction(*_args, **_kwargs):
        raise CanonicalAnswerModePolicyError(
            reason="contradictory_alert_summary_spl_goal",
            detail="intent_family=alert_summary;answer_goal=spl_artifact",
        )

    monkeypatch.setattr(
        "app.chat.canonical_planning_orchestrator.plan_evidence_from_canonical",
        _contradiction,
    )
    query = "What is CVE-2026-12345?"
    understanding = understand_query(query)
    state = {
        "request": SimpleNamespace(message=query),
        "effective_query": query,
        "query_understanding": understanding,
        "routed": {"skill": "knowledge_recall", "reasons": ["policy_test"]},
        "trace_id": "answer-mode-policy-error",
    }
    result = graph_node_lane_and_canonical_planning(state)
    assert result["canonical_planning_outcome"]["status"] == "planning_failed"
    assert result["canonical_planning_failure"]["reason"] == "contradictory_alert_summary_spl_goal"
    assert result["plan_dispatch_trace"]["dispatch_schedule"] == []
    assert "evidence_plan" not in result
    assert "execution" not in result


def test_unknown_family_keeps_evidence_planner_fail_closed_choice() -> None:
    decision = resolve_canonical_answer_mode(
        _canonical(lane="known", goal="live_investigation", family="not_a_real_family")
    )
    assert decision.rule_name == "planner_decides"
    assert decision.answer_mode is None
