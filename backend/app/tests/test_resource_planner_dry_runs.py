"""Design dry-run contract tests for Resource Planner hierarchy."""

from __future__ import annotations

from typing import Any

import pytest

from app.catalogue.match_tiers import match_catalogue_tier
from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.evals.sentinel_eval import sentinel_runtime
from app.graph.planner_led_shadow_graph import run_planner_led_shadow_graph
from app.graph.resource_planner_graph import (
    GOVERNANCE_NODE_NAMES,
    resource_planner_graph_response,
    run_resource_planner_graph,
)
from app.schemas.requests import ChatRequest

REF_QUERY = "What is AML.T0043?"
OT_QUERY = "How should I investigate unusual outbound traffic from an OT host overnight?"
TYPO_QUERY = "failed lgon spike top users last hour"


def _fake_retrieve(**kwargs: Any) -> dict[str, Any]:
    return {
        "retrieval_status": "collected",
        "chunks": [{"doc_id": "atlas-aml-t0043", "title": "AML.T0043"}],
        "required_sources": kwargs.get("required_sources") or [],
    }


def _resource_plan_steps(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    resource_plan = payload.get("resource_plan")
    if not isinstance(resource_plan, dict):
        return []
    steps = resource_plan.get("steps")
    return [step for step in steps if isinstance(step, dict)] if isinstance(steps, list) else []


def _rag_step_status(steps: list[dict[str, Any]]) -> str | None:
    for step in steps:
        if step.get("purpose") == "knowledge_retrieval":
            return str(step.get("status") or "")
    return None


def _enable_cp_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "soc_kb_retrieval_enabled", True)
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", False)
    monkeypatch.setattr(settings, "mcp_server_mock_execution_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_langgraph_shadow_enabled", True)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve)


def test_dry_run_reference_knowledge_recall_no_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_cp_stack(monkeypatch)
    with sentinel_runtime():
        response = build_live_chat_response(ChatRequest(message=REF_QUERY))
    assert response.selected_skill == "knowledge_recall"
    assert (response.evidence_plan or {}).get("answer_mode") == "rag_only"
    assert response.candidate_spl is None
    execution = response.execution.model_dump() if hasattr(response.execution, "model_dump") else response.execution
    assert execution.get("status") in {"skipped", "blocked", "requires_human_review"}
    tier = match_catalogue_tier(REF_QUERY)
    assert tier.tier == "T0"


def test_dry_run_ot_guided_investigation_no_mcp_or_spl(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_cp_stack(monkeypatch)
    with sentinel_runtime():
        response = build_live_chat_response(ChatRequest(message=OT_QUERY))
    assert response.selected_skill == "guided_investigation"
    assert response.candidate_spl is None
    evidence = response.evidence_plan or {}
    assert evidence.get("needs_mcp") is False
    assert evidence.get("mcp_allowed") is False
    execution = response.execution.model_dump() if hasattr(response.execution, "model_dump") else response.execution
    assert execution.get("status") == "skipped"


def test_dry_run_typo_failed_login_candidate_only_spl(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_cp_stack(monkeypatch)
    with sentinel_runtime():
        response = build_live_chat_response(ChatRequest(message=TYPO_QUERY))
    assert response.selected_skill == "spl_generation"
    spl_validation = response.spl_validation
    approved = spl_validation.get("approved") if isinstance(spl_validation, dict) else getattr(spl_validation, "approved", None)
    assert approved is not True
    tier = match_catalogue_tier(TYPO_QUERY)
    assert tier.tier == "T3"
    assert tier.alias_applied is True


def test_resource_planner_graph_records_decision_log_for_reference_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_cp_stack(monkeypatch)
    state = run_resource_planner_graph(ChatRequest(message=REF_QUERY))
    visited = state.get("rp_graph_trace", {}).get("visited_nodes") or []
    for node in GOVERNANCE_NODE_NAMES:
        assert node in visited
    assert isinstance(state.get("decision_log"), list)
    assert len(state.get("decision_log") or []) >= len(visited)


def test_resource_planner_graph_produces_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_cp_stack(monkeypatch)
    state = run_resource_planner_graph(ChatRequest(message=REF_QUERY))
    response = resource_planner_graph_response(state)
    assert response.selected_skill == "knowledge_recall"
    assert response.control_plane_trace is not None
    state_nodes = [r.get("node") for r in (state.get("decision_log") or []) if isinstance(r, dict)]
    trace_nodes = [r.get("node") for r in (response.control_plane_trace.get("decision_log") or []) if isinstance(r, dict)]
    assert trace_nodes == state_nodes
    for node in GOVERNANCE_NODE_NAMES:
        assert node in trace_nodes, node


def test_resource_planner_graph_typo_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_cp_stack(monkeypatch)
    with sentinel_runtime():
        state = run_resource_planner_graph(ChatRequest(message=TYPO_QUERY))
    response = resource_planner_graph_response(state)

    assert response.selected_skill == "spl_generation"
    assert (response.evidence_plan or {}).get("use_case_id") is None
    assert getattr(response, "spl_template_id", None) is None
    execution = response.execution.model_dump() if hasattr(response.execution, "model_dump") else response.execution
    assert execution.get("status") == "requires_human_review"

    tier = match_catalogue_tier(TYPO_QUERY)
    assert tier.tier == "T3"
    assert tier.use_case_id == "auth_failed_login_spike"
    assert tier.spl_template_id == "auth_failed_login_spike"
    assert tier.alias_applied is True

    visited = state.get("rp_graph_trace", {}).get("visited_nodes") or []
    for node in GOVERNANCE_NODE_NAMES:
        assert node in visited, node

    state_sufficiency = state.get("context_sufficiency")
    response_sufficiency = response.context_sufficiency
    if hasattr(state_sufficiency, "model_dump"):
        state_sufficiency = state_sufficiency.model_dump()
    if hasattr(response_sufficiency, "model_dump"):
        response_sufficiency = response_sufficiency.model_dump()
    assert state_sufficiency == response_sufficiency
    assert state_sufficiency.get("status") != "pending_finalize"


def test_imperative_shadow_rag_step_status_parity_for_ot_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_cp_stack(monkeypatch)
    imperative = build_live_chat_response(ChatRequest(message=OT_QUERY))
    _enable_cp_stack(monkeypatch)
    shadow_state = run_planner_led_shadow_graph(ChatRequest(message=OT_QUERY))

    imperative_steps = _resource_plan_steps(imperative.evidence_plan)
    shadow_steps = _resource_plan_steps(shadow_state.get("evidence_plan") if isinstance(shadow_state.get("evidence_plan"), dict) else None)
    imperative_rag = _rag_step_status(imperative_steps)
    shadow_rag = _rag_step_status(shadow_steps)
    assert imperative_rag is not None
    assert shadow_rag is not None
    assert imperative_rag == shadow_rag, f"rag step status drift: imperative={imperative_rag} shadow={shadow_rag}"
