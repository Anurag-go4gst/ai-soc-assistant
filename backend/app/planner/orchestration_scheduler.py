"""Deterministic MCP orchestration scheduler/reconcile (O5b — pure functions).

The scheduler decides *which governed recipe call runs next*; reconcile decides
*what happens after an outcome*. Both are pure: they take a recipe plus the
list of completed call records and a budget, and return a decision. They never
call a connector, never choose a tool, never write SPL, and never increase a
budget (plan A.3/A.5).

This module is exercised by fixture tests only (O5b). Wiring it into the
imperative pipeline and LangGraph — with real evidence aggregation, lineage,
and the live execution gate — is O5c and stays default-off.

Governance carried from the recipe layer:
- A conditional call fires only when its dependency's classified outcome
  matches its activation condition (deterministic, envelope-metadata only).
- A hard failure (failed/timeout/denied/blocked/schema_mismatch) fails closed:
  no further calls are scheduled; the turn stops for review.
- Empty != failed: an empty result may activate a predeclared follow-up edge
  but never triggers open-ended replanning.
- The budget is a hard stop; it is never raised by the scheduler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.orchestration.mcp_orchestration import CallBudget, CallOutcome, McpCallRecord
from app.planner.recipe_registry import Recipe, RecipeCall, evaluate_activation

# Outcomes that resolve a call's produced evidence keys. Empty is included: an
# empty result is honest negative evidence for those keys (plan A.10).
_RESOLVING_OUTCOMES: set[CallOutcome] = {"ok", "partial", "empty"}

# Outcomes that fail closed — no further scheduling, stop for review.
_HARD_FAILURE_OUTCOMES: set[CallOutcome] = {
    "failed",
    "timeout",
    "denied",
    "blocked",
    "schema_mismatch",
}

ScheduleAction = Literal["execute", "stop"]


@dataclass
class ScheduleDecision:
    action: ScheduleAction
    call_id: str | None = None
    stop_reason: str | None = None
    unresolved_evidence_keys: list[str] = field(default_factory=list)


def _outcome_by_call(records: list[McpCallRecord]) -> dict[str, CallOutcome]:
    return {record.call_id: record.outcome for record in records}


def produced_evidence_keys(recipe: Recipe, records: list[McpCallRecord]) -> set[str]:
    """Evidence keys resolved by completed calls (success, partial, or empty)."""
    resolved: set[str] = set()
    for record in records:
        if record.outcome not in _RESOLVING_OUTCOMES:
            continue
        call = recipe.call_by_id(record.call_id)
        if call is not None:
            resolved.update(call.produces_evidence_keys)
    return resolved


def unresolved_evidence_keys(recipe: Recipe, records: list[McpCallRecord]) -> list[str]:
    """Recipe evidence keys not yet resolved by any completed call (A.5 step 1)."""
    produced = produced_evidence_keys(recipe, records)
    wanted: list[str] = []
    for call in recipe.calls:
        for key in call.produces_evidence_keys:
            if key not in produced and key not in wanted:
                wanted.append(key)
    return wanted


def _dependency_satisfied(call: RecipeCall, executed: dict[str, CallOutcome]) -> bool:
    return all(dep in executed for dep in call.depends_on)


def _prior_outcome(call: RecipeCall, executed: dict[str, CallOutcome]) -> CallOutcome | None:
    # Activation refers to the depended-on call; our v1 recipes use a single
    # dependency, so the last listed dependency is the "previous" call.
    if not call.depends_on:
        return None
    return executed.get(call.depends_on[-1])


def schedule_next(
    recipe: Recipe,
    records: list[McpCallRecord],
    budget: CallBudget,
) -> ScheduleDecision:
    """Select the next ready, policy-eligible call — or stop (A.5 algorithm)."""
    executed = _outcome_by_call(records)
    missing = unresolved_evidence_keys(recipe, records)

    # Fail closed: the most recent hard failure stops the turn for review.
    if records and records[-1].outcome in _HARD_FAILURE_OUTCOMES:
        return ScheduleDecision(
            action="stop",
            stop_reason=f"fail_closed:{records[-1].outcome}",
            unresolved_evidence_keys=missing,
        )

    produced = produced_evidence_keys(recipe, records)
    ready_call_id: str | None = None
    for call in recipe.calls:
        if call.call_id in executed:
            continue
        if not _dependency_satisfied(call, executed):
            continue
        if not evaluate_activation(
            call.activation_condition,
            prior_outcome=_prior_outcome(call, executed),
            missing_keys=missing,
        ):
            continue
        # Skip a call whose outputs are already resolved by an earlier call.
        if call.produces_evidence_keys and all(
            key in produced for key in call.produces_evidence_keys
        ):
            continue
        ready_call_id = call.call_id
        break

    if ready_call_id is None:
        return ScheduleDecision(
            action="stop", stop_reason="evidence_satisfied", unresolved_evidence_keys=missing
        )

    # A call is ready but the budget is spent: stop for review, never raise it.
    if not budget.has_call_capacity():
        return ScheduleDecision(
            action="stop", stop_reason="budget_exhausted", unresolved_evidence_keys=missing
        )

    return ScheduleDecision(
        action="execute", call_id=ready_call_id, unresolved_evidence_keys=missing
    )


def outcome_edge(call: RecipeCall, outcome: CallOutcome) -> str:
    """Map a classified outcome to the call's predeclared edge target.

    Returns a sibling call_id, "terminal", or "hil" (plan A.8). Edges are data
    on the recipe — never ad hoc exception handling.
    """
    mapping = {
        "ok": "terminal" if call.terminal else "",
        "partial": "hil",
        "empty": call.on_empty,
        "failed": call.on_error,
        "timeout": call.on_timeout,
        "denied": call.on_denied,
        "blocked": call.on_denied,
        "schema_mismatch": call.on_error,
    }
    target = mapping.get(outcome, "hil")
    # An "ok" non-terminal call simply lets the scheduler pick the next ready
    # step; there is no explicit edge to follow.
    return target or "terminal"
