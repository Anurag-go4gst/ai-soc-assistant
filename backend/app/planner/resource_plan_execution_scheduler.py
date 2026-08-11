"""Pure ResourcePlan schedule compiler (Plan 2, C1-E2).

Turns a validated execution contract into the hook schedule the executor
already speaks (`app.planner.executor._HOOK_BY_NAME`). It decides *what order
the stage nodes run in*; it never runs one.

Boundaries:
- Pure. Inputs are a `ResourcePlan` plus an explicit `ScheduleInputs` record;
  there is no state read, no settings read, no I/O, and the plan is not
  mutated. `DispatchHooks` is deliberately not imported — the compiler names
  hooks, it does not hold callables.
- Governed lane order is fixed, not plan-derived. SPL generation and SPL source
  resolution always precede the execution stage, which remains the sole owner
  of the MCP execution gate and HIL. Composed step order cannot move them; a
  reversed plan compiles to the same schedule.
- Parallelism is expressed only as contract `waves` (read-only steps), never by
  emitting a hook twice or by reordering the governed lane.
- Fail closed by downgrade. Anything absent, empty, invalid, unsupported, or
  with nothing schedulable returns `(None, reason)`, and the caller keeps the
  existing fixed deterministic schedule.

Nothing imports this yet. Wiring is C1-E4, behind
`AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` (default false).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.planner.resource_plan_execution import (
    ExecutionContract,
    execution_contract_or_downgrade,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.planner.resource_plan import ResourcePlan

# Hook names this compiler may emit. A subset of the executor's hook table:
# `spl_postprocessor` and `reference_finalize` are driven by their own stage
# predicates, not by plan steps, so the compiler never schedules them.
SCHEDULABLE_HOOKS = {
    "prepare_rag_only",
    "rag_early",
    "workflow_spl",
    "spl_source_resolve",
    "ensure_workflow_plan",
    "execution",
}

# Purpose → the hooks that carry out that step. A purpose with no hook is real
# and valid (narration, context sufficiency): it contributes lineage, not work.
_PURPOSE_HOOKS: dict[str, tuple[str, ...]] = {
    "knowledge_retrieval": ("rag_early",),
    "spl_artifact": ("workflow_spl", "spl_source_resolve"),
    "mcp_execution": ("execution",),
}


@dataclass(frozen=True)
class ScheduleInputs:
    """Everything outside the plan that the schedule depends on, passed explicitly."""

    blocked_step_ids: frozenset[str]
    has_workflow_plan: bool


@dataclass(frozen=True)
class ExecutionSchedule:
    hooks: list[str]
    waves: list[list[str]]
    step_hooks: dict[str, list[str]]


def _purposes(contract: ExecutionContract, blocked: frozenset[str]) -> set[str]:
    return {step.purpose for step in contract.steps if step.step_id not in blocked}


def compile_execution_schedule(
    plan: "ResourcePlan | None",
    inputs: ScheduleInputs,
) -> tuple[ExecutionSchedule | None, str | None]:
    """Compile a plan into an ordered hook schedule, or explain the downgrade."""
    contract, downgrade = execution_contract_or_downgrade(plan)
    if contract is None:
        return None, downgrade

    blocked = inputs.blocked_step_ids
    live_purposes = _purposes(contract, blocked)

    has_rag = "knowledge_retrieval" in live_purposes
    has_spl = "spl_artifact" in live_purposes
    has_mcp = "mcp_execution" in live_purposes
    spl_blocked = any(
        step.purpose == "spl_artifact" and step.step_id in blocked for step in contract.steps
    )

    hooks = _compile_hooks(
        has_rag=has_rag,
        has_spl=has_spl,
        has_mcp=has_mcp,
        spl_blocked=spl_blocked,
        has_workflow_plan=inputs.has_workflow_plan,
    )
    if not hooks:
        return None, "no_schedulable_step"

    emitted = set(hooks)
    step_hooks = {
        step.step_id: [
            hook
            for hook in _PURPOSE_HOOKS.get(step.purpose, ())
            if hook in emitted and step.executable and step.step_id not in blocked
        ]
        for step in contract.steps
    }
    return ExecutionSchedule(hooks=hooks, waves=contract.waves, step_hooks=step_hooks), None


def _compile_hooks(
    *,
    has_rag: bool,
    has_spl: bool,
    has_mcp: bool,
    spl_blocked: bool,
    has_workflow_plan: bool,
) -> list[str]:
    """The governed lane, in fixed order. Plan content selects, never reorders."""
    # RAG-only tail: knowledge with no SPL artifact and no execution stage.
    if has_rag and not has_spl and not has_mcp and not spl_blocked:
        return ["prepare_rag_only", "rag_early"]

    hooks: list[str] = []
    if has_spl:
        hooks.append("workflow_spl")
    # Pre-MCP RAG enriches the SPL lane between generation and source resolve.
    if has_rag:
        hooks.append("rag_early")
    if has_spl:
        hooks.append("spl_source_resolve")
    if spl_blocked and not has_workflow_plan:
        hooks.append("ensure_workflow_plan")
    if hooks or has_mcp:
        hooks.append("execution")
    return hooks
