"""Phase 6 — cursor-driven ordered progression + schedule parity.

The dedicated LangGraph node extraction (separate compiled spl_postprocessor /
pre_spl_mcp_discovery nodes + rerouted conditional edges) is deferred: the
LangGraph path is shadow/parity-only and the inline hooks (Phases 3–5) already
enforce stage ordering. These tests lock the cursor-routing LOGIC + exact stage
order so the deferred topology change has a contract to satisfy.
"""

from __future__ import annotations

from app.chat.contracts.pipeline_dispatch import (
    PipelineStage,
    next_stage_after,
)
from app.chat.pipeline import advance_dispatch_cursor


def _walk(schedule: list[PipelineStage]) -> list[PipelineStage]:
    """Walk next_stage_after from start to end, collecting the visited order."""
    order: list[PipelineStage] = []
    cursor: PipelineStage | None = None
    while True:
        nxt = next_stage_after(schedule, cursor)
        if nxt is None:
            break
        order.append(nxt)
        cursor = nxt
    return order


def test_next_stage_after_walks_full_spl_schedule_in_order() -> None:
    schedule = [
        PipelineStage.pre_spl_mcp_discovery,
        PipelineStage.workflow_spl,
        PipelineStage.spl_postprocessor,
        PipelineStage.spl_source_resolve,
        PipelineStage.mcp_execution,
    ]
    assert _walk(schedule) == schedule


def test_workflow_spl_must_be_followed_by_postprocessor() -> None:
    schedule = [
        PipelineStage.workflow_spl,
        PipelineStage.spl_postprocessor,
        PipelineStage.spl_source_resolve,
    ]
    assert next_stage_after(schedule, PipelineStage.workflow_spl) is PipelineStage.spl_postprocessor


def test_advance_cursor_forward_only_and_records_path(monkeypatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_pipeline_dispatch_v2_enabled", True)
    state = {
        "pipeline_dispatch": {
            "decision": {
                "stage_schedule": [
                    PipelineStage.workflow_spl.value,
                    PipelineStage.spl_postprocessor.value,
                    PipelineStage.spl_source_resolve.value,
                ]
            },
            "runtime_context": {"dispatch_cursor": None},
        }
    }
    state = advance_dispatch_cursor(state, PipelineStage.workflow_spl)
    state = advance_dispatch_cursor(state, PipelineStage.spl_postprocessor)
    # Rewind attempt is ignored (forward-only).
    state = advance_dispatch_cursor(state, PipelineStage.workflow_spl)
    rc = state["pipeline_dispatch"]["runtime_context"]
    assert rc["dispatch_cursor"] == PipelineStage.spl_postprocessor.value
    assert rc["scheduling_trace"]["cursor_path"] == [
        PipelineStage.workflow_spl.value,
        PipelineStage.spl_postprocessor.value,
    ]


def test_advance_cursor_noop_when_flag_off(monkeypatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_pipeline_dispatch_v2_enabled", False)
    state = {"pipeline_dispatch": {"decision": {"stage_schedule": [PipelineStage.workflow_spl.value]}, "runtime_context": {}}}
    assert advance_dispatch_cursor(state, PipelineStage.workflow_spl) is state


def test_advance_cursor_ignores_unscheduled_stage(monkeypatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_pipeline_dispatch_v2_enabled", True)
    state = {
        "pipeline_dispatch": {
            "decision": {"stage_schedule": [PipelineStage.workflow_spl.value]},
            "runtime_context": {"dispatch_cursor": None},
        }
    }
    out = advance_dispatch_cursor(state, PipelineStage.mcp_execution)
    assert out["pipeline_dispatch"]["runtime_context"].get("dispatch_cursor") is None
