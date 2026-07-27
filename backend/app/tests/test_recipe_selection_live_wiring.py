"""Item 3.4 — live invocation of select_recipe_for_plan (2026-07-03).

Items 3.1-3.3 built and langgraph-verified the whole O5c mechanism but left
it 100% dormant: nothing ever called select_recipe_for_plan (item 3.2) from
the live evidence-planning path. This item wires that call in
graph_node_evidence_planning, scoped to out_of_registry/near_105_question
match paths ONLY — the same _TRIGGER_MATCH_PATHS set llm_plan_bridge.py
already uses for the identical reason: this plan is about out-of-catalogue
resource planning, and sweeping in-catalogue traffic into the newer,
less-proven recipe/O5c dispatch mechanism broke 5 pinned tests when tried
unscoped (recorded in the plan's Drift log).
"""

from __future__ import annotations

import os

import pytest

from app.chat import pipeline as pl
from app.config import settings


@pytest.fixture
def _mock_execution_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_MODE", "mock")
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")


def test_in_catalogue_query_never_recipe_routed(_mock_execution_enabled, monkeypatch: pytest.MonkeyPatch) -> None:
    """The exact query test_evidence_loop_graph.py's chronology-path tests pin
    — proves the scoping fix holds, not just that it once worked."""
    from app.chat.linear_graph_legacy import _compiled_chat_graph_cp
    from app.schemas.requests import ChatRequest

    final_state = _compiled_chat_graph_cp().invoke(
        {
            "request": ChatRequest(message="show failed admin logins in the last 24 hours"),
            "session_role": None,
            "legacy_langgraph_harness": True,
        },
        {"recursion_limit": 60},
    )
    assert final_state.get("mcp_recipe_id") is None
    assert isinstance(final_state.get("mcp_chronology"), list)


def test_out_of_registry_hunt_shape_with_grant_selects_a_recipe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolates the new wiring block directly: with match_path/shape/grant all
    satisfied, graph_node_evidence_planning must set mcp_recipe_id. Monkeypatches
    the two boundary functions rather than hunting for a natural-language query
    that happens to satisfy match_path + mcp_allowed + hunt shape simultaneously
    (independently verified as hard to construct — real queries tried during
    development landed on other shapes or in-catalogue match paths)."""
    monkeypatch.setattr(pl, "_match_path_from_state", lambda state: "out_of_registry")

    class _FakeShape:
        primary_shape = "hunt"

    monkeypatch.setattr(pl, "classify_answer_shape", lambda query, resource_plan=None: _FakeShape())
    monkeypatch.setattr(pl, "_mcp_evidence_loop_enabled", lambda state, evidence_payload: True)
    monkeypatch.setattr(pl, "plan_path_and_tools", lambda **kwargs: type("P", (), {"model_dump": lambda self: {}})())

    from app.schemas.requests import ChatRequest

    state = {
        "request": ChatRequest(message="hunt-shaped out-of-registry probe"),
        "trace_id": "test-3.4",
        "legacy_langgraph_harness": True,
        "intent_classification": {
            "intent_family": "spl_generation_only",
            "primary_intent": "ask_for_query_generation",
            "query_type": "ask_for_query_generation",
            "answer_goal": ["spl_artifact"],
            "confidence": 0.9,
            "confidence_band": "high",
            "requires_clarification": False,
            "reason": "test",
        },
        "query_to_intent": {"query_signals": {"live_data_request": True}},
    }
    result = pl.graph_node_evidence_planning(state)
    assert result.get("mcp_recipe_id") == "hunt_baseline"
    assert isinstance(result.get("mcp_call_records"), list)
    assert isinstance(result.get("mcp_loop"), dict)


def test_out_of_registry_without_grant_selects_no_recipe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pl, "_match_path_from_state", lambda state: "out_of_registry")

    class _FakeShape:
        primary_shape = "hunt"

    monkeypatch.setattr(pl, "classify_answer_shape", lambda query, resource_plan=None: _FakeShape())
    monkeypatch.setattr(pl, "_mcp_evidence_loop_enabled", lambda state, evidence_payload: True)
    monkeypatch.setattr(pl, "plan_path_and_tools", lambda **kwargs: type("P", (), {"model_dump": lambda self: {}})())

    from app.schemas.requests import ChatRequest

    state = {
        "request": ChatRequest(message="rag-only out-of-registry probe"),
        "trace_id": "test-3.4b",
        "legacy_langgraph_harness": True,
        "intent_classification": {
            "intent_family": "knowledge_only",
            "primary_intent": "ask_for_explanation",
            "query_type": "ask_for_explanation",
            "answer_goal": ["procedural_steps"],
            "confidence": 0.9,
            "confidence_band": "high",
            "requires_clarification": False,
            "reason": "test",
        },
    }
    result = pl.graph_node_evidence_planning(state)
    assert result.get("mcp_recipe_id") is None


def test_natural_hunt_query_recipe_routes_without_matchpath_monkeypatch(
    _mock_execution_enabled, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression for the 2026-07-04 fix: _match_path_from_state(state) returns
    None at the wiring point on first entry (evidence_plan/planning_decision are
    still local payloads; routing_provenance uses deterministic_match_path), so
    the earlier monkeypatched test masked a wiring block that never fired on any
    live turn. This drives the REAL compiled langgraph with a natural hunt query
    and no match-path monkeypatch — the match path must come from the composed
    plan's own provenance."""
    from app.chat.linear_graph_legacy import _compiled_chat_graph_cp
    from app.schemas.requests import ChatRequest

    final_state = _compiled_chat_graph_cp().invoke(
        {
            "request": ChatRequest(
                message=(
                    "Hunt for unusual outbound connections from our OT engineering "
                    "workstations to rare external destinations in the last 24 hours"
                )
            ),
            "session_role": None,
            "legacy_langgraph_harness": True,
        },
        {"recursion_limit": 60},
    )
    assert final_state.get("mcp_recipe_id") == "hunt_baseline"
    records = final_state.get("mcp_call_records")
    assert isinstance(records, list) and records, "recipe call records must be populated"
