"""Stage 4B — the governed evidence-collection loop wired into LangGraph.

CP off: linear parity graph, no loop. CP on: evidence_planning HUB drives
read-only mcp_call discovery hops (bounded) before the linear chain.
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.chat.evidence_loop import MAX_MCP_HOPS
from app.graph.chat_workflow import (
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
    assert ("evidence_planning", "shadow_enrichment") in edges
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
    from app.graph.chat_workflow import _hub_route

    # Execution re-entry: the stored assessor verdict drives the edge.
    assert _hub_route({"execution": {}, "mcp_loop": {"route": ROUTE_BROADEN}}) == "context_finalize"
    # Discovery re-entry with a pending hop routes to the read-only mcp_call node.
    assert (
        _hub_route({"mcp_chronology": ["splunk_get_info"], "mcp_loop": {"route": ROUTE_DISCOVERY_HOP}})
        == "mcp_call"
    )
    # Discovery exhausted → enter the linear chain once.
    assert _hub_route({"mcp_chronology": [], "mcp_loop": {"route": "execute"}}) == "shadow_enrichment"


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
        assert hop["outcome"] == "planned"
        assert hop["tool"] != "splunk_run_query"


def test_cp_off_parity_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", False)
    response = run_chat_via_langgraph(ChatRequest(message=QUERY))
    assert response is not None
    # No loop state leaks onto the linear path.
    final_state = _compiled_chat_graph().invoke({"request": ChatRequest(message=QUERY)})
    assert "mcp_chronology" not in final_state
