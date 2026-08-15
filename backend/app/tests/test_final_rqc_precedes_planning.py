"""Plan 8 R0 — final RQC and clarification precede ResourcePlan creation."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.chat.canonical_answer_mode_policy import CanonicalAnswerModePolicyError
from app.chat.canonical_handoff_builder import build_canonical_planning_input
from app.chat.canonical_handoff_store import clear_all_handoffs_for_tests, get_handoff
from app.chat.canonical_planning_orchestrator import graph_node_lane_and_canonical_planning
from app.chat.intent_family_defaults import build_t0_knowledge_stub
from app.chat.plan_evidence_from_canonical import plan_evidence_from_canonical
from app.chat.planning_telemetry import reset_planning_telemetry_for_tests
from app.config import settings
from app.query_understanding.parser import understand_query
from app.routing.select_route_from_understanding import select_route_from_understanding


ORCHESTRATOR = Path("app/chat/canonical_planning_orchestrator.py")
PLANNER = Path("app/chat/plan_evidence_from_canonical.py")


@pytest.fixture(autouse=True)
def _canonical(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", False)
    reset_planning_telemetry_for_tests()
    clear_all_handoffs_for_tests()


def _state(query: str) -> dict:
    qu = understand_query(query)
    route, prov = select_route_from_understanding(qu, query)
    return {
        "request": SimpleNamespace(message=query),
        "effective_query": query,
        "query_understanding": qu,
        "routed": {**route, "routing_provenance": prov},
        "trace_id": "r0-trace",
        "session_id": "r0-session",
    }


def test_static_plan_creator_is_after_final_rqc_and_clarification() -> None:
    source = ORCHESTRATOR.read_text(encoding="utf-8")
    rqc_idx = source.find("resolved_query = maybe_enrich_t4_semantic")
    clarify_idx = source.find("resolved_query.clarification_required")
    commit_idx = source.find("return _commit_planned_outcome")
    assert rqc_idx != -1
    assert clarify_idx != -1
    assert rqc_idx < clarify_idx < commit_idx
    tree = ast.parse(PLANNER.read_text(encoding="utf-8"))
    assert "final_rqc_clarification_blocks_planning" in ast.dump(tree)


def test_clarification_query_does_not_create_a_resource_plan() -> None:
    out = graph_node_lane_and_canonical_planning(
        _state("compare this with what happened last week")
    )
    rqc = out.get("resolved_query_contract") or {}
    assert rqc.get("clarification_required") is True
    outcome = out.get("canonical_planning_outcome") or {}
    assert outcome.get("status") == "clarification_required"
    assert out.get("evidence_plan") in (None, {})
    handoff_id = out.get("pending_handoff_id")
    assert handoff_id
    record = get_handoff(str(handoff_id), int(out.get("pending_handoff_version") or 1))
    assert record is not None
    stored = (record.canonical_planning_input or {}).get("resolved_query_contract")
    assert stored
    assert stored.get("clarification_required") is True


def test_planner_refuses_final_rqc_clarification() -> None:
    query = "What is MITRE T1059?"
    qu = understand_query(query)
    canonical = build_canonical_planning_input(
        query=query,
        query_understanding=qu,
        routed={"skill": "knowledge_recall"},
        intent_classification=build_t0_knowledge_stub(),
        resolved_tier="T0",
        processing_lane="knowledge_short_circuit",
        handoff_id="r0-block",
    )
    with pytest.raises(CanonicalAnswerModePolicyError) as exc:
        plan_evidence_from_canonical(
            canonical,
            state={
                "resolved_query_contract": {
                    "clarification_required": True,
                    "ambiguity_state": "clarification_required",
                }
            },
        )
    assert exc.value.reason == "final_rqc_clarification_blocks_planning"
