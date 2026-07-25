"""Named behavioural tests for canonical architecture completion."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.chat.canonical_handoff_store import (
    CanonicalHandoffRecord,
    clear_all_handoffs_for_tests,
    commit_resource_plan,
    get_committed_resource_plan,
    get_handoff,
    record_duplicate_call_hash,
    save_clarification_handoff,
    save_handoff,
)
from app.chat.canonical_handoff_builder import build_canonical_planning_input
from app.chat.canonical_mode import is_canonical_authoritative
from app.chat.canonical_planning_orchestrator import graph_node_lane_and_canonical_planning
from app.tests.support.canonical_flow import run_canonical_flow
from app.chat.contracts.knowledge_recall import KnowledgeRecallResult
from app.chat.decision_record import decision_log_for_trace
from app.chat.guided_detail_resolution import run_guided_detail_resolution
from app.chat.intent_family_defaults import build_t0_knowledge_stub
from app.chat.known_detail_completion import KnownCompletenessResult
from app.chat.plan_evidence_from_canonical import plan_evidence_from_canonical
from app.chat.planning_telemetry import planning_events, reset_planning_telemetry_for_tests
from app.chat.reference_qualification import qualify_reference_query
from app.config import settings
from app.graph.resource_planner_graph import rp_node_bootstrap
from app.planner.executor import execute_plan_dispatch
from app.query_understanding.parser import understand_query
from app.routing.select_route_from_understanding import select_route_from_understanding


@pytest.fixture(autouse=True)
def _canonical_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_session_context_enabled", True)
    reset_planning_telemetry_for_tests()
    clear_all_handoffs_for_tests()


def _state(query: str, *, use_case_id: str | None = None, handoff_resume: dict | None = None) -> dict:
    qu = understand_query(query)
    route, prov = select_route_from_understanding(qu, query)
    state = {
        "request": SimpleNamespace(message=query),
        "effective_query": query,
        "query_understanding": qu,
        "routed": {**route, "routing_provenance": prov},
        "trace_id": "trace-canonical-e2e",
        "session_id": "sess-test",
    }
    if use_case_id:
        state["selected_use_case"] = SimpleNamespace(use_case_id=use_case_id)
    if handoff_resume:
        state["handoff_resume"] = handoff_resume
    return state


def test_t1_t3_complete_no_classifier_no_guided() -> None:
    result = run_canonical_flow(
        "Investigate failed login spike for user:alice host:APP-01 from 10.0.0.8 in the last 24 hours",
        use_case_id="auth_failed_login_spike",
        trace_id="trace-canonical-e2e",
    )
    out = result.state
    assert result.outcome is not None and result.outcome.status == "planned"
    assert out["processing_lane"] == "known"
    assert out["intent_classification"]["llm_intent_status"] == "skipped"
    assert out.get("gap_resolution") is None
    assert out["canonical_planning_input"] is not None
    assert out["evidence_plan"]["resource_plan"] is not None
    events = [e["event"] for e in planning_events()]
    assert "lane_router.decided" in events
    assert "planner_handoff.created" in events
    assert "resource_plan.created" in events
    assert decision_log_for_trace(out)


def test_t1_t3_incomplete_preserves_original_skill() -> None:
    query = "Investigate failed login spike for host:WRONG-99"
    out = graph_node_lane_and_canonical_planning(_state(query, use_case_id="auth_failed_login_spike"))
    gap = out.get("gap_resolution") or {}
    assert gap.get("original_skill") or out["routed"].get("skill")
    assert out["canonical_planning_input"] is not None


def test_t4_to_t0_knowledge_plan() -> None:
    result = run_canonical_flow("What is CVE-2026-12345?", trace_id="trace-canonical-e2e")
    out = result.state
    assert result.outcome is not None and result.outcome.status == "planned"
    assert out["initial_tier"] == "T4"
    assert out["resolved_tier"] == "T0"
    assert out["processing_lane"] == "knowledge_short_circuit"
    assert out["evidence_plan"]["resource_plan"] is not None


def test_t4_status_query_stays_t4() -> None:
    q = qualify_reference_query("Are our systems affected by CVE-2026-12345?")
    assert not q.resolves_to_t0
    out = graph_node_lane_and_canonical_planning(_state("Are our systems affected by CVE-2026-12345?"))
    assert out["resolved_tier"] != "T0"
    assert out["processing_lane"] == "guided"


def test_same_lane_different_answer_goals_differ() -> None:
    query = "What is MITRE T1059?"
    qu = understand_query(query)
    intent = build_t0_knowledge_stub()
    base = build_canonical_planning_input(
        query=query,
        query_understanding=qu,
        routed={"skill": "knowledge_recall"},
        intent_classification=intent,
        resolved_tier="T0",
        processing_lane="knowledge_short_circuit",
        handoff_id="cpi:goal-a",
    )
    plan_a, _, _ = plan_evidence_from_canonical(base, intent_classification=intent, query_understanding=qu)
    plan_b, _, _ = plan_evidence_from_canonical(
        base.model_copy(
            update={
                "trace": base.trace.model_copy(update={"handoff_id": "cpi:goal-b", "handoff_version": 2}),
                "routing": base.routing.model_copy(
                    update={
                        "answer_goal": "live_investigation",
                        "intent_family": "live_investigation",
                        "processing_lane": "guided",
                        "resolved_tier": "T4",
                        "primary_skill": "attack_discovery",
                    }
                ),
            }
        ),
        intent_classification={
            **intent,
            "intent_family": "live_investigation",
            "primary_intent": "attack_discovery",
            "answer_goal_primary": "live_investigation",
            "answer_goal": ["live_results"],
        },
        query_understanding=qu,
    )
    assert plan_a.answer_mode != plan_b.answer_mode


def test_tool_failure_not_successful_resolution() -> None:
    completeness = KnownCompletenessResult(
        required_fields=["cve_context"],
        present_fields=[],
        missing_fields=["cve_context"],
        missing_field_categories={"cve_context": "tool_discoverable"},
        completeness_status="incomplete",
        divert_to_guided=True,
    )
    error_result = KnowledgeRecallResult(status="error", errors=["source_unavailable"])
    with patch("app.chat.guided_detail_resolution.run_knowledge_recall", return_value=error_result):
        gap = run_guided_detail_resolution(
            query="What is CVE-2026-12345?",
            handoff_id="h-fail",
            handoff_version=1,
            intent_family="reference_knowledge",
            answer_goal="reference_explanation",
            completeness=completeness,
            reference_ids=["CVE-2026-12345"],
        )
    assert gap.tool_statuses.get("knowledge_recall") == "error"
    assert gap.resolution_status != "complete"


def test_duplicate_tool_call_blocked() -> None:
    assert record_duplicate_call_hash("h-dup", 1, "abc") is False
    assert record_duplicate_call_hash("h-dup", 1, "abc") is True


def test_duplicate_handoff_replay_idempotent() -> None:
    handoff_id = "cpi:replay"
    version = 1
    query = "What is MITRE T1059?"
    qu = understand_query(query)
    intent = build_t0_knowledge_stub()
    canonical = build_canonical_planning_input(
        query=query,
        query_understanding=qu,
        routed={"skill": "knowledge_recall"},
        intent_classification=intent,
        resolved_tier="T0",
        processing_lane="knowledge_short_circuit",
        handoff_id=handoff_id,
        handoff_version=version,
    )
    plan1, _, _ = plan_evidence_from_canonical(canonical, intent_classification=intent, query_understanding=qu)
    plan2, _, _ = plan_evidence_from_canonical(canonical, intent_classification=intent, query_understanding=qu)
    assert plan1.model_dump() == plan2.model_dump()
    assert get_committed_resource_plan(handoff_id, version) is not None


def test_legacy_planner_not_called_on_canonical_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.chat import pipeline

    calls: list[str] = []

    def _spy(*_a, **_k):
        calls.append("legacy_evidence_planning")
        return {"evidence_plan": {}}

    monkeypatch.setattr(pipeline, "graph_node_evidence_planning", _spy)
    state = {"intent_classification": None, "evidence_plan": None}
    out = pipeline._graph_node_planning_decision_from_canonical(state)
    assert calls == []
    assert out.get("canonical_planning_failure") is not None


def test_legacy_plan_evidence_not_invoked_when_canonical_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def _spy(*_a, **_k):
        calls.append("plan_evidence")
        raise AssertionError("legacy plan_evidence should not run")

    monkeypatch.setattr("app.chat.evidence_planner.plan_evidence", _spy)
    state = {"intent_classification": None, "evidence_plan": None}
    from app.chat import pipeline

    pipeline._graph_node_planning_decision_from_canonical(state)
    assert calls == []


def test_runtime_parity_imperative_vs_rp_graph() -> None:
    query = "What is CVE-2026-12345?"
    st = _state(query)
    direct = graph_node_lane_and_canonical_planning(dict(st))
    via_rp = rp_node_bootstrap(dict(st))
    for key in ("processing_lane", "resolved_tier", "initial_tier"):
        assert direct.get(key) == via_rp.get(key)
    assert bool((direct.get("evidence_plan") or {}).get("resource_plan")) == bool(
        (via_rp.get("evidence_plan") or {}).get("resource_plan")
    )


def test_clarification_handoff_persisted() -> None:
    save_clarification_handoff(
        handoff_id="cpi:clarify",
        handoff_version=1,
        canonical_planning_input={"routing": {"processing_lane": "known"}},
        gap_resolution=None,
        unresolved_fields=["user"],
        clarification_reason="missing_user",
        original_query="Investigate failed login spike",
    )
    record = get_handoff("cpi:clarify", 1)
    assert record is not None
    assert record.status == "awaiting_clarification"


def test_execution_rejects_uncommitted_plan() -> None:
    from app.chat.pipeline import _dispatch_hooks

    state = {
        "evidence_plan": {
            "resource_plan": {"steps": [], "provenance": {"committed": False}},
        },
        "trace_id": "t1",
    }
    out = execute_plan_dispatch(state, hooks=_dispatch_hooks())
    assert out.get("canonical_planning_failure") is not None


def test_canonical_authoritative_flag() -> None:
    assert is_canonical_authoritative() is True
