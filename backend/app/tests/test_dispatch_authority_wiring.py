"""REV5-A — runtime reads pipeline_dispatch via project_dispatch_flags."""

from __future__ import annotations

import pytest

from app.chat.contracts.pipeline_dispatch import (
    LlmHop,
    PipelineDispatchContract,
    PipelineStage,
    imperative_hook_schedule_from_state,
    projected_flags_from_state,
    project_dispatch_flags,
)
from app.chat.pipeline import _should_use_llm_spl_failover, _run_legacy_dispatch_fallback
from app.planner.executor import _legacy_predicate_dispatch_schedule
from app.planner.executor import DispatchHooks


def _state(*, schedule: list[PipelineStage], hops: list[LlmHop] | None = None) -> dict:
    decision = PipelineDispatchContract(
        request_mode="spl_authoring",
        stage_schedule=schedule,
        llm_hops=hops or [],
    )
    return {
        "pipeline_dispatch": {
            "decision": decision.model_dump(mode="json"),
            "runtime_context": {},
        },
        "evidence_plan": {"needs_spl": True, "needs_rag": False},
        "planning_decision": {"path_type": "spl_generation"},
        "request": type("R", (), {"message": "test"})(),
        "routed": {"skill": "spl_generation", "tool_plan": []},
        "trace_id": "t-rev5a",
    }


def test_projected_flags_from_state_requires_v2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.ai_soc_pipeline_dispatch_v2_enabled", False)
    assert projected_flags_from_state(_state(schedule=[PipelineStage.workflow_spl])) is None


def test_imperative_schedule_maps_stage_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.ai_soc_pipeline_dispatch_v2_enabled", True)
    state = _state(
        schedule=[
            PipelineStage.pre_spl_mcp_discovery,
            PipelineStage.workflow_spl,
            PipelineStage.spl_postprocessor,
            PipelineStage.spl_source_resolve,
        ]
    )
    assert imperative_hook_schedule_from_state(state) == [
        "workflow_spl",
        "spl_postprocessor",
        "spl_source_resolve",
    ]


def test_v2_projection_is_fenced_when_resource_plan_authority_is_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.settings.ai_soc_pipeline_dispatch_v2_enabled", True)
    monkeypatch.setattr("app.config.settings.ai_soc_resource_plan_execution_enabled", True)
    state = _state(schedule=[PipelineStage.workflow_spl])
    assert projected_flags_from_state(state) is None
    assert imperative_hook_schedule_from_state(state) is None


def test_should_use_llm_spl_failover_reads_dispatch_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_pipeline_dispatch_v2_enabled", True)
    flags = project_dispatch_flags(
        PipelineDispatchContract(
            request_mode="spl_authoring",
            stage_schedule=[PipelineStage.workflow_spl],
            llm_hops=[LlmHop.spl_plan_compiler],
        )
    )
    assert _should_use_llm_spl_failover("spl_generation", dispatch_flags=flags) is True
    flags_off = dict(flags)
    flags_off["call_spl_llm"] = False
    assert _should_use_llm_spl_failover("spl_generation", dispatch_flags=flags_off) is False


def test_legacy_executor_schedule_uses_dispatch_v2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.ai_soc_pipeline_dispatch_v2_enabled", True)
    state = _state(schedule=[PipelineStage.rag_early])
    hooks = DispatchHooks(
        uses_rag_only_path=lambda _s: True,
        uses_pre_mcp_rag=lambda _s: False,
        prepare_rag_only=lambda s: s,
        rag_early=lambda s: s,
        spl_source_resolve=lambda s: s,
        workflow_spl=lambda s: s,
        spl_postprocessor=lambda s: s,
        ensure_workflow_plan=lambda s: s,
        reference_finalize=lambda s: s,
        execution=lambda s: s,
    )
    schedule = _legacy_predicate_dispatch_schedule(state, hooks, set())
    assert schedule == ["prepare_rag_only", "rag_early"]


def test_legacy_dispatch_fallback_uses_v2_hooks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_pipeline_dispatch_v2_enabled", True)
    monkeypatch.setattr("app.config.settings.ai_soc_pipeline_dispatch_v2_enabled", True)
    calls: list[str] = []

    def _mark(name: str):
        def _node(state: dict) -> dict:
            calls.append(name)
            return state

        return _node

    import app.chat.pipeline as pl

    monkeypatch.setattr(pl, "graph_node_workflow_spl", _mark("workflow_spl"))
    monkeypatch.setattr(pl, "graph_node_spl_source_resolve", _mark("spl_source_resolve"))
    monkeypatch.setattr(pl, "graph_node_execution", _mark("execution"))
    monkeypatch.setattr(pl, "graph_node_prepare_rag_only", _mark("prepare_rag_only"))
    monkeypatch.setattr(pl, "graph_node_rag_early", _mark("rag_early"))

    state = _state(
        schedule=[PipelineStage.workflow_spl, PipelineStage.spl_source_resolve],
    )
    out = _run_legacy_dispatch_fallback(state, dispatch_source="test")
    assert out["plan_dispatch_trace"]["dispatch_authority"] == "pipeline_dispatch_v2"
    assert calls == ["workflow_spl", "spl_source_resolve", "execution"]


def test_build_plan_dispatch_trace_from_pipeline_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.chat.contracts.pipeline_dispatch import (
        LlmHop,
        build_plan_dispatch_trace_from_pipeline_dispatch,
    )

    monkeypatch.setattr("app.config.settings.ai_soc_pipeline_dispatch_v2_enabled", True)
    state = _state(
        schedule=[PipelineStage.pre_spl_mcp_discovery, PipelineStage.workflow_spl, PipelineStage.spl_postprocessor],
        hops=[LlmHop.spl_plan_compiler],
    )
    trace = build_plan_dispatch_trace_from_pipeline_dispatch(state)
    assert trace is not None
    assert trace["dispatch_authority"] == "pipeline_dispatch_v2"
    assert trace["dispatch_schedule"] == ["workflow_spl", "spl_postprocessor", "execution"]
    assert trace["projected_flags"]["call_spl_llm"] is True
