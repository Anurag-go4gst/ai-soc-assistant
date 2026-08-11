"""Plan 2 C1-E4 — ResourcePlan-driven execution order wired into the one seam.

Both runtimes reach dispatch through `execute_plan_dispatch`, so the compiled
schedule is wired at `build_step_walk_dispatch_schedule` and nowhere else.
Flag-off must be exactly the fixed predicate schedule; flag-on must never move
a safety gate.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.chat.pipeline_dispatch_builder import build_pipeline_dispatch
from app.config import settings
from app.planner.executor import (
    DispatchHooks,
    _legacy_predicate_dispatch_schedule,
    build_plan_dispatch_trace,
    build_step_walk_dispatch_schedule,
    derive_dispatch_booleans_from_plan,
    execute_plan_dispatch,
    walk_plan_steps,
)
from app.query_understanding.parser import understand_query
from app.tests.support.legacy_planning_harness import with_committed_resource_plan

_PROBES = [
    ("Which users have excessive failed logins?", "attack_discovery"),
    ("Generate SPL for failed logins", "spl_generation"),
    ("What is our password policy for contractor accounts?", "knowledge_recall"),
    ("Which hosts are generating the most SMB traffic?", "attack_discovery"),
]


@pytest.fixture(autouse=True)
def _cp_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)


def _hooks(calls: list[str] | None = None, *, rag_only: bool = False, pre_mcp: bool = False):
    sink = calls if calls is not None else []

    def node(name: str):
        def run(state: dict[str, Any]) -> dict[str, Any]:
            sink.append(name)
            if name == "workflow_spl":
                return {**state, "workflow_plan": {"skill": "spl_generation"}}
            if name == "ensure_workflow_plan":
                return {**state, "workflow_plan": {"skill": "alert_summary"}}
            return state

        return run

    return DispatchHooks(
        uses_rag_only_path=lambda _s: rag_only,
        uses_pre_mcp_rag=lambda _s: pre_mcp,
        prepare_rag_only=node("prepare_rag_only"),
        rag_early=node("rag_early"),
        spl_source_resolve=node("spl_source_resolve"),
        workflow_spl=node("workflow_spl"),
        spl_postprocessor=node("spl_postprocessor"),
        ensure_workflow_plan=node("ensure_workflow_plan"),
        reference_finalize=node("reference_finalize"),
        execution=node("execution"),
    )


def _state_from_question(question: str, skill: str) -> dict[str, Any]:
    qu = understand_query(question)
    q2i = build_query_to_intent(query=question, query_understanding=qu, routed_skill=skill)
    intent = q2i.intent_classification.model_dump()
    plan = plan_evidence(
        intent,
        query_to_intent=q2i.model_dump(),
        query_understanding=qu,
        routed={"skill": skill},
    )
    payload = plan.model_dump()
    resource_plan = payload.get("resource_plan")
    if isinstance(resource_plan, dict):
        provenance = dict(resource_plan.get("provenance") or {})
        provenance["committed"] = True
        resource_plan["provenance"] = provenance
    return {
        "evidence_plan": payload,
        "planning_decision": {"path_type": payload.get("answer_mode")},
        "intent_classification": intent,
        "query_to_intent": q2i.model_dump(),
        "query_understanding": qu,
    }


def _schedules(state: dict[str, Any]) -> tuple[list[str], list[str]]:
    walk = walk_plan_steps(state)
    derived = derive_dispatch_booleans_from_plan(state)
    hooks = _hooks(rag_only=derived["uses_rag_only_path"], pre_mcp=derived["uses_pre_mcp_rag"])
    legacy = _legacy_predicate_dispatch_schedule(state, hooks, walk.blocked_step_ids)
    walked = build_step_walk_dispatch_schedule(state, walk, hooks)
    return legacy, walked


# --- flag-off parity ----------------------------------------------------------


@pytest.mark.parametrize(("question", "skill"), _PROBES)
def test_flag_off_schedule_is_exactly_the_fixed_schedule(
    question: str, skill: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", False)
    state = _state_from_question(question, skill)
    if walk_plan_steps(state) is None:
        pytest.skip("no composed plan")
    legacy, walked = _schedules(state)
    assert walked == legacy


def test_flag_off_trace_carries_no_execution_order_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", False)
    state = _state_from_question(*_PROBES[0])
    walk = walk_plan_steps(state)
    trace = build_plan_dispatch_trace(
        state,
        walk=walk,
        schedule=["workflow_spl"],
        hooks=_hooks(),
        dispatch_source="resource_plan_step_walk",
    )
    assert "execution_order" not in trace


# --- flag-on behavior ---------------------------------------------------------


@pytest.mark.parametrize(("question", "skill"), _PROBES)
def test_flag_on_compiled_schedule_matches_the_fixed_schedule(
    question: str, skill: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Activation is a change of authority, not (yet) a change of order."""
    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", True)
    state = _state_from_question(question, skill)
    if walk_plan_steps(state) is None:
        pytest.skip("no composed plan")
    legacy, walked = _schedules(state)
    assert walked == legacy


def test_flag_on_trace_records_activation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", True)
    state = _state_from_question(*_PROBES[0])
    trace = build_plan_dispatch_trace(
        state,
        walk=walk_plan_steps(state),
        schedule=["workflow_spl"],
        hooks=_hooks(),
        dispatch_source="resource_plan_step_walk",
    )
    assert trace["execution_order"] == {"active": True, "downgrade_reason": None}


# --- dispatch v2 precedence ---------------------------------------------------


def _v2_state(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setattr("app.config.settings.ai_soc_pipeline_dispatch_v2_enabled", True)
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_pipeline_dispatch_v2_enabled", True)
    plan = EvidencePlan(
        answer_mode="live_investigation",
        rag_phase="rag_only",
        needs_rag=False,
        needs_spl=True,
        needs_mcp=False,
        needs_mitre=False,
        spl_allowed=True,
        mcp_allowed=False,
        policy_context_required=False,
        policy_context_recommended=False,
    )
    dispatch = build_pipeline_dispatch(
        evidence_plan=plan.model_dump(),
        intent_classification={"intent_family": "spl_generation"},
    )
    return with_committed_resource_plan(
        {
            "pipeline_dispatch": dispatch.model_dump(mode="json"),
            "evidence_plan": plan.model_dump(),
            "planning_decision": {"path_type": "spl_generation"},
        },
        steps=[{"step_id": "spl", "resource_id": "skill:spl_generation", "purpose": "spl_artifact"}],
    )


def test_dispatch_v2_projection_takes_precedence_and_records_the_downgrade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.planner import executor

    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", True)
    state = _v2_state(monkeypatch)
    walk = walk_plan_steps(state)
    compiled, reason = executor._execution_driven_schedule(state, walk)
    assert compiled is None
    assert reason == "dispatch_v2_projected_schedule"
    legacy, walked = _schedules(state)
    assert walked == legacy


def test_unparseable_plan_downgrades_instead_of_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.planner import executor

    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", True)
    state = {
        "evidence_plan": {
            "resource_plan": {
                "steps": [{"step_id": "spl", "resource_id": 42, "purpose": ["not", "a", "string"]}],
                "provenance": {"committed": True},
            }
        }
    }
    walk = walk_plan_steps(state)
    compiled, reason = executor._execution_driven_schedule(state, walk)
    assert compiled is None
    assert reason == "plan_parse_failed"


# --- gate order and single seam ----------------------------------------------


def test_flag_on_keeps_spl_validation_before_the_execution_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", True)
    state = _state_from_question(*_PROBES[0])
    _, walked = _schedules(state)
    assert walked.index("spl_source_resolve") < walked.index("execution")
    assert walked[-1] == "execution"


def test_both_runtimes_share_one_dispatch_seam() -> None:
    """The graph node is a thin delegate; there is no second scheduler."""
    import inspect

    from app.chat import pipeline

    source = inspect.getsource(pipeline.graph_node_composed_dispatch)
    assert "execute_plan_dispatch" in source


@pytest.mark.parametrize("flag", [False, True])
def test_dispatched_hook_calls_match_the_schedule_on_both_postures(
    flag: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", flag)
    state = _state_from_question(*_PROBES[0])
    derived = derive_dispatch_booleans_from_plan(state)
    calls: list[str] = []
    result = execute_plan_dispatch(
        state,
        _hooks(calls, rag_only=derived["uses_rag_only_path"], pre_mcp=derived["uses_pre_mcp_rag"]),
    )
    assert calls == result["plan_dispatch_trace"]["dispatch_schedule"]
    assert len(calls) == len(set(calls))
