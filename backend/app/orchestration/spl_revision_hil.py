"""Analyst-facing HIL reasons for review-only SPL paths."""

from __future__ import annotations

from typing import Any

_GOVERNED_TEMPLATE_PROVIDERS = frozenset(
    {
        "deterministic_template_render",
        "deterministic_user_bound_skeleton",
    }
)

_HARD_VALIDATION_PREFIXES = (
    "blocked_command:",
    "disallowed_",
    "prompt_injection",
    "structural_",
)

_NON_FINAL_EXPLICIT_REASONS = frozenset(
    {
        "",
        "spl_validation_failed",
        "candidate_spl_review_only",
    }
)


def resolve_spl_revision_hil_reason(
    spl_validation: dict[str, Any] | None,
    *,
    candidate_spl: dict[str, Any] | None = None,
) -> str:
    """Map a non-approved SPL validation to an analyst-facing HIL reason."""
    if not isinstance(spl_validation, dict):
        return "spl_validation_failed"

    reject_reasons = [str(item) for item in spl_validation.get("reject_reasons") or []]
    if any(reason.startswith(_HARD_VALIDATION_PREFIXES) for reason in reject_reasons):
        return "spl_validation_failed"

    provider = str(
        spl_validation.get("selected_candidate_spl_provider")
        or spl_validation.get("generation_mode")
        or (candidate_spl or {}).get("generation_mode")
        or ""
    ).strip()
    template_id = str(
        spl_validation.get("template_id") or (candidate_spl or {}).get("template_id") or ""
    ).strip()
    rendered = str(
        (candidate_spl or {}).get("candidate_spl")
        or spl_validation.get("normalized_spl")
        or ""
    ).strip()

    if str(spl_validation.get("llm_fallback_status") or "") == "lab_draft_fallback":
        return "lab_draft_preview_review_required"

    if template_id and provider in _GOVERNED_TEMPLATE_PROVIDERS:
        if len(rendered) > 20 or bool(reject_reasons):
            return "template_review_required"

    explicit = str(spl_validation.get("review_required_reason") or "").strip()
    if explicit and explicit not in _NON_FINAL_EXPLICIT_REASONS:
        return explicit

    return "spl_validation_failed"


def polish_spl_revision_human_review(
    human_review: dict[str, Any] | None,
    *,
    spl_validation: dict[str, Any] | None,
    candidate_spl: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Replace misleading spl_validation_failed labels when a review-only draft exists."""
    review = dict(human_review or {})
    if not review.get("required"):
        return review
    if str(review.get("review_type") or "") != "spl_revision":
        return review
    reason = str(review.get("reason") or "")
    if reason not in {"", "spl_validation_failed", "candidate_spl_review_only"}:
        return review
    updated = resolve_spl_revision_hil_reason(
        spl_validation,
        candidate_spl=candidate_spl,
    )
    if updated == reason:
        return review
    return {**review, "reason": updated}
