"""Phase 6 — cursor-driven ordered progression + schedule parity.

Dedicated LangGraph nodes for spl_postprocessor / pre_spl_mcp_discovery remain
deferred; cursor-driven conditional routing is partially wired in
``chat_workflow._after_shadow_tail`` / ``_after_workflow_spl`` when dispatch v2
is on. Inline hooks in the imperative path enforce stage ordering. These tests
lock cursor-routing logic + exact stage order for the deferred topology change.
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


def test_cannot_skip_pre_spl_when_advancing_workflow_spl(monkeypatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_pipeline_dispatch_v2_enabled", True)
    state = {
        "pipeline_dispatch": {
            "decision": {
                "stage_schedule": [
                    PipelineStage.pre_spl_mcp_discovery.value,
                    PipelineStage.workflow_spl.value,
                    PipelineStage.spl_postprocessor.value,
                ]
            },
            "runtime_context": {"dispatch_cursor": None},
        }
    }
    out = advance_dispatch_cursor(state, PipelineStage.workflow_spl)
    assert out["pipeline_dispatch"]["runtime_context"].get("dispatch_cursor") is None


def test_dispatch_v2_route_after_shadow_tail_prefers_workflow_for_pre_spl(monkeypatch) -> None:
    from app.chat.pipeline import dispatch_v2_route_after_shadow_tail

    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_pipeline_dispatch_v2_enabled", True)
    state = {
        "pipeline_dispatch": {
            "decision": {
                "stage_schedule": [
                    PipelineStage.pre_spl_mcp_discovery.value,
                    PipelineStage.workflow_spl.value,
                ]
            },
            "runtime_context": {},
        }
    }
    assert dispatch_v2_route_after_shadow_tail(state) == "workflow_spl"
