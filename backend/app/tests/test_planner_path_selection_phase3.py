from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.chat.planning_decision import ALLOWED_LIVE_SKILLS, plan_path_and_tools
from app.config import settings
from app.query_understanding.parser import understand_query

REPO_ROOT = Path(__file__).resolve().parents[3]
CROSSWALK_PATH = REPO_ROOT / "docs" / "evals" / "soc_capability_crosswalk.json"


def _plan(query: str, *, routed_skill: str, tool_plan: list[str] | None = None, monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.setattr(settings, "control_plane_enabled", True)
    qu = understand_query(query)
    q2i = build_query_to_intent(query=query, query_understanding=qu, routed_skill=routed_skill)
    intent = q2i.intent_classification.model_dump()
    evidence = plan_evidence(intent, query_to_intent=q2i.model_dump(), routed={"skill": routed_skill}).model_dump()
    return plan_path_and_tools(
        intent_classification=intent,
        evidence_plan=evidence,
        routed={"skill": routed_skill, "tool_plan": tool_plan or []},
        query_understanding=qu,
        selected_use_case=None,
        llm_intent_advisory=q2i.llm_intent_advisory.model_dump() if q2i.llm_intent_advisory else None,
    )


def test_sop_query_produces_rag_only_without_spl_mcp_tools(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_planner_path_selection_enabled", True)
    planning = _plan("What is the escalation policy for failed logins?", routed_skill="knowledge_recall", monkeypatch=monkeypatch)

    assert planning.path_type == "rag_only"
    assert "rag" in planning.branches
    assert "spl" in planning.blocked_tools
    assert "mcp_execution" in planning.blocked_tools
    assert planning.execution_enabled is False


def test_spl_review_query_produces_spl_branch_without_execution(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_planner_path_selection_enabled", True)
    planning = _plan(
        "Generate SPL for failed logins",
        routed_skill="spl_generation",
        tool_plan=["generate_spl", "validate_spl"],
        monkeypatch=monkeypatch,
    )

    assert planning.path_type == "spl_review"
    assert "spl" in planning.branches
    assert planning.execution_enabled is False
    assert "mcp_execution" in planning.blocked_tools


def test_spl_plus_playbook_query_produces_spl_review_plus_rag(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_planner_path_selection_enabled", True)
    planning = _plan(
        "Investigate failed logins and show the playbook steps for escalation policy",
        routed_skill="attack_discovery",
        monkeypatch=monkeypatch,
    )

    assert planning.path_type == "spl_review_plus_rag"
    assert "spl" in planning.branches
    assert "rag" in planning.branches


def test_full_alert_investigation_produces_hybrid_investigation_without_execution(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_planner_path_selection_enabled", True)
    planning = _plan(
        "Review this alert for severity, MITRE mapping, and governed SPL",
        routed_skill="attack_discovery",
        monkeypatch=monkeypatch,
    )

    assert planning.path_type == "hybrid_investigation"
    assert set(planning.branches) >= {"spl", "mitre", "severity"}
    assert planning.execution_enabled is False


def test_mitre_only_without_alert_context_requires_clarification(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_planner_path_selection_enabled", True)
    planning = _plan("Map this to MITRE", routed_skill="knowledge_recall", monkeypatch=monkeypatch)

    assert planning.path_type == "mitre_context_required"
    assert planning.clarification_needed is True
    assert "clarification" in planning.branches


def test_unsafe_request_produces_unsafe_blocked(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_planner_path_selection_enabled", True)
    planning = _plan(
        "Block all suspicious connections from this IP immediately",
        routed_skill="knowledge_recall",
        monkeypatch=monkeypatch,
    )

    assert planning.path_type == "unsafe_blocked"
    assert "unsafe_blocked" in planning.branches or "block" in planning.branches
    assert "mcp_execution" in planning.blocked_tools


def test_unmapped_soc_query_produces_generic_guidance_without_fake_use_case(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_planner_path_selection_enabled", True)
    planning = _plan("Explain what a SOC analyst should check first", routed_skill="knowledge_recall", monkeypatch=monkeypatch)

    assert planning.path_type in {"generic_soc_guidance", "rag_only", "clarification_required"}
    assert planning.use_case_id is None


def test_llm_advisory_cannot_override_unsafe_blocked(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_planner_path_selection_enabled", True)
    query = "Block all suspicious connections from this IP immediately"
    qu = understand_query(query)
    q2i = build_query_to_intent(query=query, query_understanding=qu, routed_skill="knowledge_recall")
    advisory = {
        "path_type_candidate": "hybrid_investigation",
        "intent_family_candidate": "live_investigation",
        "adjudication_status": "accepted",
        "adjudication_reason": "test_override_attempt",
    }
    planning = plan_path_and_tools(
        intent_classification=q2i.intent_classification.model_dump(),
        evidence_plan=plan_evidence(q2i.intent_classification.model_dump()).model_dump(),
        routed={"skill": "knowledge_recall", "tool_plan": []},
        query_understanding=qu,
        llm_intent_advisory=advisory,
    )
    assert planning.path_type == "unsafe_blocked"


def test_flag_off_preserves_trace_only_authority(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_planner_path_selection_enabled", False)
    planning = _plan("Generate SPL for failed logins", routed_skill="spl_generation", monkeypatch=monkeypatch)

    assert planning.authority_source == "deterministic_trace_only"
    assert planning.planner_path_selection_enabled is False
    assert planning.execution_enabled is False


def test_flag_on_enables_planner_path_selection_metadata(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_planner_path_selection_enabled", True)
    planning = _plan("Generate SPL for failed logins", routed_skill="spl_generation", monkeypatch=monkeypatch)

    assert planning.authority_source == "deterministic_planner_path_selection"
    assert planning.planner_path_selection_enabled is True
    assert "planner_schedules_branches_no_execution" in planning.precedence_applied


def test_live_execution_skill_stays_within_allowed_enum(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_planner_path_selection_enabled", True)
    for skill in ALLOWED_LIVE_SKILLS:
        planning = plan_path_and_tools(
            intent_classification={"intent_family": "spl_generation_only", "requires_clarification": False},
            evidence_plan={"needs_spl": True, "needs_mcp": False, "reasons": ["test"]},
            routed={"skill": skill, "tool_plan": []},
            query_understanding=None,
        )
        assert planning.live_execution_skill in ALLOWED_LIVE_SKILLS


def test_crosswalk_metadata_only_not_runtime_activation_allowed(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_planner_path_selection_enabled", True)
    crosswalk = json.loads(CROSSWALK_PATH.read_text(encoding="utf-8"))
    metadata_row = next(
        row for row in crosswalk["use_case_rows"] if row.get("runtime_support_status") == "metadata_only"
    )
    planning = plan_path_and_tools(
        intent_classification={"intent_family": "knowledge_only", "requires_clarification": False},
        evidence_plan={"answer_mode": "rag_only", "needs_rag": True, "reasons": ["test"]},
        routed={"skill": "knowledge_recall", "tool_plan": []},
        query_understanding=type(
            "QU",
            (),
            {"mapped_use_case_ids": [metadata_row["use_case_id"]], "mapped_question_ref": None, "mapped_operation_type": None},
        )(),
    )
    assert planning.planner_runtime_activation_allowed is False
    assert planning.runtime_support_status == "metadata_only"
