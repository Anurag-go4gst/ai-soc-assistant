"""Plan 5.2 — LangGraph state-channel integrity + CanonicalFacts path parity.

Audit table (ChatPipelineState channels required for spine / gate / dispatch):
| Channel               | Writer(s)                                      | Risk if undeclared        |
|-----------------------|------------------------------------------------|---------------------------|
| canonical_facts       | attach_canonical_facts_to_state (finalize)     | Spine dropped on graph    |
| final_evidence_gate   | graph_node_context_finalize, handoff finalize  | Gate trace inconsistent   |
| plan_dispatch_trace   | execute_plan_dispatch, planner executor        | Dispatch trace missing    |
| intent_dispatch       | graph_node_query_to_intent (Phase 1A)          | Already declared          |

LangGraph ``StateGraph(ChatPipelineState)`` silently drops keys not on the TypedDict.
Regression: imperative ``build_live_chat_response`` vs ``run_chat_via_langgraph`` must
yield identical CanonicalFacts on the same query after normalizing volatile ids.

Known dispatch divergence (pre-existing, not 5.2): imperative ``plan_dispatch`` populates
``mcp_evidence`` while the linear LangGraph graph uses ``composed_dispatch``; parity
tests exclude ``executed_evidence`` facts harvested from ``mcp_execution`` only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from app.chat.contracts.canonical_facts import CanonicalFacts
from app.chat.pipeline import ChatPipelineState, build_live_chat_response
from app.evals.sentinel_eval import load_sentinel_rows, sentinel_runtime
from app.graph.chat_workflow import run_chat_via_langgraph
from app.schemas.requests import ChatRequest

_PIPELINE_PATH = Path(__file__).resolve().parents[1] / "chat" / "pipeline.py"
_PHASE52_CHANNELS = ("canonical_facts", "final_evidence_gate", "plan_dispatch_trace")
_VOLATILE_PAYLOAD_KEYS = frozenset({"evidence_id", "source_refs", "fact_id"})


def _stable_canonical_facts_signature(raw: dict[str, Any] | None) -> tuple[Any, ...]:
    if not isinstance(raw, dict):
        return ("missing",)
    facts = CanonicalFacts.model_validate(raw)
    rows: list[tuple[str, str, str, str]] = []
    for fact in facts.facts:
        # Imperative plan_dispatch may harvest mcp_evidence the linear graph path lacks.
        if fact.kind == "executed_evidence" and fact.provenance.node == "mcp_execution":
            continue
        payload = {key: value for key, value in fact.payload.items() if key not in _VOLATILE_PAYLOAD_KEYS}
        rows.append(
            (
                fact.kind,
                json.dumps(payload, sort_keys=True, default=str),
                fact.provenance.node,
                fact.provenance.evidence_class,
            )
        )
    rows.sort()
    return (facts.schema_version, facts.authority_holder, tuple(rows))


def _state_write_keys_from_pipeline() -> set[str]:
    text = _PIPELINE_PATH.read_text(encoding="utf-8")
    keys: set[str] = set()
    for pattern in (
        r'\{\*\*state,\s*"([a-z_][a-z0-9_]*)"\s*:',
        r'state\s*=\s*\{\*\*state,\s*"([a-z_][a-z0-9_]*)"\s*:',
    ):
        keys.update(re.findall(pattern, text))
    return keys


def test_phase52_spine_channels_declared_on_chat_pipeline_state() -> None:
    annotations = ChatPipelineState.__annotations__
    for channel in _PHASE52_CHANNELS:
        assert channel in annotations, f"missing ChatPipelineState channel: {channel}"


def test_pipeline_state_writes_are_declared_channels() -> None:
    """Every top-level ``{**state, "key": ...}`` write in pipeline.py is declared."""
    write_keys = _state_write_keys_from_pipeline()
    annotations = set(ChatPipelineState.__annotations__)
    undeclared = sorted(write_keys - annotations)
    assert not undeclared, f"undeclared pipeline state writes: {undeclared}"


@pytest.mark.parametrize("row", load_sentinel_rows()[:5], ids=lambda row: row["key"])
def test_canonical_facts_parity_imperative_vs_langgraph(row) -> None:
    message = row["question"]
    with sentinel_runtime():
        imperative = build_live_chat_response(ChatRequest(message=message))
        graph = run_chat_via_langgraph(ChatRequest(message=message))

    imp_sig = _stable_canonical_facts_signature(imperative.canonical_facts)
    graph_sig = _stable_canonical_facts_signature(graph.canonical_facts)
    assert imp_sig == graph_sig, row["key"]
    assert imp_sig[0] != "missing", row["key"]


def test_langgraph_final_state_retains_canonical_facts_channel() -> None:
    from app.graph.chat_workflow import _compiled_chat_graph

    row = load_sentinel_rows()[0]
    with sentinel_runtime():
        final_state = _compiled_chat_graph().invoke({"request": ChatRequest(message=row["question"])})

    assert isinstance(final_state.get("canonical_facts"), dict)
    response = final_state.get("response")
    assert response is not None
    assert _stable_canonical_facts_signature(final_state.get("canonical_facts")) == _stable_canonical_facts_signature(
        response.canonical_facts
    )
