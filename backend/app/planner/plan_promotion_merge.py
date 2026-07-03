"""Merge deterministic floor plans with validated LLM proposals (item 1.3)."""

from __future__ import annotations

import time
from typing import Any

from app.config import settings
from app.llm.turn_llm_budget import TurnLlmBudget
from app.planner.llm_plan_bridge import (
    _BRIDGE_TIMEOUT_SECONDS_CAP,
    bridge_enabled,
    bridge_trigger_match,
    propose_validated_llm_plan,
)
from app.planner.resource_plan import PlanStep, ResourcePlan


def planner_hop_budget_blocked(budget: TurnLlmBudget | None) -> bool:
    """Skip the planner hop when the turn cannot fit bridge + synthesis reserve."""
    if budget is None:
        return False
    remaining = budget.remaining_seconds()
    if remaining is None:
        return False
    reserve = float(_BRIDGE_TIMEOUT_SECONDS_CAP) + budget.composer_reserve_seconds()
    return remaining < reserve


def merge_floor_with_promoted(
    *,
    floor: ResourcePlan,
    promoted: ResourcePlan,
) -> tuple[ResourcePlan, list[dict[str, str]]]:
    """Retain every floor step; add validated LLM steps; never remove floor steps."""
    floor_keys = {(step.resource_id, step.purpose) for step in floor.steps}
    promoted_keys = {(step.resource_id, step.purpose) for step in promoted.steps}
    rejected: list[dict[str, str]] = []

    for step in floor.steps:
        if step.purpose in {"knowledge_retrieval", "spl_artifact", "mitre_mapping", "mcp_execution"}:
            if (step.resource_id, step.purpose) not in promoted_keys:
                rejected.append(
                    {
                        "step": step.step_id,
                        "reason": "floor_step_retained_against_proposal",
                    }
                )

    additions: list[PlanStep] = []
    for step in promoted.steps:
        if (step.resource_id, step.purpose) in floor_keys:
            continue
        additions.append(step)

    merged_steps = list(floor.steps)
    if additions:
        insert_at = len(merged_steps)
        for index, step in enumerate(merged_steps):
            if step.purpose == "narration" or step.step_id == "narration":
                insert_at = index
                break
        for offset, step in enumerate(additions):
            merged_steps.insert(insert_at + offset, step)

    provenance = dict(floor.provenance)
    provenance.update(promoted.provenance)
    provenance["llm_bridge"] = "promoted"
    provenance["floor_step_count"] = len(floor.steps)
    provenance["llm_additions"] = [step.step_id for step in additions]
    if rejected:
        provenance["floor_merge_rejected"] = rejected
    if promoted.provenance.get("dropped_steps"):
        provenance["llm_dropped_steps"] = promoted.provenance["dropped_steps"]

    plan_source: str = floor.plan_source
    if additions:
        plan_source = "llm_proposed_validated"

    return (
        ResourcePlan(
            steps=merged_steps,
            plan_source=plan_source,  # type: ignore[arg-type]
            provenance=provenance,
        ),
        rejected,
    )


def apply_llm_primary_resource_plan(
    floor_plan: ResourcePlan,
    *,
    query: str,
    match_path: str | None,
    action_mode: str | None,
    mcp_allowed: bool,
    budget: TurnLlmBudget | None = None,
    client: Any | None = None,
) -> tuple[ResourcePlan, bool]:
    """Return the live resource plan and whether an LLM planner hop ran."""
    if not settings.control_plane_enabled:
        return floor_plan, False

    if (
        floor_plan.provenance.get("composer") == "guided_hybrid_v1"
        or floor_plan.provenance.get("skill_id") == "guided_investigation"
    ):
        return floor_plan, False

    if not bridge_enabled():
        provenance = dict(floor_plan.provenance)
        provenance["llm_bridge"] = "skipped:flags_off"
        return floor_plan.model_copy(update={"provenance": provenance}), False

    if planner_hop_budget_blocked(budget):
        provenance = dict(floor_plan.provenance)
        provenance["llm_bridge"] = "skipped:budget"
        return floor_plan.model_copy(update={"provenance": provenance}), False

    if not bridge_trigger_match(match_path):
        return floor_plan, False

    proposed = propose_validated_llm_plan(
        query=query,
        match_path=match_path,
        action_mode=action_mode,
        mcp_allowed=mcp_allowed,
        client=client,
        require_bridge_flags=True,
    )
    if proposed is None:
        provenance = dict(floor_plan.provenance)
        provenance["llm_bridge"] = "rejected:no_valid_proposal"
        return floor_plan.model_copy(update={"provenance": provenance}), False

    merged, _rejected = merge_floor_with_promoted(floor=floor_plan, promoted=proposed)
    return merged, True


def record_planner_sidecar(
    budget: TurnLlmBudget | None,
    *,
    started_at: float,
    outcome: str = "completed",
) -> None:
    if budget is None:
        return
    budget.record_sidecar(
        role="route_plan_candidate_generator",
        provider_label="local_or_failover",
        outcome=outcome,
        latency_ms=int((time.monotonic() - started_at) * 1000),
    )
