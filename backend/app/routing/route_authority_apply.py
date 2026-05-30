"""Stage 3L-S3 Step 3: Apply cov.q046 pilot operation authority to shadow compare only."""

from __future__ import annotations

from typing import Any, Final

from app.routing.route_authority_gate import RouteAuthorityEvaluation

AUTHORITY_HOLDER_LEGACY_SELECTED_SKILL: Final[str] = "legacy_selected_skill"
AUTHORITY_HOLDER_ROUTE_PLAN_PRIMARY_SKILL: Final[str] = "route_plan_primary_skill"
MIGRATION_PHASE_S3_STEP_3: Final[str] = "S3_step_3_cov_q046_pilot"


def build_authority_trace(evaluation: RouteAuthorityEvaluation) -> str:
    if evaluation.authority_applied:
        return (
            "Operation authority applied for allowlisted coverage_id "
            f"{evaluation.coverage_id!r}: planning uses route_plan.primary_skill="
            f"{evaluation.candidate_primary_skill!r}; legacy selected_skill="
            f"{evaluation.selected_skill_before!r} remains on the /chat response."
        )
    reason = evaluation.authority_fallback_reason or "unknown"
    return (
        "Operation authority not applied; legacy selected_skill remains authoritative. "
        f"fallback_reason={reason!r}."
    )


def apply_operation_authority_to_compare(
    compare: dict[str, Any],
    evaluation: RouteAuthorityEvaluation,
) -> dict[str, Any]:
    """Update route_authority_compare when Step 3 pilot gates pass (shadow/planning metadata only)."""
    if evaluation.global_enabled:
        compare["migration_phase"] = MIGRATION_PHASE_S3_STEP_3
    compare["authority_decision"] = "applied" if evaluation.authority_applied else "fallback"
    compare["authority_trace"] = build_authority_trace(evaluation)
    compare["authority_holder"] = (
        AUTHORITY_HOLDER_ROUTE_PLAN_PRIMARY_SKILL
        if evaluation.authority_applied
        else AUTHORITY_HOLDER_LEGACY_SELECTED_SKILL
    )
    compare["planning_primary_skill"] = (
        evaluation.candidate_primary_skill
        if evaluation.authority_applied
        else None
    )
    compare["legacy_selected_skill_preserved"] = evaluation.selected_skill_before
    return compare
