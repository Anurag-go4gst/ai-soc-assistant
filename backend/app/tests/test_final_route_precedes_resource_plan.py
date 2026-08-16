"""Plan 8 R1 — final route ownership is committed before ResourcePlan creation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.chat.canonical_planning_orchestrator import graph_node_lane_and_canonical_planning
from app.chat.planning_telemetry import reset_planning_telemetry_for_tests
from app.chat.canonical_handoff_store import clear_all_handoffs_for_tests
from app.config import settings
from app.query_understanding.parser import understand_query
from app.routing.select_route_from_understanding import select_route_from_understanding


def test_static_final_route_bind_precedes_plan_creator() -> None:
    source = Path("app/chat/canonical_planning_orchestrator.py").read_text(encoding="utf-8")
    bind_idx = source.find("def _bind_final_route_from_rqc")
    commit_idx = source.find("evidence_plan, consumed, ignored = plan_evidence_from_canonical")
    bind_call = source.find("state, lane, canonical = _bind_final_route_from_rqc")
    assert bind_idx != -1
    assert bind_call != -1
    assert commit_idx != -1
    assert bind_call < commit_idx


def test_planned_path_has_route_adjudication_before_resource_plan(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    reset_planning_telemetry_for_tests()
    clear_all_handoffs_for_tests()
    query = (
        "Investigate failed login spike for user:alice host:APP-01 "
        "from 10.0.0.8 in the last 24 hours"
    )
    qu = understand_query(query)
    route, prov = select_route_from_understanding(qu, query)
    out = graph_node_lane_and_canonical_planning(
        {
            "request": SimpleNamespace(message=query),
            "effective_query": query,
            "query_understanding": qu,
            "routed": {**route, "routing_provenance": prov},
            "selected_use_case": SimpleNamespace(use_case_id="auth_failed_login_spike"),
            "trace_id": "r1-trace",
            "session_id": "r1-session",
            "route_plan_shadow": {},
        }
    )
    assert out.get("route_adjudication")
    plan = out.get("evidence_plan") or {}
    assert plan.get("resource_plan")
    canonical = out.get("canonical_planning_input") or {}
    routing = canonical.get("routing") or {}
    final_route = (out.get("route_adjudication") or {}).get("final_route")
    if final_route:
        assert routing.get("primary_skill") == final_route
