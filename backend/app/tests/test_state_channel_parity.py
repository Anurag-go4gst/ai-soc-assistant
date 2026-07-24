"""Plan 5.2 — LangGraph state-channel integrity + CanonicalFacts path parity.

Audit table (ChatPipelineState channels required for spine / gate / dispatch):
| Channel               | Writer(s)                                      | Risk if undeclared        |
|-----------------------|------------------------------------------------|---------------------------|
| canonical_facts       | attach_canonical_facts_to_state (finalize)     | Spine dropped on graph    |
| final_evidence_gate   | graph_node_context_finalize, handoff finalize  | Gate trace inconsistent   |
| plan_dispatch_trace   | execute_plan_dispatch, planner executor        | Dispatch trace missing    |
| intent_dispatch       | graph_node_query_to_intent (Phase 1A)          | Already declared          |

LangGraph ``StateGraph(ChatPipelineState)`` silently drops keys not on the TypedDict.
Item 12b: regression uses the Resource Planner graph as production authority (not
linear ``chat_workflow`` imperative-vs-langgraph parity).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from app.chat.contracts.canonical_facts import CanonicalFacts
from app.chat.pipeline import ChatPipelineState
from app.evals.sentinel_eval import load_sentinel_rows, sentinel_runtime
from app.graph.resource_planner_graph import (
    _compiled_resource_planner_graph,
    run_chat_via_resource_planner_graph,
)
from app.schemas.requests import ChatRequest

_PIPELINE_PATH = Path(__file__).resolve().parents[1] / "chat" / "pipeline.py"
_PHASE52_CHANNELS = ("canonical_facts", "final_evidence_gate", "plan_dispatch_trace", "decision_log")
_VOLATILE_PAYLOAD_KEYS = frozenset({"evidence_id", "source_refs", "fact_id"})


def _stable_canonical_facts_signature(raw: dict[str, Any] | None) -> tuple[Any, ...]:
    if not isinstance(raw, dict):
        return ("missing",)
    facts = CanonicalFacts.model_validate(raw)
    rows: list[tuple[str, str, str, str]] = []
    for fact in facts.facts:
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
def test_canonical_facts_present_on_resource_planner_graph(row) -> None:
    """Item 12b batch-1: CanonicalFacts spine is attached on RP graph responses."""
    with sentinel_runtime():
        response = run_chat_via_resource_planner_graph(ChatRequest(message=row["question"]))

    assert _stable_canonical_facts_signature(response.canonical_facts)[0] != "missing", row["key"]


def test_resource_planner_final_state_retains_decision_log_channel() -> None:
    from app.chat.decision_record import emit_decision_record
    from app.planner.planner_hierarchy import DecisionRecord

    row = load_sentinel_rows()[0]
    with sentinel_runtime():
        graph = _compiled_resource_planner_graph()
        seeded = emit_decision_record(
            {"request": ChatRequest(message=row["question"])},
            DecisionRecord(
                record_id="dr:parity",
                node="test.seed",
                authority="test",
                decision_reason="parity_probe",
                inputs_ref=["request"],
                outputs_ref=["response"],
            ),
        )
        final_state = graph.invoke(seeded)

    log = final_state.get("decision_log")
    assert isinstance(log, list) and log
    assert log[0]["record_id"] == "dr:parity"


def test_resource_planner_final_state_retains_canonical_facts_channel() -> None:
    row = load_sentinel_rows()[0]
    with sentinel_runtime():
        final_state = _compiled_resource_planner_graph().invoke(
            {"request": ChatRequest(message=row["question"])},
        )

    assert isinstance(final_state.get("canonical_facts"), dict)
    response = final_state.get("response")
    assert response is not None
    assert _stable_canonical_facts_signature(final_state.get("canonical_facts")) == _stable_canonical_facts_signature(
        response.canonical_facts
    )
