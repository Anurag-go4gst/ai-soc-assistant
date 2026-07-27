"""Post-guided completeness gate."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.chat.contracts.gap_resolution import GapResolutionResult


class PostGuidedCompletenessResult(BaseModel):
    status: Literal[
        "complete",
        "complete_with_limitations",
        "clarification_required",
        "policy_blocked",
        "resolution_failed",
    ]
    unresolved_fields: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    clarification_required: bool = False


def evaluate_post_guided_completeness(
    gap: GapResolutionResult | None,
    *,
    planner_required_fields: list[str],
    user_only_fields: list[str],
) -> PostGuidedCompletenessResult:
    if gap is None:
        return PostGuidedCompletenessResult(status="complete")

    unresolved = list(gap.unresolved_details)
    required_unresolved = [f for f in unresolved if f in planner_required_fields or f in user_only_fields]
    if gap.resolution_status == "policy_blocked":
        return PostGuidedCompletenessResult(status="policy_blocked", limitations=list(gap.limitations))
    if gap.clarification_required or required_unresolved:
        return PostGuidedCompletenessResult(
            status="clarification_required",
            unresolved_fields=required_unresolved,
            limitations=list(gap.limitations),
            clarification_required=True,
        )
    if gap.resolution_status == "resolution_failed":
        return PostGuidedCompletenessResult(
            status="resolution_failed",
            unresolved_fields=unresolved,
            limitations=list(gap.limitations),
        )
    if unresolved:
        return PostGuidedCompletenessResult(
            status="complete_with_limitations",
            unresolved_fields=unresolved,
            limitations=list(gap.limitations),
        )
    if gap.limitations:
        return PostGuidedCompletenessResult(
            status="complete_with_limitations",
            limitations=list(gap.limitations),
        )
    return PostGuidedCompletenessResult(status="complete")
