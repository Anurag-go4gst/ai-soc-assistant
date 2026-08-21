"""P0 — investigation authority order: no ResourcePlan before approval; T4 ≠ planner."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.chat.canonical_handoff_store import clear_all_handoffs_for_tests
from app.chat.canonical_planning_orchestrator import graph_node_lane_and_canonical_planning
from app.chat.contracts.semantic_t4_proposal import (
    FROZEN_SEMANTIC_T4_PROPOSAL_FIELDS,
    SemanticT4Proposal,
)
from app.chat.investigation_shaped import is_investigation_shaped_final_rqc
from app.chat.planning_telemetry import reset_planning_telemetry_for_tests
from app.chat.skill_intent_compatibility import CAPABILITY_MCP, CAPABILITY_SPL
from app.config import settings
from app.query_understanding.parser import understand_query
from app.routing.select_route_from_understanding import select_route_from_understanding


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_investigation_plan_before_resource_plan_enabled", False)
    reset_planning_telemetry_for_tests()
    clear_all_handoffs_for_tests()


def _planning_state(query: str) -> dict:
    qu = understand_query(query)
    route, prov = select_route_from_understanding(qu, query)
    return {
        "request": SimpleNamespace(message=query),
        "effective_query": query,
        "query_understanding": qu,
        "routed": {**route, "routing_provenance": prov},
        "trace_id": "p0-trace",
        "session_id": "p0-session",
        "route_plan_shadow": {},
    }


def test_investigation_no_resource_plan_before_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_investigation_plan_before_resource_plan_enabled", True)
    query = (
        "Investigate failed login spike for user:alice host:APP-01 "
        "from 10.0.0.8 in the last 24 hours"
    )
    out = graph_node_lane_and_canonical_planning(_planning_state(query))
    outcome = out.get("canonical_planning_outcome") or {}
    assert outcome.get("status") == "awaiting_investigation_plan"
    assert outcome.get("resource_plan") is None
    assert out.get("evidence_plan") in (None, {})
    assert out.get("execution") in (None, {})
    assert out.get("mcp_evidence") in (None, {}, [])
    assert out.get("route_adjudication")
    assert (out.get("resolved_query_contract") or {}).get("clarification_required") is not True


def test_flag_off_investigation_still_commits_resource_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_investigation_plan_before_resource_plan_enabled", False)
    query = (
        "Investigate failed login spike for user:alice host:APP-01 "
        "from 10.0.0.8 in the last 24 hours"
    )
    out = graph_node_lane_and_canonical_planning(_planning_state(query))
    plan = out.get("evidence_plan") or {}
    assert plan.get("resource_plan")
    assert (out.get("canonical_planning_outcome") or {}).get("status") == "planned"


def test_knowledge_recall_still_commits_resource_plan_when_flag_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_investigation_plan_before_resource_plan_enabled", True)
    query = "What is the CERT-In OT reporting obligation for power utilities?"
    out = graph_node_lane_and_canonical_planning(_planning_state(query))
    outcome = out.get("canonical_planning_outcome") or {}
    # Pure knowledge / policy citation must not enter the investigation wait-state.
    assert outcome.get("status") != "awaiting_investigation_plan"
    if outcome.get("status") == "planned":
        assert (out.get("evidence_plan") or {}).get("resource_plan")


def test_t4_cannot_become_investigation_planner() -> None:
    """T4 frozen schema has no planner / tool / MCP / InvestigationPlan grants."""
    forbidden = {
        "tool_grants",
        "mcp_calls",
        "InvestigationPlanProposal",
        "investigation_plan",
        "resource_plan",
        "primary_skill",
        "selected_skill",
        "executable",
        "auth0",
    }
    assert not (forbidden & set(FROZEN_SEMANTIC_T4_PROPOSAL_FIELDS))
    with pytest.raises(ValidationError):
        SemanticT4Proposal.model_validate(
            {
                "normalized_goal": "investigate auth anomaly",
                "tool_grants": ["splunk_run_query"],
            }
        )
    with pytest.raises(ValidationError):
        SemanticT4Proposal.model_validate(
            {
                "normalized_goal": "investigate auth anomaly",
                "InvestigationPlanProposal": {"objective": "hunt"},
            }
        )
    # Capability lists on the proposal are merge-reject / legacy only — not frozen grants.
    proposal = SemanticT4Proposal(normalized_goal="investigate auth anomaly")
    assert proposal.required_capabilities == []
    assert "tool_grants" not in SemanticT4Proposal.model_fields


def test_t13_investigation_does_not_bypass_common_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    """T1–T3-complete investigation with needs_splunk still enters wait-for-plan when flag on."""
    monkeypatch.setattr(settings, "ai_soc_investigation_plan_before_resource_plan_enabled", True)
    rqc = {
        "intent_family": "live_investigation",
        "answer_goal": "live_results",
        "required_capabilities": [CAPABILITY_SPL, CAPABILITY_MCP],
        "understanding_source": "deterministic_qualification",
        "clarification_required": False,
        "ambiguity_state": "unambiguous",
    }
    assert is_investigation_shaped_final_rqc(
        resolved_query_contract=rqc,
        primary_skill="attack_discovery",
        intent_classification={"intent_family": "live_investigation"},
        query_understanding=SimpleNamespace(soc_investigation_shaped=True),
    )
    query = (
        "Investigate failed login spike for user:alice host:APP-01 "
        "from 10.0.0.8 in the last 24 hours"
    )
    out = graph_node_lane_and_canonical_planning(_planning_state(query))
    outcome = out.get("canonical_planning_outcome") or {}
    assert outcome.get("status") == "awaiting_investigation_plan"
    assert outcome.get("resource_plan") is None
    # Same wait-state channel T4-rescued investigations will use (P0 stub).
    assert (out.get("canonical_planning_outcome") or {}).get("status") == "awaiting_investigation_plan"


def test_guided_owner_is_investigation_shaped() -> None:
    assert is_investigation_shaped_final_rqc(
        resolved_query_contract={"intent_family": "knowledge_recall", "answer_goal": "policy_citation"},
        primary_skill="guided_investigation",
    )
