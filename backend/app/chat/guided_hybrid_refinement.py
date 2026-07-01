"""Bounded refinement loop for guided hybrid dispatch (REV4 batch 2 P13a)."""

from __future__ import annotations

from typing import Any

from app.chat.contracts.investigation_plan import InvestigationPlan

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


def count_collected_guided_hops(mcp_evidence: list[dict[str, Any]] | None) -> int:
    """Count hops whose outcome is collected — planned hops are excluded."""
    return sum(
        1
        for hop in mcp_evidence or []
        if isinstance(hop, dict) and str(hop.get("outcome") or "") == "collected"
    )
