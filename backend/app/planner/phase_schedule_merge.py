"""Deterministic merge seam (Plan 5 C1).

    ResolvedQueryContract + ResourcePlan + PhaseContract  ->  ONE schedule

There is exactly one compiler: `resource_plan_execution_scheduler.compile_execution_schedule`.
This module does not replace it. It does the two things the compiler cannot:

1. **Re-inserts contracted lifecycle phases the compiler cannot schedule.**
   `SCHEDULABLE_HOOKS` deliberately excludes `spl_postprocessor` and
   `reference_finalize` because they were driven by stage predicates elsewhere.
   Plan 3 A0 measured the consequence: made authoritative without a lifecycle
   contract, the compiler dropped a stage on 4 of 5 probes. The `PhaseContract`
   is that missing piece, and insertion is deterministic — a missing mandatory
   phase goes at the earliest index satisfying every registry ordering
   constraint, or the whole merge downgrades. It is never repaired silently.

2. **Evaluates capability satisfaction at SCHEDULE level.**
   Plan 5 amendment 5, from the measured B5 regression: a run's required
   capabilities are satisfied by the complete governed schedule, not by the one
   routed skill. A plan whose primary skill is `spl_generation` legitimately
   satisfies `{spl, mcp}` as `spl → validate → mcp read → synthesis`. This is a
   deterministic function over the merged schedule and the committed plan —
   never a model call, and never a route veto.

Boundaries: pure; no settings, state, LLM or I/O. Ordering comes from
dependencies and registry constraints, never from a fixed Knowledge→SPL→MCP
sequence. Read-only steps may repeat; side-effecting steps keep
`max_attempts=1`, which `resource_plan_execution` already enforces. Anything
invalid returns `(None, reason)` so the caller keeps the existing fixed
deterministic schedule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.planner.phase_contract import PhaseContract, PhaseContractViolation
from app.planner.phase_registry import (
    PHASE_REGISTRY,
    PhaseOrderViolation,
    UnknownPhaseError,
    phase_for_hook,
    validate_schedule_order,
)
from app.planner.resource_plan_execution import (
    SIDE_EFFECTING_PURPOSES,
    execution_contract_or_downgrade,
)
from app.planner.resource_plan_execution_scheduler import (
    ScheduleInputs,
    compile_execution_schedule,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.chat.contracts.resolved_query import ResolvedQueryContract
    from app.planner.resource_plan import ResourcePlan

SCHEMA_VERSION = "phase_schedule_merge_v1"

CAPABILITY_SPL = "spl"
CAPABILITY_MCP = "mcp"

# Which capability a lifecycle phase carries out. The execution phase owns the
# MCP gate, so it is what makes `mcp` reachable in a schedule.
_CAPABILITY_BY_PHASE: dict[str, str] = {
    "workflow_spl": CAPABILITY_SPL,
    "execution": CAPABILITY_MCP,
    "pre_spl_mcp_discovery": CAPABILITY_MCP,
}

# Read-only MCP work that satisfies `mcp` without the execution gate.
_CAPABILITY_BY_PURPOSE: dict[str, str] = {
    "spl_artifact": CAPABILITY_SPL,
    "mcp_execution": CAPABILITY_MCP,
    "mcp_discovery": CAPABILITY_MCP,
    "safe_catalog_query": CAPABILITY_MCP,
}


@dataclass(frozen=True)
class CapabilitySatisfaction:
    """Does this governed schedule satisfy the contract's capability requirements?"""

    satisfied: bool
    required: frozenset[str]
    granted: frozenset[str]
    missing: frozenset[str]
    prohibited_violated: frozenset[str]


@dataclass(frozen=True)
class MergedSchedule:
    """One dependency-valid runnable schedule plus the lifecycle it honours."""

    hooks: tuple[str, ...]
    waves: tuple[tuple[str, ...], ...]
    step_hooks: dict[str, list[str]]
    inserted_phases: tuple[str, ...]
    inline_phases: tuple[str, ...]
    capability: CapabilitySatisfaction


def _insertion_index(
    hooks: list[str], phase: str, placed: dict[str, int]
) -> int | None:
    """Earliest index for `phase` that satisfies every ordering constraint."""
    spec = PHASE_REGISTRY[phase]
    lower = 0
    for predecessor in spec.after:
        if predecessor in placed:
            lower = max(lower, placed[predecessor] + 1)

    upper = len(hooks)
    for name, other in PHASE_REGISTRY.items():
        if phase in other.after and name in placed:
            upper = min(upper, placed[name])

    return lower if lower <= upper else None


def _apply_phase_contract(
    hooks: list[str], phase_contract: PhaseContract
) -> tuple[list[str], list[str]] | None:
    """Insert every contracted mandatory hook phase the compiler omitted."""
    merged = list(hooks)
    inserted: list[str] = []

    missing = [
        name
        for name in PHASE_REGISTRY  # registry declaration order → deterministic
        if name in phase_contract.hook_bound_mandatory
        and PHASE_REGISTRY[name].hook_name not in merged
    ]
    for phase in missing:
        placed = {phase_for_hook(hook).name: index for index, hook in enumerate(merged)}
        index = _insertion_index(merged, phase, placed)
        if index is None:
            return None
        merged.insert(index, str(PHASE_REGISTRY[phase].hook_name))
        inserted.append(phase)
    return merged, inserted


def evaluate_capability_satisfaction(
    contract: "ResolvedQueryContract",
    plan: "ResourcePlan | None",
    hooks: tuple[str, ...] | list[str],
) -> CapabilitySatisfaction:
    """Deterministic: does the whole governed schedule cover the required capabilities?

    Deliberately **not** "does the routed skill grant every capability" — that
    reading is what demoted `cisco.ot.029` at B5. A schedule that generates SPL,
    validates it and then runs the governed MCP read satisfies `{spl, mcp}`
    whatever single skill owns the route.
    """
    required = frozenset(contract.required_capabilities)
    prohibited = frozenset(contract.prohibited_capabilities)

    granted: set[str] = set()
    for hook in hooks:
        try:
            phase = phase_for_hook(hook).name
        except UnknownPhaseError:
            continue
        capability = _CAPABILITY_BY_PHASE.get(phase)
        if capability:
            granted.add(capability)

    if plan is not None:
        for step in plan.steps:
            if str(getattr(step, "status", "")) in {
                "blocked_policy",
                "not_onboarded",
                "skipped_unavailable",
            }:
                continue
            capability = _CAPABILITY_BY_PURPOSE.get(str(step.purpose))
            if capability:
                granted.add(capability)

    granted_frozen = frozenset(granted)
    return CapabilitySatisfaction(
        satisfied=bool(required <= granted_frozen) and not (granted_frozen & prohibited),
        required=required,
        granted=granted_frozen,
        missing=frozenset(required - granted_frozen),
        prohibited_violated=frozenset(granted_frozen & prohibited),
    )


def merge_schedule(
    contract: "ResolvedQueryContract",
    plan: "ResourcePlan | None",
    phase_contract: PhaseContract,
    inputs: ScheduleInputs,
) -> tuple[MergedSchedule | None, str | None]:
    """Compile one schedule honouring the plan's dependencies and the run's lifecycle.

    Returns `(None, reason)` for anything absent, invalid, cyclic, unsupported or
    unplaceable — the caller keeps the fixed deterministic schedule and no
    mandatory lifecycle phase is ever silently dropped.
    """
    compiled, downgrade = compile_execution_schedule(plan, inputs)
    if compiled is None:
        return None, downgrade

    applied = _apply_phase_contract(list(compiled.hooks), phase_contract)
    if applied is None:
        return None, "phase_contract_unplaceable"
    hooks, inserted = applied

    try:
        validate_schedule_order(hooks)
        phase_contract.validate_schedule(hooks)
    except (PhaseOrderViolation, PhaseContractViolation, UnknownPhaseError):
        return None, "phase_contract_violation"

    execution_contract, contract_downgrade = execution_contract_or_downgrade(plan)
    if execution_contract is None:  # pragma: no cover - compile already proved it valid
        return None, contract_downgrade

    for step in execution_contract.steps:
        if step.purpose in SIDE_EFFECTING_PURPOSES and step.max_attempts != 1:
            return None, "side_effecting_step_declares_retry"

    capability = evaluate_capability_satisfaction(contract, plan, hooks)

    return (
        MergedSchedule(
            hooks=tuple(hooks),
            waves=tuple(tuple(wave) for wave in execution_contract.waves),
            step_hooks=dict(compiled.step_hooks),
            inserted_phases=tuple(inserted),
            inline_phases=tuple(sorted(phase_contract.inline_mandatory)),
            capability=capability,
        ),
        None,
    )
