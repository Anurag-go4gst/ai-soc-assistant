"""Review-only SPL preview gate for guided hybrid dispatch (REV4 P7)."""

from __future__ import annotations

from typing import Any

from app.spl.draft_preview import build_draft_preview


def build_guided_spl_draft_preview_if_allowed(
    *,
    query: str,
    evidence_plan: dict[str, Any] | Any,
    investigation_plan: Any,
    unsafe_enforcement: bool = False,
    llm_intent_advisory: dict[str, Any] | None = None,
    query_understanding: Any | None = None,
) -> dict[str, Any] | None:
    """Gate SPL draft on ``spl_review_allowed`` and ``spl_review_requested``."""
    if isinstance(evidence_plan, dict):
        spl_review_allowed = bool(evidence_plan.get("spl_review_allowed"))
    else:
        spl_review_allowed = bool(getattr(evidence_plan, "spl_review_allowed", False))
    spl_review_requested = bool(getattr(investigation_plan, "spl_review_requested", False))
    if not spl_review_allowed or not spl_review_requested:
        return None
    return build_draft_preview(
        query,
        unsafe_enforcement=unsafe_enforcement,
        llm_intent_advisory=llm_intent_advisory,
        query_understanding=query_understanding,
    )
