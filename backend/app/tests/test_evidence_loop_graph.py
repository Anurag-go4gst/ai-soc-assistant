"""Stage 4B — governed evidence-collection loop (legacy linear CP graph).

Topology and hub-routing regression on ``linear_graph_legacy`` (test harness only).
Production ``/chat`` uses the RP hierarchy graph.
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.chat.evidence_loop import MAX_MCP_HOPS
from app.chat.linear_graph_legacy import (
    _compiled_chat_graph,
    _compiled_chat_graph_cp,
    run_chat_via_langgraph,
)
from app.schemas.requests import ChatRequest

QUERY = "show failed admin logins in the last 24 hours"


def test_cp_off_graph_has_no_loop() -> None:
    graph = _compiled_chat_graph().get_graph()
    assert "mcp_call" not in set(graph.nodes)
    edges = {(e.source, e.target) for e in graph.edges}
    assert ("evidence_planning", "shadow_tail") in edges
    assert ("execution", "context_finalize") in edges


def test_cp_on_graph_has_bounded_loop_topology() -> None:
    graph = _compiled_chat_graph_cp().get_graph()
    nodes = set(graph.nodes)
    assert "mcp_call" in nodes
    edges = {(e.source, e.target) for e in graph.edges}
    # Loopbacks to the HUB.
    assert ("mcp_call", "evidence_planning") in edges
    assert ("execution", "evidence_planning") in edges


def test_hub_route_consumes_execution_verdict() -> None:
    from app.chat.evidence_loop import ROUTE_BROADEN, ROUTE_DISCOVERY_HOP
    from app.chat.linear_graph_legacy import _hub_route

    # Execution re-entry: the stored assessor verdict drives the edge.
    assert _hub_route({"execution": {}, "mcp_loop": {"route": ROUTE_BROADEN}}) == "context_finalize"
    # Discovery re-entry with a pending hop routes to the read-only mcp_call node.
    assert (
        _hub_route({"mcp_chronology": ["splunk_get_info"], "mcp_loop": {"route": ROUTE_DISCOVERY_HOP}})
        == "mcp_call"
    )
    # Discovery exhausted → enter the linear chain once.
    assert _hub_route({"mcp_chronology": [], "mcp_loop": {"route": "execute"}}) == "shadow_tail"


def test_cp_on_run_terminates_and_surfaces_loop_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    # Must not raise GraphRecursionError — the single bound guarantees termination.
    response = run_chat_via_langgraph(ChatRequest(message=QUERY))
    assert response is not None
    trace = response.control_plane_trace or {}
    loop = trace.get("evidence_loop")
    assert isinstance(loop, dict)
    assert loop["hops_done"] <= MAX_MCP_HOPS
    assert len(loop["hops"]) >= 1  # at least one read-only discovery hop ran
    assert loop["decision"]["route"]  # a verdict was recorded


def test_cp_on_loop_state_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    final_state = _compiled_chat_graph_cp().invoke(
        {"request": ChatRequest(message=QUERY), "session_role": None},
        {"recursion_limit": MAX_MCP_HOPS * 2 + 30},
    )
    assert int(final_state.get("mcp_hops_done", 0)) <= MAX_MCP_HOPS
    # Discovery chronology was composed and read-only hops were recorded.
    assert isinstance(final_state.get("mcp_chronology"), list)
    for hop in final_state.get("mcp_evidence") or []:
        assert hop["outcome"] in {"planned", "collected"}
        assert hop["tool"] != "splunk_run_query"


def test_cp_on_merges_loop_hops_into_source_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    response = run_chat_via_langgraph(ChatRequest(message=QUERY))
    assert response is not None
    discovery = [item for item in response.source_evidence if item.source_type == "mcp_discovery"]
    assert len(discovery) >= 1
    assert all(item.collection_status in {"planned", "collected"} for item in discovery)
    discovery_ids = {item.evidence_id for item in discovery}
    assert discovery_ids.issubset(set(response.structured_context.source_evidence_refs))


def test_cp_on_chronology_is_deterministic_without_advisory_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    # Live blocking path must NOT call the slow LLM planner unless the advisory
    # flag is on (PowerGrid latency incident regression guard).
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    import app.chat.pipeline as pipeline

    def _boom(*args, **kwargs):
        raise AssertionError("plan_tool_chronology must not run on the live path by default")

    monkeypatch.setattr(pipeline, "plan_tool_chronology", _boom)
    monkeypatch.setattr(pipeline, "mcp_tool_plan_llm_advisory_enabled", lambda: False)
    # _boom not raising already proves the LLM planner was skipped; assert the
    # recorded provenance too.
    response = run_chat_via_langgraph(ChatRequest(message=QUERY))
    assert response is not None
    loop_planner = ((response.control_plane_trace or {}).get("evidence_loop") or {}).get("planner") or {}
    assert loop_planner.get("decision_source") == "deterministic_default"
    assert (loop_planner.get("planner") or {}).get("llm_called") is False


def test_cp_off_parity_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", False)
    response = run_chat_via_langgraph(ChatRequest(message=QUERY))
    assert response is not None
    # No loop state leaks onto the linear path.
    final_state = _compiled_chat_graph().invoke({"request": ChatRequest(message=QUERY)})
    assert "mcp_chronology" not in final_state


def test_cp_on_recipe_driven_turn_runs_through_real_langgraph_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """O5c end to end (items 3.1-3.3): a turn seeded with mcp_recipe_id (today
    only item 3.2's selector would set this — no live pipeline stage does yet)
    must terminate correctly through the SAME compiled graph the chronology
    path uses — discovery hop runs, records a call, advances to the search
    call, and the turn ends safely (mock execution globally gated in this
    test env, so it correctly stops at analyst hand-off rather than looping)."""
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    final_state = _compiled_chat_graph_cp().invoke(
        {
            "request": ChatRequest(message=QUERY),
            "session_role": None,
            "mcp_recipe_id": "hunt_baseline",
        },
        {"recursion_limit": MAX_MCP_HOPS * 2 + 30},
    )
    records = final_state.get("mcp_call_records")
    assert isinstance(records, list) and len(records) >= 1
    assert records[0]["call_id"] == "c1_discovery"
    assert records[0]["outcome"] == "ok"
    assert isinstance(final_state.get("mcp_loop"), dict)
    assert final_state.get("execution") is not None


def test_debug_trace_surfaces_mcp_calls_for_recipe_driven_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    """The analyst-visible trace (item 3.3) must carry the same per-call
    lineage the graph produced — not just consumed internally."""
    from app.chat.control_plane_trace import build_control_plane_trace

    monkeypatch.setattr(settings, "control_plane_enabled", True)
    final_state = _compiled_chat_graph_cp().invoke(
        {
            "request": ChatRequest(message=QUERY),
            "session_role": None,
            "mcp_recipe_id": "hunt_baseline",
        },
        {"recursion_limit": MAX_MCP_HOPS * 2 + 30},
    )
    trace = build_control_plane_trace(final_state)
    calls = trace.get("mcp_calls")
    assert isinstance(calls, list) and len(calls) >= 1
    assert calls[0]["call_id"] == "c1_discovery"
    assert calls[0]["call_class"] == "metadata_discovery"
    assert trace.get("mcp_loop") is not None
