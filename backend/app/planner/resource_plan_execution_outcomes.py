"""Failure, skip, fallback and finalization reconcile (Plan 2, C1-E5).

Given an execution contract and the outcomes observed for its steps, this
module decides what each step's status is, what may still run, whether the turn
stops for a human, and whether finalization may run. It is a pure function of
its inputs, so replaying a turn produces identical statuses.

Rules that must not erode:
- Nothing uncertain or side-effecting is ever retried automatically. A step that
  may have already changed something is reported, never repeated.
- A failed or blocked dependency skips its dependents rather than running them
  on missing input; an *empty* dependency is honest negative evidence and does
  not skip anything.
- Finalization runs exactly once and carries declared limitations instead of
  silently presenting partial evidence as complete.
- No contract means no opinion: the caller stays on the fixed schedule.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from app.planner.resource_plan_execution import ExecutionContract


class ExecutionOutcome(str, Enum):
    OK = "ok"
    EMPTY = "empty"
    FAILED = "failed"
    TIMEOUT = "timeout"
    DENIED = "denied"
    UNCERTAIN = "uncertain"


class StepDisposition(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    COMPLETED_EMPTY = "completed_empty"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    UNCERTAIN = "uncertain"


HARD_FAILURE_OUTCOMES = frozenset(
    {ExecutionOutcome.FAILED, ExecutionOutcome.TIMEOUT, ExecutionOutcome.DENIED}
)

_OUTCOME_DISPOSITION: dict[ExecutionOutcome, StepDisposition] = {
    ExecutionOutcome.OK: StepDisposition.COMPLETED,
    ExecutionOutcome.EMPTY: StepDisposition.COMPLETED_EMPTY,
    ExecutionOutcome.FAILED: StepDisposition.FAILED,
    ExecutionOutcome.TIMEOUT: StepDisposition.FAILED,
    ExecutionOutcome.DENIED: StepDisposition.BLOCKED,
    ExecutionOutcome.UNCERTAIN: StepDisposition.UNCERTAIN,
}

# Dispositions that stop everything downstream of them.
_STOPS_DOWNSTREAM = {
    StepDisposition.FAILED,
    StepDisposition.BLOCKED,
    StepDisposition.SKIPPED,
    StepDisposition.UNCERTAIN,
}


@dataclass(frozen=True)
class ExecutionReconciliation:
    dispositions: dict[str, StepDisposition] = field(default_factory=dict)
    skip_reasons: dict[str, str] = field(default_factory=dict)
    fallback_targets: dict[str, str] = field(default_factory=dict)
    runnable_step_ids: list[str] = field(default_factory=list)
    retry_step_ids: list[str] = field(default_factory=list)
    requires_human_review: bool = False
    stop_reason: str | None = None


@dataclass(frozen=True)
class FinalizationDecision:
    finalize: bool
    partial: bool = False
    limitations: list[str] = field(default_factory=list)
    reason: str | None = None


def reconcile_execution(
    contract: ExecutionContract | None,
    outcomes: Mapping[str, ExecutionOutcome],
) -> ExecutionReconciliation:
    """Resolve step statuses, downstream skips, fallbacks and stop conditions."""
    if contract is None:
        return ExecutionReconciliation(stop_reason="no_execution_contract")

    dispositions: dict[str, StepDisposition] = {}
    skip_reasons: dict[str, str] = {}
    fallback_targets: dict[str, str] = {}
    requires_review = False
    stop_reason: str | None = None

    for step in contract.steps:
        if not step.executable:
            dispositions[step.step_id] = StepDisposition.BLOCKED
            if step.skip_reason:
                skip_reasons[step.step_id] = step.skip_reason
            continue

        outcome = outcomes.get(step.step_id)
        if outcome is None:
            dispositions[step.step_id] = StepDisposition.PENDING
            continue

        disposition = _OUTCOME_DISPOSITION[outcome]
        dispositions[step.step_id] = disposition

        if outcome in HARD_FAILURE_OUTCOMES or outcome is ExecutionOutcome.UNCERTAIN:
            fallback_targets[step.step_id] = step.on_failure
            if step.on_failure == "hil":
                requires_review = True
        if outcome is ExecutionOutcome.UNCERTAIN:
            # An operation that may already have taken effect is reported, never
            # repeated, and always surfaced to a human.
            requires_review = True
            stop_reason = stop_reason or (
                "uncertain_side_effect" if step.side_effecting else "uncertain_step"
            )

    _propagate_skips(contract, dispositions, skip_reasons)

    runnable = [
        step.step_id
        for step in contract.steps
        if dispositions.get(step.step_id) is StepDisposition.PENDING
        and all(
            dispositions.get(dependency)
            in {StepDisposition.COMPLETED, StepDisposition.COMPLETED_EMPTY}
            for dependency in step.depends_on
        )
    ]

    return ExecutionReconciliation(
        dispositions=dispositions,
        skip_reasons=skip_reasons,
        fallback_targets=fallback_targets,
        runnable_step_ids=runnable,
        # Deliberately always empty: no automatic retry is issued from here.
        # A declared `max_attempts > 1` bounds an in-stage retry the stage owns;
        # it never authorizes this reconcile pass to re-run a step.
        retry_step_ids=[],
        requires_human_review=requires_review,
        stop_reason=stop_reason,
    )


def _propagate_skips(
    contract: ExecutionContract,
    dispositions: dict[str, StepDisposition],
    skip_reasons: dict[str, str],
) -> None:
    """A step whose dependency failed, blocked or skipped is skipped, not run."""
    changed = True
    while changed:
        changed = False
        for step in contract.steps:
            if dispositions.get(step.step_id) is not StepDisposition.PENDING:
                continue
            for dependency in step.depends_on:
                upstream = dispositions.get(dependency)
                if upstream in _STOPS_DOWNSTREAM:
                    dispositions[step.step_id] = StepDisposition.SKIPPED
                    skip_reasons[step.step_id] = f"dependency_{upstream.value}:{dependency}"
                    changed = True
                    break


def finalization_decision(
    reconciliation: ExecutionReconciliation,
    *,
    already_finalized: bool,
) -> FinalizationDecision:
    """Finalize once, with honest limitations for anything that did not deliver."""
    if already_finalized:
        return FinalizationDecision(finalize=False, reason="already_finalized")

    limitations: list[str] = []
    partial = False
    for step_id, disposition in reconciliation.dispositions.items():
        if disposition is StepDisposition.FAILED:
            limitations.append(f"step_failed:{step_id}")
            partial = True
        elif disposition is StepDisposition.BLOCKED:
            limitations.append(f"step_blocked:{step_id}")
            partial = True
        elif disposition is StepDisposition.SKIPPED:
            limitations.append(f"step_skipped:{step_id}")
            partial = True
        elif disposition is StepDisposition.UNCERTAIN:
            limitations.append(f"step_outcome_uncertain:{step_id}")
            partial = True
        elif disposition is StepDisposition.COMPLETED_EMPTY:
            # Empty is honest negative evidence, not a partial answer.
            limitations.append(f"step_returned_no_results:{step_id}")

    return FinalizationDecision(finalize=True, partial=partial, limitations=limitations)
