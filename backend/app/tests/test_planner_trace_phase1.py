from __future__ import annotations

from app.chat.intent_classifier import build_query_to_intent
from app.chat.planning_decision import compute_planning_decision_trace_only
from app.query_understanding.parser import understand_query


def test_trace_only_planner_keeps_execution_disabled_for_spl_review() -> None:
    query = "Generate SPL for failed logins"
    qu = understand_query(query)
    q2i = build_query_to_intent(query=query, query_understanding=qu, routed_skill="spl_generation")
    planning = compute_planning_decision_trace_only(
        intent_classification=q2i.intent_classification.model_dump(),
        evidence_plan={
            "needs_spl": True,
            "needs_mcp": False,
            "needs_rag": False,
            "needs_mitre": False,
            "reasons": ["spl_artifact_requested"],
        },
        routed={"skill": "spl_generation", "tool_plan": ["generate_spl", "validate_spl"]},
        query_understanding=qu,
        selected_use_case=None,
    )

    assert planning.path_type == "spl_review"
    assert planning.execution_enabled is False
    assert "spl" in planning.branches
    assert "mcp" in planning.blocked_tools
    assert planning.authority_source == "deterministic_trace_only"


def test_trace_only_planner_marks_mitre_without_context_as_clarification() -> None:
    query = "Map this to MITRE"
    qu = understand_query(query)
    q2i = build_query_to_intent(query=query, query_understanding=qu, routed_skill="knowledge_recall")
    planning = compute_planning_decision_trace_only(
        intent_classification=q2i.intent_classification.model_dump(),
        evidence_plan={
            "needs_spl": False,
            "needs_mcp": False,
            "needs_rag": False,
            "needs_mitre": True,
            "requires_hil": False,
            "reasons": ["mitre_mapping_requires_grounding"],
        },
        routed={"skill": "knowledge_recall", "tool_plan": ["retrieve_approved_knowledge"]},
        query_understanding=qu,
        selected_use_case=None,
    )

    assert planning.path_type == "mitre_context_required"
    assert planning.clarification_needed is True
    assert planning.hil_required is True
    assert planning.branches == ["hil", "clarification"]
    assert "mcp_execution" in planning.blocked_tools

