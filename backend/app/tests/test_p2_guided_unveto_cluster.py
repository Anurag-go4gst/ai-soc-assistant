"""P2 — guided catalog unveto + runtime composable planning flag."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.chat.evidence_planner import plan_evidence
from app.config import settings
from app.planner.executor import derive_dispatch_booleans_from_plan


_CATALOG = Path(__file__).resolve().parents[1] / "skills" / "catalog.json"


def _guided_intent() -> dict:
    return {
        "intent_family": "guided_investigation",
        "primary_intent": "guided_investigation",
        "query_type": "investigation_with_guidance",
        "answer_goal": ["procedural_steps"],
        "confidence": 0.9,
        "confidence_band": "high",
        "requires_clarification": False,
        "reason": "p2_test",
    }


def _guided_catalog_row() -> dict:
    data = json.loads(_CATALOG.read_text(encoding="utf-8"))
    skills = data["skills"] if isinstance(data, dict) else data
    for row in skills:
        if row.get("skill_id") == "guided_investigation":
            return row
    raise AssertionError("guided_investigation row missing")


def test_catalog_no_longer_lists_mcp_execution_as_guided_read_veto() -> None:
    row = _guided_catalog_row()
    assert "mcp_execution" not in (row.get("blocked_tools") or [])
    for write in ("remediation", "admin", "write"):
        assert write in (row.get("blocked_tools") or [])
    allowed = row.get("allowed_tools") or []
    assert "governed_rag" in allowed
    assert "splunk_mcp_search" in allowed


def test_flag_off_restores_rag_only_evidence_and_executor_scheduling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_guided_composable_planning_enabled", False)
    plan = plan_evidence(
        intent_classification=_guided_intent(),
        user_query="Investigate unusual OT remote access outside change window",
    )
    assert plan.needs_spl is False
    assert plan.needs_mcp is False
    assert plan.spl_allowed is False
    assert plan.mcp_allowed is False
    derived = derive_dispatch_booleans_from_plan(
        {
            "planning_decision": {"path_type": "guided_investigation"},
            "evidence_plan": plan.model_dump(),
        }
    )
    assert derived["uses_rag_only_path"] is True


def test_flag_on_guided_owner_does_not_force_rag_only_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_guided_composable_planning_enabled", True)
    plan = plan_evidence(
        intent_classification=_guided_intent(),
        user_query="Investigate unusual OT remote access outside change window",
    )
    assert plan.needs_spl is True
    assert plan.needs_mcp is True
    assert plan.spl_allowed is True
    assert plan.mcp_allowed is True
    assert plan.action_mode == "recommend_only"
    derived = derive_dispatch_booleans_from_plan(
        {
            "planning_decision": {"path_type": "guided_investigation"},
            "evidence_plan": plan.model_dump(),
        }
    )
    assert derived["uses_rag_only_path"] is False


def test_writes_remain_blocked_in_catalog() -> None:
    row = _guided_catalog_row()
    blocked = set(row.get("blocked_tools") or [])
    assert {"remediation", "admin", "write"} <= blocked


def test_composable_flag_does_not_route_to_spl_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_guided_composable_planning_enabled", True)
    plan = plan_evidence(
        intent_classification=_guided_intent(),
        user_query="Hunt for suspicious lateral movement across OT assets",
    )
    assert plan.answer_mode == "guided_investigation"
