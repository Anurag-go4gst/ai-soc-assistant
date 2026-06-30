"""Phase 6c — dedicated spl_postprocessor node; no double-apply when v2 on."""

from __future__ import annotations

import pytest

from app.chat.contracts.pipeline_dispatch import PipelineStage
from app.chat.pipeline import (
    _defer_spl_postprocessor_inline,
    graph_node_spl_postprocessor,
)


def _spl_state(monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_pipeline_dispatch_v2_enabled", True)
    return {
        "request": type("R", (), {"message": "outbound spike from 10.0.0.5"})(),
        "routed": {"skill": "spl_generation", "tool_plan": []},
        "trace_id": "t-6c",
        "pipeline_dispatch": {
            "decision": {
                "request_mode": "spl_authoring",
                "stage_schedule": [
                    PipelineStage.workflow_spl.value,
                    PipelineStage.spl_postprocessor.value,
                    PipelineStage.spl_source_resolve.value,
                ],
                "llm_hops": [],
            },
            "runtime_context": {"dispatch_cursor": None, "scheduling_trace": {}},
        },
        "candidate_spl": {
            "candidate_spl": "index=foo | head 100",
            "generation_mode": "deterministic_lab_draft",
            "detection_family": "auth_failed_login_threshold",
        },
        "spl_validation": {"approved": False, "normalized_spl": None},
    }


def test_defer_inline_when_dispatch_v2_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_pipeline_dispatch_v2_enabled", False)
    assert _defer_spl_postprocessor_inline() is False
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_pipeline_dispatch_v2_enabled", True)
    assert _defer_spl_postprocessor_inline() is True


def test_dedicated_node_applies_postprocessor_once(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _spl_state(monkeypatch)
    rc = state["pipeline_dispatch"]["runtime_context"]
    rc["dispatch_cursor"] = PipelineStage.workflow_spl.value
    rc["scheduling_trace"] = {"cursor_path": [PipelineStage.workflow_spl.value]}
    assert (state["candidate_spl"].get("review_only_spl_postprocessor_trace") or {}) == {}
    out = graph_node_spl_postprocessor(state)
    trace = (out["candidate_spl"] or {}).get("review_only_spl_postprocessor_trace") or {}
    assert trace.get("postprocessor_evaluated") is True
    path = out["pipeline_dispatch"]["runtime_context"]["scheduling_trace"]["cursor_path"]
    assert path == [
        PipelineStage.workflow_spl.value,
        PipelineStage.spl_postprocessor.value,
    ]


def test_workflow_spl_cursor_stops_before_postprocessor_when_deferred(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After workflow_spl cursor advance, postprocessor cursor waits for dedicated node."""
    from app.chat.pipeline import advance_dispatch_cursor

    state = _spl_state(monkeypatch)
    out = advance_dispatch_cursor(state, PipelineStage.workflow_spl)
    rc = out["pipeline_dispatch"]["runtime_context"]
    assert rc.get("dispatch_cursor") == PipelineStage.workflow_spl.value
    path = (rc.get("scheduling_trace") or {}).get("cursor_path") or []
    assert path == [PipelineStage.workflow_spl.value]
    assert PipelineStage.spl_postprocessor.value not in path
