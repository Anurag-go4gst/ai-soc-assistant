"""Tests for canonical planning architecture (rev 4)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.chat.canonical_handoff_builder import build_canonical_planning_input
from app.chat.canonical_planning_orchestrator import graph_node_lane_and_canonical_planning
from app.chat.decision_record import emit_decision_record
from app.chat.evidence_planner import _present_evidence_keys
from app.chat.intent_family_defaults import build_t0_knowledge_stub
from app.chat.known_detail_completion import evaluate_known_detail_completion
from app.chat.lane_router import initial_tier_for_match_path, is_known_catalogue_match, lane_for_match_path
from app.chat.plan_evidence_from_canonical import plan_evidence_from_canonical
from app.chat.canonical_handoff_store import clear_all_handoffs_for_tests
from app.chat.planning_telemetry import planning_events, reset_planning_telemetry_for_tests
from app.chat.reference_qualification import qualify_reference_query
from app.config import settings
from app.planner.planner_hierarchy import DecisionRecord, new_decision_record_id
from app.query_understanding.parser import understand_query
from app.routing.select_route_from_understanding import select_route_from_understanding


@pytest.fixture(autouse=True)
def _enable_canonical(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    reset_planning_telemetry_for_tests()
    clear_all_handoffs_for_tests()


def test_lane_router_t1_t3_known() -> None:
    for path in ("exact_105_question", "use_case_catalog", "near_105_question"):
        assert is_known_catalogue_match(path)
        initial, resolved, lane = lane_for_match_path(path)
        assert initial in {"T1", "T2", "T3"}
        assert lane == "known"


def test_no_match_initial_t4() -> None:
    assert initial_tier_for_match_path("out_of_registry") == "T4"
    _, _, lane = lane_for_match_path("out_of_registry")
    assert lane == "guided"


def test_t0_only_after_qualification() -> None:
    assert initial_tier_for_match_path("out_of_registry") == "T4"
    q = qualify_reference_query("What is MITRE T1059?", intent_family="reference_knowledge")
    assert q.resolves_to_t0
    _, resolved, lane = lane_for_match_path("out_of_registry", resolved_tier="T0")
    assert resolved == "T0"
    assert lane == "knowledge_short_circuit"


def test_cve_status_stays_t4() -> None:
    q = qualify_reference_query("Are our systems affected by CVE-2026-12345?")
    assert not q.resolves_to_t0
    assert "environment_status" in q.requested_scopes


def test_present_key_projection_bare_user_host() -> None:
    qu = understand_query("alice failed login on app01")
    present = _present_evidence_keys(query_to_intent={}, query_understanding=qu)
    assert "user" in present
    assert "host" in present


def test_known_complete_path_skips_full_classifier(monkeypatch: pytest.MonkeyPatch) -> None:
    query = "Investigate failed login spike for user:alice host:APP-01 from 10.0.0.8 in the last 24 hours"
    qu = understand_query(query)
    route, prov = select_route_from_understanding(qu, query)
    state = {
        "request": SimpleNamespace(message=query),
        "effective_query": query,
        "query_understanding": qu,
        "routed": {**route, "routing_provenance": prov},
        "selected_use_case": SimpleNamespace(use_case_id="auth_failed_login_spike"),
        "trace_id": "trace-test",
    }
    out = graph_node_lane_and_canonical_planning(state)
    assert out["intent_classification"]["llm_intent_status"] == "skipped"
    assert out["evidence_plan"]["resource_plan"] is not None
    assert out["processing_lane"] == "known"


def test_t4_resolves_to_t0_knowledge_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    query = "What is CVE-2026-12345?"
    qu = understand_query(query)
    route, prov = select_route_from_understanding(qu, query)
    state = {
        "request": SimpleNamespace(message=query),
        "effective_query": query,
        "query_understanding": qu,
        "routed": {**route, "routing_provenance": prov},
        "trace_id": "trace-t0",
    }
    out = graph_node_lane_and_canonical_planning(state)
    assert out["resolved_tier"] == "T0"
    assert out["processing_lane"] == "knowledge_short_circuit"
    assert out["intent_classification"]["intent_family"] == "reference_knowledge"
    assert out["evidence_plan"]["resource_plan"] is not None
    events = [e["event"] for e in planning_events()]
    assert "tier.resolved" in events
    assert "planner_handoff.created" in events
    assert "resource_plan.created" in events


def test_decision_record_payload_roundtrip() -> None:
    record = emit_decision_record(
        {},
        DecisionRecord(
            record_id=new_decision_record_id(),
            node="lane_router",
            authority="deterministic",
            decision_reason="test",
            inputs_ref=["state"],
            outputs_ref=["state"],
            payload={"match_path": "use_case_catalog", "user": "secret-user"},
        ),
    )
    payload = record["decision_log"][-1]["payload"]
    assert payload["match_path"] == "use_case_catalog"


def test_final_planner_consumes_answer_goal(monkeypatch: pytest.MonkeyPatch) -> None:
    query = "What is MITRE T1059?"
    qu = understand_query(query)
    intent = build_t0_knowledge_stub()
    canonical = build_canonical_planning_input(
        query=query,
        query_understanding=qu,
        routed={"skill": "knowledge_recall", "reasons": ["test"]},
        intent_classification=intent,
        resolved_tier="T0",
        processing_lane="knowledge_short_circuit",
        handoff_id="cpi:test-goal-a",
    )
    plan_a, consumed_a, _ = plan_evidence_from_canonical(
        canonical,
        intent_classification=intent,
        query_understanding=qu,
        routed={"skill": "knowledge_recall"},
    )
    canonical_b = canonical.model_copy(
        update={
            "trace": canonical.trace.model_copy(update={"handoff_id": "cpi:test-goal-b"}),
            "routing": canonical.routing.model_copy(
                update={
                    "answer_goal": "live_investigation",
                    "intent_family": "live_investigation",
                    "processing_lane": "guided",
                    "resolved_tier": "T4",
                }
            ),
        }
    )
    intent_b = {
        **intent,
        "intent_family": "live_investigation",
        "primary_intent": "attack_discovery",
        "answer_goal_primary": "live_investigation",
        "answer_goal": ["live_results"],
    }
    plan_b, consumed_b, _ = plan_evidence_from_canonical(
        canonical_b,
        intent_classification=intent_b,
        query_understanding=qu,
        routed={"skill": "attack_discovery"},
    )
    assert plan_a.answer_mode != plan_b.answer_mode
    assert "routing.answer_goal" in consumed_a


def test_unknown_family_fail_closed() -> None:
    from app.chat.evidence_planner import plan_evidence

    plan = plan_evidence(
        {
            "intent_family": "not_a_real_family",
            "primary_intent": "human_review",
            "query_type": "ask_for_next_action",
            "answer_goal": ["clarification"],
            "confidence": 0.5,
            "confidence_band": "low",
            "requires_clarification": False,
            "reason": "synthetic",
        }
    )
    assert plan.answer_mode == "clarification"
    assert "unknown_intent_family_fail_closed" in plan.reasons


def test_known_incomplete_wrong_entity_divert() -> None:
    qu = understand_query("Investigate failed login spike for host:WRONG-99")
    completeness = evaluate_known_detail_completion(
        use_case_id="auth_failed_login_spike",
        query_to_intent={},
        query_understanding=qu,
    )
    assert completeness.divert_to_guided or completeness.clarification_required
