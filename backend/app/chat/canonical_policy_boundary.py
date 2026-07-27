"""Authoritative canonical unsafe-action policy boundary (Item 21)."""

from __future__ import annotations

from typing import Any

from app.chat.contracts.gap_resolution import GapResolutionResult
from app.chat.post_guided_completeness import PostGuidedCompletenessResult

POLICY_REASON_UNSAFE_ACTION = "unsafe_action_blocked"


def resolve_canonical_policy_block_reason(
    *,
    intent_classification: dict[str, Any] | None,
    query_understanding: Any,
    gap: GapResolutionResult | None = None,
    post: PostGuidedCompletenessResult | None = None,
) -> str | None:
    """Return a typed policy reason when the request must not plan or execute."""
    if post is not None and post.status == "policy_blocked":
        return POLICY_REASON_UNSAFE_ACTION
    if gap is not None and gap.resolution_status == "policy_blocked":
        return POLICY_REASON_UNSAFE_ACTION
    if not isinstance(intent_classification, dict):
        return None
    from app.chat.planning_decision import _unsafe_containment_detected

    if _unsafe_containment_detected(intent_classification, query_understanding):
        return POLICY_REASON_UNSAFE_ACTION
    return None
