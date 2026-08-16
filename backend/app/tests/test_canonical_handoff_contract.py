"""Plan 8 R0 — durable handoff carries the final ResolvedQueryContract."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.chat.canonical_handoff_store import clear_all_handoffs_for_tests, get_handoff
from app.chat.canonical_planning_orchestrator import graph_node_lane_and_canonical_planning
from app.chat.planning_telemetry import reset_planning_telemetry_for_tests
from app.config import settings
from app.query_understanding.parser import understand_query
from app.routing.select_route_from_understanding import select_route_from_understanding


@pytest.fixture(autouse=True)
def _canonical(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", False)
    reset_planning_telemetry_for_tests()
    clear_all_handoffs_for_tests()


def test_handoff_persists_final_rqc_on_clarification() -> None:
    query = "compare this with what happened last week"
    qu = understand_query(query)
    route, prov = select_route_from_understanding(qu, query)
    out = graph_node_lane_and_canonical_planning(
        {
            "request": SimpleNamespace(message=query),
            "effective_query": query,
            "query_understanding": qu,
            "routed": {**route, "routing_provenance": prov},
            "session_id": "r0-handoff",
            "trace_id": "r0-handoff-trace",
        }
    )
    rqc = out.get("resolved_query_contract")
    assert isinstance(rqc, dict)
    assert rqc.get("intent_family")
    handoff_id = out.get("pending_handoff_id")
    assert handoff_id
    record = get_handoff(str(handoff_id), int(out.get("pending_handoff_version") or 1))
    assert record is not None
    stored = (record.canonical_planning_input or {}).get("resolved_query_contract")
    assert stored == rqc
