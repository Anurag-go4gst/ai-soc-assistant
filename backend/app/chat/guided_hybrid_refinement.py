"""Bounded refinement loop for guided hybrid dispatch (REV4 batch 2 P13a)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Mapping

from app.chat.contracts.investigation_plan import InvestigationPlan

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.planner.resource_plan_execution import ExecutionContract

# Planning is round 0; refinements continue while recommended until this cap.
MAX_GUIDED_INVESTIGATION_ROUNDS = 3

REFINEMENT_CAP_WARNING = "refinement_cap_reached"


def refinement_cap_reached(*, refinement_round: int, refinement_recommended: bool) -> bool:
    """True when another refinement pass would exceed the hard round cap."""
    return bool(refinement_recommended) and refinement_round + 1 >= MAX_GUIDED_INVESTIGATION_ROUNDS


def should_run_refinement_pass(*, refinement_round: int, refinement_recommended: bool) -> bool:
    """True when a follow-on refinement pass is allowed after the current round."""
    return bool(refinement_recommended) and refinement_round + 1 < MAX_GUIDED_INVESTIGATION_ROUNDS


def apply_refinement_cap_warning(plan: InvestigationPlan) -> InvestigationPlan:
    """Record cap exhaustion without widening execution posture."""
    warnings = list(plan.validation_warnings)
    if REFINEMENT_CAP_WARNING not in warnings:
        warnings.append(REFINEMENT_CAP_WARNING)
    return plan.model_copy(
        update={
            "refinement_recommended": False,
            "validation_warnings": warnings,
        }
    )


# --- Plan 3 B0: evidence-driven bounded refinement ---------------------------
#
# The legacy gate above keys on `InvestigationPlan.refinement_recommended`, which
# has been hardcoded False since the guided LLM proposer was retired (Plan 2
# B1=RETIRE) — so guided investigation was permanently one-round. The functions
# below supply the round-varying input Plan 2's B2-R2 note identified as missing:
# the evidence keys the collection actually produced, plus a plan fingerprint so
# a round that would re-plan identically never runs.
#
# Deliberately absent: any LLM proposer, and any "collected N items so another
# round is warranted" heuristic. Counting is not evidence of a *different* plan.

GUIDED_REFINEMENT_REASONS = frozenset(
    {
        "new_evidence_with_open_gap",
        "no_new_evidence",
        "evidence_satisfied",
        "plan_unchanged",
        "round_bound_reached",
        "no_execution_contract",
    }
)


@dataclass(frozen=True)
class GuidedRefinementOutcome:
    """Why another guided round did or did not run. Always traced."""

    refine: bool
    reason: str
    unresolved_gaps: list[str] = field(default_factory=list)


def _channel_is_populated(value: Any) -> bool:
    """Empty evidence is honest negative evidence, never grounds for a new round."""
    if value is None:
        return False
    if isinstance(value, Mapping):
        return any(_channel_is_populated(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return len(value) > 0
    if isinstance(value, str):
        return bool(value.strip())
    return True


def produced_evidence_keys_from_state(
    contract: "ExecutionContract | None",
    state: Mapping[str, Any],
) -> set[str]:
    """Contract evidence keys whose backing state channel actually carries data."""
    if contract is None:
        return set()
    produced: set[str] = set()
    for step in contract.steps:
        for key in step.produces_evidence_keys:
            root = str(key).split(".")[0]
            if _channel_is_populated(state.get(root)):
                produced.add(key)
    return produced


def guided_plan_fingerprint(plan: Any) -> str:
    """Stable identity of a plan's executable shape — step ids, purposes, resources.

    Deliberately excludes status and provenance: a re-plan that only changes
    bookkeeping is the same plan and must not buy another round.
    """
    if plan is None:
        return ""
    parts = [
        f"{step.step_id}:{step.purpose}:{step.resource_id}"
        for step in getattr(plan, "steps", [])
    ]
    return "|".join(parts)


def evaluate_guided_refinement(
    *,
    contract: "ExecutionContract | None",
    previous_produced_keys: set[str],
    current_produced_keys: set[str],
    rounds_used: int,
    previous_fingerprint: str,
    current_fingerprint: str,
) -> GuidedRefinementOutcome:
    """Authorize one more bounded round only on genuinely round-varying input.

    Order matters: the hard cap is checked first so no evidence or plan state can
    talk past it.
    """
    from app.planner.resource_plan_execution_handoffs import evaluate_unresolved_gaps

    gaps = evaluate_unresolved_gaps(contract, produced_keys=current_produced_keys)

    if rounds_used >= MAX_GUIDED_INVESTIGATION_ROUNDS:
        return GuidedRefinementOutcome(False, "round_bound_reached", gaps)
    if contract is None:
        return GuidedRefinementOutcome(False, "no_execution_contract", gaps)
    if not current_produced_keys - previous_produced_keys:
        return GuidedRefinementOutcome(False, "no_new_evidence", gaps)
    if not gaps:
        return GuidedRefinementOutcome(False, "evidence_satisfied", gaps)
    if previous_fingerprint and previous_fingerprint == current_fingerprint:
        return GuidedRefinementOutcome(False, "plan_unchanged", gaps)
    return GuidedRefinementOutcome(True, "new_evidence_with_open_gap", gaps)


def count_collected_guided_hops(mcp_evidence: list[dict[str, Any]] | None) -> int:
    """Count hops whose outcome is collected — planned hops are excluded."""
    return sum(
        1
        for hop in mcp_evidence or []
        if isinstance(hop, dict) and str(hop.get("outcome") or "") == "collected"
    )
