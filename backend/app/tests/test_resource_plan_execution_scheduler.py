"""Plan 2 C1-E2 — pure ResourcePlan schedule compiler.

Compiles a validated execution contract into the deterministic hook schedule
the executor already speaks. Pure: no worker call, no connector, no LLM, no
state mutation, no settings read. Nothing here is wired into dispatch — that is
C1-E4, behind `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` (default false).
"""

from __future__ import annotations

from typing import Any

import pytest

from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.config import settings
from app.planner.executor import (
    DispatchHooks,
    _legacy_predicate_dispatch_schedule,
    derive_dispatch_booleans_from_plan,
    walk_plan_steps,
)
from app.planner.resource_plan import PlanStep, ResourcePlan
from app.planner.resource_plan_execution import StepExecutionSpec
from app.planner.resource_plan_execution_scheduler import (
    SCHEDULABLE_HOOKS,
    ScheduleInputs,
    compile_execution_schedule,
)
from app.query_understanding.parser import understand_query


def _step(step_id: str, purpose: str, **kwargs: Any) -> PlanStep:
    return PlanStep(step_id=step_id, resource_id=f"resource:{purpose}", purpose=purpose, **kwargs)


def _plan(*steps: PlanStep) -> ResourcePlan:
    return ResourcePlan(steps=list(steps))


def _inputs(**kwargs: Any) -> ScheduleInputs:
    base: dict[str, Any] = {"blocked_step_ids": frozenset(), "has_workflow_plan": False}
    base.update(kwargs)
    return ScheduleInputs(**base)


def _compile(plan: ResourcePlan, **kwargs: Any):
    return compile_execution_schedule(plan, _inputs(**kwargs))


@pytest.fixture(autouse=True)
def _cp_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)


# --- shape --------------------------------------------------------------------


def test_compiled_hooks_use_only_the_executor_hook_vocabulary() -> None:
    from app.planner.executor import _HOOK_BY_NAME

    assert SCHEDULABLE_HOOKS <= set(_HOOK_BY_NAME)


def test_spl_plan_compiles_the_spl_lane() -> None:
    schedule, reason = _compile(
        _plan(_step("spl", "spl_artifact"), _step("mcp", "mcp_execution"), _step("n", "narration"))
    )
    assert reason is None
    assert schedule.hooks == ["workflow_spl", "spl_source_resolve", "execution"]
    assert schedule.waves == [["spl", "n"], ["mcp"]]


def test_rag_only_plan_compiles_the_rag_tail() -> None:
    schedule, reason = _compile(_plan(_step("rag", "knowledge_retrieval"), _step("n", "narration")))
    assert reason is None
    assert schedule.hooks == ["prepare_rag_only", "rag_early"]


def test_pre_mcp_rag_runs_between_spl_generation_and_source_resolve() -> None:
    schedule, _ = _compile(
        _plan(
            _step("rag", "knowledge_retrieval"),
            _step("spl", "spl_artifact"),
            _step("mcp", "mcp_execution"),
        )
    )
    assert schedule.hooks == ["workflow_spl", "rag_early", "spl_source_resolve", "execution"]


def test_every_hook_appears_at_most_once() -> None:
    schedule, _ = _compile(
        _plan(
            _step("spl", "spl_artifact"),
            _step("spl2", "spl_artifact"),
            _step("mcp", "mcp_execution"),
            _step("mcp2", "mcp_execution"),
        )
    )
    assert len(schedule.hooks) == len(set(schedule.hooks))


def test_step_to_hook_mapping_is_reported() -> None:
    schedule, _ = _compile(_plan(_step("spl", "spl_artifact"), _step("mcp", "mcp_execution")))
    assert schedule.step_hooks["spl"] == ["workflow_spl", "spl_source_resolve"]
    assert schedule.step_hooks["mcp"] == ["execution"]


def test_non_dispatchable_purposes_map_to_no_hook() -> None:
    schedule, _ = _compile(
        _plan(
            _step("spl", "spl_artifact"),
            _step("n", "narration"),
            _step("ctx", "context_sufficiency"),
        )
    )
    assert schedule.step_hooks["n"] == []
    assert schedule.step_hooks["ctx"] == []


# --- ordering authority -------------------------------------------------------


def test_composed_order_does_not_reorder_the_governed_lane() -> None:
    """Reversing a plan cannot move SPL validation after the MCP gate."""
    forward, _ = _compile(_plan(_step("spl", "spl_artifact"), _step("mcp", "mcp_execution")))
    reversed_plan, _ = _compile(_plan(_step("mcp", "mcp_execution"), _step("spl", "spl_artifact")))
    assert forward.hooks == reversed_plan.hooks
    assert reversed_plan.hooks.index("spl_source_resolve") < reversed_plan.hooks.index("execution")


def test_declared_dependency_cannot_place_execution_before_spl_validation() -> None:
    schedule, _ = _compile(
        _plan(
            _step("mcp", "mcp_execution", execution=StepExecutionSpec(depends_on=[])),
            _step("spl", "spl_artifact"),
        )
    )
    assert schedule.hooks.index("workflow_spl") < schedule.hooks.index("execution")


def test_tie_breaking_is_stable_and_follows_composed_order() -> None:
    plan = _plan(
        _step("rag", "knowledge_retrieval"),
        _step("cve", "cve_lookup"),
        _step("mitre", "mitre_mapping"),
    )
    first, _ = _compile(plan)
    second, _ = _compile(plan)
    assert first.waves == second.waves
    assert first.waves[0] == ["rag", "cve", "mitre"]


# --- blocked / skipped --------------------------------------------------------


def test_blocked_spl_step_drops_the_spl_lane_and_ensures_a_workflow_plan() -> None:
    schedule, _ = _compile(
        _plan(_step("spl", "spl_artifact"), _step("mcp", "mcp_execution")),
        blocked_step_ids=frozenset({"spl"}),
    )
    assert "workflow_spl" not in schedule.hooks
    assert "spl_source_resolve" not in schedule.hooks
    assert schedule.hooks == ["ensure_workflow_plan", "execution"]


def test_blocked_spl_step_with_an_existing_workflow_plan_skips_the_ensure_hook() -> None:
    schedule, _ = _compile(
        _plan(_step("spl", "spl_artifact"), _step("mcp", "mcp_execution")),
        blocked_step_ids=frozenset({"spl"}),
        has_workflow_plan=True,
    )
    assert schedule.hooks == ["execution"]


def test_blocked_rag_step_drops_only_rag_hooks() -> None:
    schedule, _ = _compile(
        _plan(
            _step("rag", "knowledge_retrieval"),
            _step("spl", "spl_artifact"),
            _step("mcp", "mcp_execution"),
        ),
        blocked_step_ids=frozenset({"rag"}),
    )
    assert schedule.hooks == ["workflow_spl", "spl_source_resolve", "execution"]


def test_policy_blocked_mcp_step_still_reaches_the_execution_stage() -> None:
    """The execution node owns the gate and the honest blocked outcome."""
    schedule, _ = _compile(
        _plan(
            _step("spl", "spl_artifact"),
            _step("mcp", "mcp_execution", status="blocked_policy", status_reason="skill_contract"),
        )
    )
    assert schedule.hooks[-1] == "execution"
    assert schedule.step_hooks["mcp"] == []


# --- downgrade ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("plan", "expected"),
    [
        (None, "no_resource_plan"),
        (ResourcePlan(), "empty_resource_plan"),
    ],
)
def test_absent_or_empty_plan_downgrades(plan: ResourcePlan | None, expected: str) -> None:
    schedule, reason = compile_execution_schedule(plan, _inputs())
    assert schedule is None
    assert reason == expected


def test_invalid_contract_downgrades() -> None:
    schedule, reason = _compile(
        _plan(_step("spl", "spl_artifact", execution=StepExecutionSpec(depends_on=["ghost"])))
    )
    assert schedule is None
    assert reason == "contract_invalid:unknown_dependency"


def test_unsupported_purpose_downgrades() -> None:
    schedule, reason = _compile(_plan(_step("x", "teleport_the_analyst")))
    assert schedule is None
    assert reason == "unsupported_purpose:teleport_the_analyst"


def test_plan_with_no_schedulable_step_downgrades() -> None:
    schedule, reason = _compile(_plan(_step("n", "narration")))
    assert schedule is None
    assert reason == "no_schedulable_step"


# --- purity -------------------------------------------------------------------


def test_scheduler_calls_no_worker_and_reads_no_state_or_flag() -> None:
    import ast
    import inspect

    from app.planner import resource_plan_execution_scheduler

    tree = ast.parse(inspect.getsource(resource_plan_execution_scheduler))
    imported: set[str] = set()
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
            imported_names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported_names.update(alias.asname or alias.name for alias in node.names)
    for forbidden in ("app.config", "app.connectors", "app.mcp", "app.llm", "httpx", "requests"):
        assert not any(name.startswith(forbidden) for name in imported), forbidden
    # Names hooks, never holds callables: no worker table is imported.
    assert "DispatchHooks" not in imported_names
    assert "_HOOK_BY_NAME" not in imported_names


def test_compiling_does_not_mutate_the_plan() -> None:
    plan = _plan(_step("spl", "spl_artifact"), _step("mcp", "mcp_execution"))
    before = plan.model_dump()
    _compile(plan)
    assert plan.model_dump() == before


# --- parity against the current fixed schedule --------------------------------

_PROBES = [
    ("Which users have excessive failed logins?", "attack_discovery"),
    ("Generate SPL for failed logins", "spl_generation"),
    ("What is our password policy for contractor accounts?", "knowledge_recall"),
    ("Which hosts are generating the most SMB traffic?", "attack_discovery"),
]


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


def _legacy_hooks(state: dict[str, Any]) -> tuple[list[str], Any]:
    walk = walk_plan_steps(state)
    derived = derive_dispatch_booleans_from_plan(state)

    def node(_name: str):
        def run(inner: dict[str, Any]) -> dict[str, Any]:
            return inner

        return run

    hooks = DispatchHooks(
        uses_rag_only_path=lambda _s: derived["uses_rag_only_path"],
        uses_pre_mcp_rag=lambda _s: derived["uses_pre_mcp_rag"],
        prepare_rag_only=node("prepare_rag_only"),
        rag_early=node("rag_early"),
        spl_source_resolve=node("spl_source_resolve"),
        workflow_spl=node("workflow_spl"),
        spl_postprocessor=node("spl_postprocessor"),
        ensure_workflow_plan=node("ensure_workflow_plan"),
        reference_finalize=node("reference_finalize"),
        execution=node("execution"),
    )
    return _legacy_predicate_dispatch_schedule(state, hooks, walk.blocked_step_ids), walk


@pytest.mark.parametrize(("question", "skill"), _PROBES)
def test_compiled_schedule_matches_the_current_fixed_schedule(question: str, skill: str) -> None:
    state = _state_from_question(question, skill)
    legacy, walk = _legacy_hooks(state)
    if walk is None:
        pytest.skip("no composed plan")
    plan = ResourcePlan.model_validate(state["evidence_plan"]["resource_plan"])
    schedule, reason = compile_execution_schedule(
        plan,
        ScheduleInputs(
            blocked_step_ids=frozenset(walk.blocked_step_ids),
            has_workflow_plan=bool(state.get("workflow_plan")),
        ),
    )
    assert reason is None, reason
    assert schedule.hooks == legacy
