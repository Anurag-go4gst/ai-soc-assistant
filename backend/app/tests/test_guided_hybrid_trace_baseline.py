"""REV4 batch 1 P1 — guided hybrid flag-off baseline and planning trace.

Encodes plan §1.2 sample-query posture with CONTROL_PLANE_ENABLED=true and
AI_SOC_GUIDED_HYBRID_INVESTIGATION_ENABLED=false (default). Future phases must
keep this snapshot stable when the hybrid flag stays off.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.chat.pipeline import build_live_chat_response
from app.chat.planning_decision import plan_path_and_tools
from app.config import settings
from app.query_understanding.parser import understand_query
from app.routing.route_adjudication import adjudicate_route
from app.routing.select_route_from_understanding import select_route_from_understanding
from app.schemas.requests import ChatRequest

SAMPLE_QUERY = (
    "How should I investigate unusual outbound traffic from an OT host overnight?"
)

# Frozen wire snapshot (CP on, hybrid flag off) — update only with explicit baseline refresh.
_EXPECTED_FLAG_OFF_SNAPSHOT: dict[str, Any] = {
    "selected_skill": "guided_investigation",
    "final_route": "guided_investigation",
    "path_type": "guided_investigation",
    "answer_mode": "guided_investigation",
    "needs_rag": True,
    "needs_spl": False,
    "needs_mcp": False,
    "mcp_allowed": False,
    "spl_allowed": False,
    "dispatch_schedule": ["prepare_rag_only", "rag_early"],
    "dispatch_source": "resource_plan_step_walk",
    "execution_status": "skipped",
    "has_mcp_chronology": False,
    "resource_step_ids": ["rag", "evidence", "sufficiency", "narration"],
}


@pytest.fixture(autouse=True)
def _cp_on_hybrid_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_guided_hybrid_investigation_enabled", False)
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)
    monkeypatch.setattr(settings, "telemetry_mode", "none")
    monkeypatch.setattr(settings, "ai_soc_telemetry_sink", "none")


def _planning_layers(query: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    understanding = understand_query(query)
    base, provenance = select_route_from_understanding(understanding, query)
    routed = {**base, "routing_provenance": provenance}
    query_to_intent = build_query_to_intent(
        query=query,
        query_understanding=understanding,
        routed_skill=base["skill"],
    )
    evidence = plan_evidence(
        query_to_intent.intent_classification,
        query_to_intent=query_to_intent.model_dump(),
        routed=routed,
        query_understanding=understanding,
    )
    route = adjudicate_route(
        deterministic_route=routed["skill"],
        evidence_plan=evidence,
        intent_classification=query_to_intent.intent_classification,
        query_understanding=understanding,
        query_to_intent=query_to_intent.model_dump(),
    )
    planning = plan_path_and_tools(
        intent_classification=query_to_intent.intent_classification.model_dump(),
        evidence_plan=evidence.model_dump(),
        routed=routed,
        query_understanding=understanding,
    )
    return (
        route.model_dump() if hasattr(route, "model_dump") else dict(route),
        evidence.model_dump(),
        planning.model_dump() if hasattr(planning, "model_dump") else dict(planning),
    )


def _flag_off_wire_snapshot(query: str) -> dict[str, Any]:
    response = build_live_chat_response(ChatRequest(message=query))
    evidence_plan = response.evidence_plan or {}
    planning = response.planning_decision or {}
    trace = response.control_plane_trace or {}
    dispatch = trace.get("plan_dispatch") or {}
    route_adj = response.route_adjudication
    if hasattr(route_adj, "model_dump"):
        route_adj = route_adj.model_dump()
    execution = response.execution
    if hasattr(execution, "model_dump"):
        execution = execution.model_dump()
    else:
        execution = {}
    resource_plan = evidence_plan.get("resource_plan") or {}
    steps = resource_plan.get("steps") or []
    return {
        "selected_skill": response.selected_skill,
        "final_route": (route_adj or {}).get("final_route"),
        "path_type": planning.get("path_type"),
        "answer_mode": evidence_plan.get("answer_mode"),
        "needs_rag": evidence_plan.get("needs_rag"),
        "needs_spl": evidence_plan.get("needs_spl"),
        "needs_mcp": evidence_plan.get("needs_mcp"),
        "mcp_allowed": evidence_plan.get("mcp_allowed"),
        "spl_allowed": evidence_plan.get("spl_allowed"),
        "dispatch_schedule": dispatch.get("dispatch_schedule"),
        "dispatch_source": dispatch.get("dispatch_source"),
        "execution_status": execution.get("status"),
        "has_mcp_chronology": bool(trace.get("mcp_chronology")),
        "resource_step_ids": [str(step.get("step_id") or "") for step in steps],
    }


def test_guided_hybrid_flag_defaults_false() -> None:
    assert settings.ai_soc_guided_hybrid_investigation_enabled is False


def test_planning_layer_baseline_fields() -> None:
    route, evidence, planning = _planning_layers(SAMPLE_QUERY)
    assert route.get("final_route") == "guided_investigation"
    assert planning.get("path_type") == "guided_investigation"
    assert evidence.get("answer_mode") == "guided_investigation"
    assert evidence.get("needs_rag") is True
    assert evidence.get("needs_spl") is False
    assert evidence.get("needs_mcp") is False
    assert evidence.get("mcp_allowed") is False
    assert evidence.get("spl_allowed") is False


def test_live_pipeline_flag_off_posture_and_dispatch() -> None:
    snapshot = _flag_off_wire_snapshot(SAMPLE_QUERY)
    assert snapshot["dispatch_schedule"] == ["prepare_rag_only", "rag_early"]
    assert "execution" not in (snapshot["dispatch_schedule"] or [])
    assert snapshot["has_mcp_chronology"] is False
    assert snapshot["execution_status"] == "skipped"


def test_flag_off_wire_snapshot_byte_stable() -> None:
    snapshot = _flag_off_wire_snapshot(SAMPLE_QUERY)
    assert snapshot == _EXPECTED_FLAG_OFF_SNAPSHOT


def test_flag_off_evidence_plan_has_no_hybrid_capability_keys() -> None:
    """New REV4 capability fields must not appear on wire when flag off (P4 adds them)."""
    _, evidence, _ = _planning_layers(SAMPLE_QUERY)
    wire = {k: v for k, v in evidence.items() if v is not None}
    for key in (
        "discovery_allowed",
        "investigation_planning_enabled",
        "spl_review_allowed",
        "safe_spl_execution_allowed",
        "freeform_spl_execution_allowed",
        "mcp_action_allowed",
    ):
        assert key not in wire


def test_flag_off_trace_has_no_guided_handoff() -> None:
    response = build_live_chat_response(ChatRequest(message=SAMPLE_QUERY))
    trace = response.control_plane_trace or {}
    assert "guided_handoff" not in trace
    # Sanity: stable JSON round-trip for regression diffing
    json.dumps(_flag_off_wire_snapshot(SAMPLE_QUERY), sort_keys=True)
