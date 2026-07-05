"""Phase 6b — executor imperative parity for six representative request_modes.

Locks that ``imperative_hook_schedule_from_state`` + executor append rules match
``build_pipeline_dispatch`` stage order, and that ``advance_dispatch_cursor``
records the full scheduled stage path (cursor trace parity).
"""

from __future__ import annotations

from typing import Any

import pytest

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.contracts.pipeline_dispatch import (
    PipelineStage,
    imperative_hook_schedule_from_state,
)
from app.chat.pipeline import advance_dispatch_cursor
from app.chat.pipeline_dispatch_builder import build_pipeline_dispatch
from app.planner.executor import DispatchHooks, _legacy_predicate_dispatch_schedule


def _plan(**over: Any) -> EvidencePlan:
    base = dict(
        answer_mode="rag_only",
        rag_phase="rag_only",
        needs_rag=False,
        needs_spl=False,
        needs_mcp=False,
        needs_mitre=False,
        spl_allowed=False,
        mcp_allowed=False,
        policy_context_required=False,
        policy_context_recommended=False,
    )
    base.update(over)
    return EvidencePlan(**base)


def _executor_hooks(state: dict[str, Any], hooks: DispatchHooks) -> list[str]:
    return _legacy_predicate_dispatch_schedule(state, hooks, set())


def _noop_hooks() -> DispatchHooks:
    return DispatchHooks(
        uses_rag_only_path=lambda _s: False,
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


def _walk_cursor_path(state: dict[str, Any]) -> list[str]:
    decision = state["pipeline_dispatch"]["decision"]
    schedule = [PipelineStage(s) for s in decision.get("stage_schedule") or []]
    out = state
    for stage in schedule:
        out = advance_dispatch_cursor(out, stage)
    rc = out["pipeline_dispatch"]["runtime_context"]
    return list((rc.get("scheduling_trace") or {}).get("cursor_path") or [])


def _dispatch_state(
    monkeypatch: pytest.MonkeyPatch,
    plan: EvidencePlan,
    family: str,
    *,
    llm_spl: bool = False,
    mcp_discovery: bool = False,
) -> dict[str, Any]:
    monkeypatch.setattr("app.config.settings.ai_soc_pipeline_dispatch_v2_enabled", True)
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_pipeline_dispatch_v2_enabled", True)
    if llm_spl:
        monkeypatch.setattr("app.chat.pipeline_dispatch_builder.settings.ai_soc_llm_spl_fallback_enabled", True)
    if mcp_discovery:
        monkeypatch.setattr("app.chat.pipeline_dispatch_builder.settings.mcp_discovery_enabled", True)
    dispatch = build_pipeline_dispatch(
        evidence_plan=plan.model_dump(),
        intent_classification={"intent_family": family},
    )
    return {
        "pipeline_dispatch": dispatch.model_dump(mode="json"),
        "evidence_plan": plan.model_dump(),
        "planning_decision": {"path_type": "spl_generation"},
    }


@pytest.mark.parametrize(
    "label,plan_kwargs,family,llm_spl,mcp_discovery,expected_hooks",
    [
        (
            "mitre_knowledge",
            {"answer_mode": "rag_only", "needs_rag": True, "needs_mitre": True},
            "mitre_explanation",
            False,
            False,
            ["prepare_rag_only", "rag_early"],
        ),
        (
            "cve_review",
            {"needs_rag": True},
            "cve_investigation",
            False,
            False,
            ["prepare_rag_only", "rag_early"],
        ),
        (
            "knowledge",
            {"answer_mode": "rag_only", "needs_rag": True},
            "sop_or_playbook",
            False,
            False,
            ["prepare_rag_only", "rag_early"],
        ),
        (
            "spl_authoring",
            {
                "answer_mode": "live_investigation",
                "needs_spl": True,
                "spl_allowed": True,
                "normalized_slot_summary": {
                    "normalized_slots": {"index": "pgcil_soc", "sourcetype": "wineventlog"},
                    "unbound_constraints": [],
                },
            },
            "spl_generation_only",
            True,
            False,
            ["workflow_spl", "spl_postprocessor", "spl_source_resolve", "execution"],
        ),
        (
            "hybrid",
            {
                "answer_mode": "hybrid",
                "needs_rag": True,
                "needs_spl": True,
                "spl_allowed": True,
                "needs_mitre": True,
                "normalized_slot_summary": {
                    "normalized_slots": {"index": "pgcil_soc", "sourcetype": "wineventlog"},
                    "unbound_constraints": [],
                },
            },
            "hybrid_alert_review",
            False,
            False,
            ["prepare_rag_only", "rag_early", "workflow_spl", "spl_postprocessor", "spl_source_resolve", "execution"],
        ),
        (
            "spl_and_run_pre_spl",
            {
                "answer_mode": "live_investigation",
                "needs_spl": True,
                "spl_allowed": True,
                "needs_mcp": True,
                "mcp_allowed": True,
                "normalized_slot_summary": {
                    "normalized_slots": {},
                    "unbound_constraints": [{"slot": "index"}],
                },
            },
            "spl_generation_and_run",
            False,
            True,
            ["workflow_spl", "spl_postprocessor", "spl_source_resolve", "execution"],
        ),
    ],
)
def test_executor_schedule_matches_dispatch_v2_for_request_mode(
    monkeypatch: pytest.MonkeyPatch,
    label: str,
    plan_kwargs: dict[str, Any],
    family: str,
    llm_spl: bool,
    mcp_discovery: bool,
    expected_hooks: list[str],
) -> None:
    state = _dispatch_state(
        monkeypatch,
        _plan(**plan_kwargs),
        family,
        llm_spl=llm_spl,
        mcp_discovery=mcp_discovery,
    )
    hooks = _executor_hooks(state, _noop_hooks())
    assert hooks == expected_hooks, label
    mapped = imperative_hook_schedule_from_state(state)
    assert mapped is not None
    rag_only = bool(
        mapped
        and "workflow_spl" not in mapped
        and all(h in {"prepare_rag_only", "rag_early"} for h in mapped)
    )
    expected_mapped = mapped if rag_only else [*mapped, "execution"] if "execution" not in mapped else mapped
    assert hooks == expected_mapped, label


@pytest.mark.parametrize(
    "label,plan_kwargs,family,llm_spl,mcp_discovery",
    [
        ("mitre_knowledge", {"answer_mode": "rag_only", "needs_rag": True, "needs_mitre": True}, "mitre_explanation", False, False),
        ("cve_review", {"needs_rag": True}, "cve_investigation", False, False),
        ("knowledge", {"answer_mode": "rag_only", "needs_rag": True}, "sop_or_playbook", False, False),
        (
            "spl_authoring",
            {
                "answer_mode": "live_investigation",
                "needs_spl": True,
                "spl_allowed": True,
                "normalized_slot_summary": {
                    "normalized_slots": {"index": "pgcil_soc", "sourcetype": "wineventlog"},
                    "unbound_constraints": [],
                },
            },
            "spl_generation_only",
            True,
            False,
        ),
        (
            "hybrid",
            {
                "answer_mode": "hybrid",
                "needs_rag": True,
                "needs_spl": True,
                "spl_allowed": True,
                "needs_mitre": True,
                "normalized_slot_summary": {
                    "normalized_slots": {"index": "pgcil_soc", "sourcetype": "wineventlog"},
                    "unbound_constraints": [],
                },
            },
            "hybrid_alert_review",
            False,
            False,
        ),
        (
            "spl_and_run_pre_spl",
            {
                "answer_mode": "live_investigation",
                "needs_spl": True,
                "spl_allowed": True,
                "needs_mcp": True,
                "mcp_allowed": True,
                "normalized_slot_summary": {
                    "normalized_slots": {},
                    "unbound_constraints": [{"slot": "index"}],
                },
            },
            "spl_generation_and_run",
            False,
            True,
        ),
    ],
)
def test_cursor_path_records_full_stage_schedule_order(
    monkeypatch: pytest.MonkeyPatch,
    label: str,
    plan_kwargs: dict[str, Any],
    family: str,
    llm_spl: bool,
    mcp_discovery: bool,
) -> None:
    state = _dispatch_state(
        monkeypatch,
        _plan(**plan_kwargs),
        family,
        llm_spl=llm_spl,
        mcp_discovery=mcp_discovery,
    )
    decision = state["pipeline_dispatch"]["decision"]
    expected = list(decision["stage_schedule"])
    cursor_path = _walk_cursor_path(state)
    assert cursor_path == expected, label


def test_execute_plan_dispatch_calls_match_v2_schedule(monkeypatch: pytest.MonkeyPatch) -> None:
    """Imperative executor call order matches dispatch v2 hook schedule."""
    from app.planner.executor import execute_plan_dispatch

    state = _dispatch_state(
        monkeypatch,
        _plan(
            answer_mode="live_investigation",
            needs_spl=True,
            spl_allowed=True,
            normalized_slot_summary={
                "normalized_slots": {"index": "pgcil_soc", "sourcetype": "wineventlog"},
                "unbound_constraints": [],
            },
        ),
        "spl_generation_only",
        llm_spl=True,
    )
    calls: list[str] = []

    def node(name: str):
        def run(s: dict) -> dict:
            calls.append(name)
            if name == "workflow_spl":
                return {**s, "workflow_plan": {"skill": "spl_generation"}}
            return s

        return run

    hooks = DispatchHooks(
        uses_rag_only_path=lambda _s: False,
        uses_pre_mcp_rag=lambda _s: False,
        prepare_rag_only=node("prepare_rag_only"),
        rag_early=node("rag_early"),
        spl_source_resolve=node("spl_source_resolve"),
        workflow_spl=node("workflow_spl"),
        spl_postprocessor=node("spl_postprocessor"),
        ensure_workflow_plan=node("ensure_workflow_plan"),
        reference_finalize=node("reference_finalize"),
        execution=node("execution"),
    )
    expected = _executor_hooks(state, hooks)
    execute_plan_dispatch(state, hooks)
    assert calls == expected
