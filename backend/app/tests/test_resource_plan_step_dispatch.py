"""Batch C — ResourcePlan step-walk dispatch parity and probe coverage."""

from __future__ import annotations

from typing import Any

import pytest

from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.planner.executor import (
    DispatchHooks,
    _legacy_predicate_dispatch_schedule,
    build_step_walk_dispatch_schedule,
    derive_dispatch_booleans_from_plan,
    execute_plan_dispatch,
    walk_plan_steps,
)
from app.planner.resource_plan import ResourcePlan, project_booleans
from app.query_understanding.parser import understand_query
from app.schemas.requests import ChatRequest

_Q046 = "Which users have excessive failed logins?"
_T1_SPL = "Generate SPL for failed logins"
_T2_GUIDED = "Strange OT chatter to a brand new external host overnight, anything to hunt?"
_RAG_POLICY = "What is our password policy for contractor accounts?"
_UNSAFE = "Isolate host 10.0.0.55 immediately and block all outbound traffic now"
_T0_SMB = "Which hosts are generating the most SMB traffic?"


def _hooks(calls: list[str], *, rag_only: bool = False, pre_mcp: bool = False) -> DispatchHooks:
    def node(name: str):
        def run(state: dict[str, Any]) -> dict[str, Any]:
            calls.append(name)
            if name == "workflow_spl":
                return {**state, "workflow_plan": {"skill": "spl_generation"}}
            if name == "ensure_workflow_plan":
                return {**state, "workflow_plan": {"skill": "alert_summary"}}
            return state

        return run

    return DispatchHooks(
        uses_rag_only_path=lambda _state: rag_only,
        uses_pre_mcp_rag=lambda _state: pre_mcp,
        prepare_rag_only=node("prepare_rag_only"),
        rag_early=node("rag_early"),
        spl_source_resolve=node("spl_source_resolve"),
        workflow_spl=node("workflow_spl"),
        spl_postprocessor=node("spl_postprocessor"),
        ensure_workflow_plan=node("ensure_workflow_plan"),
        execution=node("execution"),
    )


def _state_from_question(question: str, *, skill: str = "attack_discovery") -> dict[str, Any]:
    qu = understand_query(question)
    q2i = build_query_to_intent(query=question, query_understanding=qu, routed_skill=skill)
    intent = q2i.intent_classification.model_dump()
    plan = plan_evidence(
        intent,
        query_to_intent=q2i.model_dump(),
        query_understanding=qu,
        routed={"skill": skill},
    )
    payload = plan.model_dump()
    return {
        "evidence_plan": payload,
        "planning_decision": {"path_type": payload.get("answer_mode")},
        "intent_classification": intent,
        "query_to_intent": q2i.model_dump(),
        "query_understanding": qu,
    }


@pytest.fixture(autouse=True)
def _cp_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)


def test_walk_plan_steps_preserves_order_and_blocked_lineage() -> None:
    state = {
        "evidence_plan": {
            "resource_plan": {
                "steps": [
                    {"step_id": "rag", "resource_id": "rag_corpus:soc_kb", "purpose": "knowledge_retrieval"},
                    {
                        "step_id": "mcp",
                        "resource_id": "mcp_tool:splunk_run_query",
                        "purpose": "mcp_execution",
                        "status": "blocked_policy",
                        "status_reason": "skill_contract",
                    },
                ]
            }
        }
    }
    walk = walk_plan_steps(state)
    assert walk is not None
    assert walk.step_walk_order == ["rag", "mcp"]
    assert walk.dispatchable_step_ids == ["rag"]
    assert walk.skipped_step_reasons["mcp"] == "skill_contract"
    assert "mcp" in walk.blocked_step_ids


def test_step_walk_schedule_matches_legacy_predicate_schedule() -> None:
    state = _state_from_question(_Q046)
    walk = walk_plan_steps(state)
    assert walk is not None
    derived = derive_dispatch_booleans_from_plan(state)
    hooks = _hooks(
        [],
        rag_only=derived["uses_rag_only_path"],
        pre_mcp=derived["uses_pre_mcp_rag"],
    )
    legacy = _legacy_predicate_dispatch_schedule(state, hooks, walk.blocked_step_ids)
    walked = build_step_walk_dispatch_schedule(state, walk, hooks)
    assert walked == legacy


@pytest.mark.parametrize(
    ("question", "skill"),
    [
        (_T0_SMB, "attack_discovery"),
        (_Q046, "attack_discovery"),
        (_T1_SPL, "spl_generation"),
        (_T2_GUIDED, "guided_investigation"),
        (_RAG_POLICY, "knowledge_recall"),
    ],
)
def test_step_walk_dispatch_parity_for_tier_probes(question: str, skill: str) -> None:
    state = _state_from_question(question, skill=skill)
    walk = walk_plan_steps(state)
    if walk is None:
        pytest.skip("no composed plan")
    derived = derive_dispatch_booleans_from_plan(state)
    composed = ResourcePlan.model_validate(state["evidence_plan"]["resource_plan"])
    projected = project_booleans(composed)
    plan = state["evidence_plan"]
    for key in ("needs_rag", "needs_spl", "needs_mcp", "needs_mitre"):
        assert projected[key] == bool(plan.get(key)), key
    hooks = _hooks(
        [],
        rag_only=derived["uses_rag_only_path"],
        pre_mcp=derived["uses_pre_mcp_rag"],
    )
    legacy = _legacy_predicate_dispatch_schedule(state, hooks, walk.blocked_step_ids)
    walked = build_step_walk_dispatch_schedule(state, walk, hooks)
    assert walked == legacy


def test_execute_plan_dispatch_records_step_walk_trace() -> None:
    calls: list[str] = []
    state = _state_from_question(_Q046)
    derived = derive_dispatch_booleans_from_plan(state)
    result = execute_plan_dispatch(
        state,
        _hooks(
            calls,
            rag_only=derived["uses_rag_only_path"],
            pre_mcp=derived["uses_pre_mcp_rag"],
        ),
    )
    trace = result.get("plan_dispatch_trace") or {}
    assert trace.get("dispatch_source") == "resource_plan_step_walk"
    assert trace.get("step_walk_order")
    assert trace.get("predicate_parity", {}).get("uses_rag_only_path") is True
    assert "execution" in calls


def test_chat_probe_dispatch_trace_visible_under_cp_on() -> None:
    payload = build_live_chat_response(ChatRequest(message=_Q046)).model_dump(mode="json")
    trace = (payload.get("control_plane_trace") or {}).get("plan_dispatch") or {}
    assert trace.get("dispatch_source") == "resource_plan_step_walk"
    assert trace.get("step_walk_order")
    contract = payload.get("run_contract") or {}
    assert int(contract.get("collected_evidence_count") or 0) == 0
    assert contract.get("allow_live_result_language") is False


def test_mcp_needed_but_blocked_probe_preserves_route_and_mcp_step() -> None:
    payload = build_live_chat_response(ChatRequest(message=_Q046)).model_dump(mode="json")
    plan = payload.get("evidence_plan") or {}
    if not plan.get("needs_mcp"):
        pytest.skip("probe did not require MCP")
    steps = (plan.get("resource_plan") or {}).get("steps") or []
    assert any(s.get("step_id") == "mcp" for s in steps)
    routing = (payload.get("run_contract") or {}).get("routing") or {}
    assert payload.get("selected_skill") == routing.get("canonical_skill")
    posture = (payload.get("run_contract") or {}).get("mcp_posture") or {}
    assert posture.get("execution_authorized") is False


def test_unsafe_containment_probe_blocks_execution_claims() -> None:
    payload = build_live_chat_response(ChatRequest(message=_UNSAFE)).model_dump(mode="json")
    contract = payload.get("run_contract") or {}
    assert contract.get("execution_authorized") is False
    assert int(contract.get("collected_evidence_count") or 0) == 0
    planning = payload.get("planning_decision") or {}
    assert planning.get("path_type") in {
        "unsafe_blocked",
        "analyst_review_required",
        "live_investigation",
    }


def test_resource_plan_does_not_change_intent_or_route() -> None:
    state = _state_from_question(_Q046)
    before_mode = state["evidence_plan"].get("answer_mode")
    walk = walk_plan_steps(state)
    assert walk is not None
    calls: list[str] = []
    derived = derive_dispatch_booleans_from_plan(state)
    after = execute_plan_dispatch(
        state,
        _hooks(
            calls,
            rag_only=derived["uses_rag_only_path"],
            pre_mcp=derived["uses_pre_mcp_rag"],
        ),
    )
    assert after["evidence_plan"].get("answer_mode") == before_mode
    assert after.get("intent_classification") == state.get("intent_classification")


def test_cp_off_legacy_dispatch_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", False)
    payload = build_live_chat_response(ChatRequest(message=_T0_SMB)).model_dump(mode="json")
    trace = (payload.get("control_plane_trace") or {}).get("plan_dispatch") or {}
    if trace:
        assert trace.get("dispatch_source") == "cp_off_legacy"
