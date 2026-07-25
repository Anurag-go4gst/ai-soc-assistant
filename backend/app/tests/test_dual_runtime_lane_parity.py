"""Dual-runtime parity: imperative orchestrator vs RP bootstrap canonical path."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.chat.canonical_planning_orchestrator import graph_node_lane_and_canonical_planning
from app.config import settings
from app.graph.resource_planner_graph import rp_node_bootstrap
from app.query_understanding.parser import understand_query
from app.routing.select_route_from_understanding import select_route_from_understanding


@pytest.fixture(autouse=True)
def _enable_canonical(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)


def _base_state(query: str, *, use_case_id: str | None = None) -> dict:
    qu = understand_query(query)
    route, prov = select_route_from_understanding(qu, query)
    state = {
        "request": SimpleNamespace(message=query),
        "effective_query": query,
        "query_understanding": qu,
        "routed": {**route, "routing_provenance": prov},
        "trace_id": "parity-trace",
    }
    if use_case_id:
        state["selected_use_case"] = SimpleNamespace(use_case_id=use_case_id)
    return state


def _parity_keys(out: dict) -> dict:
    return {
        "processing_lane": out.get("processing_lane"),
        "resolved_tier": out.get("resolved_tier"),
        "initial_tier": out.get("initial_tier"),
        "intent_family": (out.get("intent_classification") or {}).get("intent_family"),
        "primary_skill": (out.get("routed") or {}).get("skill"),
        "has_resource_plan": bool((out.get("evidence_plan") or {}).get("resource_plan")),
        "has_canonical": out.get("canonical_planning_input") is not None,
    }


@pytest.mark.parametrize(
    "query,use_case_id",
    [
        (
            "Investigate failed login spike for user:alice host:APP-01 from 10.0.0.8 in the last 24 hours",
            "auth_failed_login_spike",
        ),
        ("What is CVE-2026-12345?", None),
        ("Investigate unusual DNS behaviour around finance users", None),
    ],
)
def test_imperative_vs_rp_bootstrap_parity(query: str, use_case_id: str | None) -> None:
    state = _base_state(query, use_case_id=use_case_id)
    direct = graph_node_lane_and_canonical_planning(dict(state))
    via_rp = rp_node_bootstrap(dict(state))
    assert _parity_keys(direct) == _parity_keys(via_rp)
