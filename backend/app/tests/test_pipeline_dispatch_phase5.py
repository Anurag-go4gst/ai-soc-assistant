"""Phase 5 — pre-SPL MCP discovery node."""

from __future__ import annotations

import pytest

from app.chat.contracts.pipeline_dispatch import PipelineStage
from app.chat.pipeline import graph_node_pre_spl_mcp_discovery


def _state_with_schedule(schedule: list[str], cursor: str | None = None) -> dict:
    return {
        "pipeline_dispatch": {
            "decision": {"stage_schedule": schedule, "slot_handoff": {"normalized_slots": {}}},
            "runtime_context": {"dispatch_cursor": cursor},
        }
    }


def test_noop_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.chat.pipeline.settings.ai_soc_pipeline_dispatch_v2_enabled", False
    )
    state = _state_with_schedule([PipelineStage.pre_spl_mcp_discovery.value])
    assert graph_node_pre_spl_mcp_discovery(state) is state


def test_noop_when_pre_spl_not_next(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_pipeline_dispatch_v2_enabled", True)
    monkeypatch.setattr("app.chat.pipeline.settings.mcp_discovery_enabled", True)
    state = _state_with_schedule([PipelineStage.workflow_spl.value])
    assert graph_node_pre_spl_mcp_discovery(state) is state


def test_runs_discovery_and_writes_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_pipeline_dispatch_v2_enabled", True)
    monkeypatch.setattr("app.chat.pipeline.settings.mcp_discovery_enabled", True)
    monkeypatch.setattr(
        "app.chat.pipeline.run_mcp_source_discovery",
        lambda **_kw: ({"index": "pgcil_soc", "sourcetype": "wineventlog"}, {"tools_called": ["splunk_get_indexes"]}),
    )
    state = _state_with_schedule([PipelineStage.pre_spl_mcp_discovery.value, PipelineStage.workflow_spl.value])
    out = graph_node_pre_spl_mcp_discovery(state)
    rc = out["pipeline_dispatch"]["runtime_context"]
    assert rc["mcp_discovery_context"]["indexes"] == ["pgcil_soc"]
    assert rc["mcp_discovery_context"]["sourcetypes"] == ["wineventlog"]
    assert rc["dispatch_cursor"] == PipelineStage.pre_spl_mcp_discovery.value
    assert rc["mcp_phase"] == "pre_spl"


def test_discovery_failure_records_skip_and_advances_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_pipeline_dispatch_v2_enabled", True)
    monkeypatch.setattr("app.chat.pipeline.settings.mcp_discovery_enabled", True)

    def _boom(**_kw):
        raise RuntimeError("connector down")

    monkeypatch.setattr("app.chat.pipeline.run_mcp_source_discovery", _boom)
    state = _state_with_schedule(
        [PipelineStage.pre_spl_mcp_discovery.value, PipelineStage.workflow_spl.value]
    )
    out = graph_node_pre_spl_mcp_discovery(state)
    rc = out["pipeline_dispatch"]["runtime_context"]
    assert rc["dispatch_cursor"] == PipelineStage.pre_spl_mcp_discovery.value
    assert rc["scheduling_trace"]["skipped_stages"][-1]["reason"] == "discovery_failed"
    assert rc["scheduling_trace"]["cursor_path"] == [PipelineStage.pre_spl_mcp_discovery.value]


def test_mcp_discovery_disabled_records_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_pipeline_dispatch_v2_enabled", True)
    monkeypatch.setattr("app.chat.pipeline.settings.mcp_discovery_enabled", False)
    state = _state_with_schedule(
        [PipelineStage.pre_spl_mcp_discovery.value, PipelineStage.workflow_spl.value]
    )
    out = graph_node_pre_spl_mcp_discovery(state)
    rc = out["pipeline_dispatch"]["runtime_context"]
    assert rc["scheduling_trace"]["skipped_stages"][-1]["reason"] == "mcp_discovery_disabled"
    assert rc["dispatch_cursor"] == PipelineStage.pre_spl_mcp_discovery.value
