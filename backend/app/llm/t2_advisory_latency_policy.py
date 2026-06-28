"""Bounded advisory latency for non-frozen-T0 / T2 / out-of-registry review-only turns.

Frozen-T0 catalogue rows (exact-105, explicit t0_exact_authority) keep their own
2s intent-advisor cap in ``pipeline.graph_node_query_to_intent``. This module
covers every other advisory-eligible turn where a slow on-prem model must not
block ``/chat`` for 60–120s: out-of-registry hunts, T1 SPL-meta rows, near/semantic
105, and catalogue rows without frozen intent authority.

Policy is trace-only for authority — deterministic routing, SPL, MITRE, and
execution gates are unchanged; a timed-out advisor simply falls back.
"""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.use_cases.routing_authority import (
    llm_advisory_recommended,
    sidecar_intent_is_t0,
)

_T2_BOUND_REASON = "t2_review_only_advisory_bounded"


def t2_intent_advisor_bound_seconds() -> float:
    configured = float(
        getattr(settings, "ai_soc_llm_t2_intent_advisor_bound_seconds", 25.0) or 25.0
    )
    return max(1.0, configured)


def t2_turn_deadline_seconds() -> float:
    configured = float(
        getattr(settings, "ai_soc_llm_t2_turn_deadline_seconds", 45.0) or 45.0
    )
    return max(5.0, configured)


def should_bound_t2_intent_advisor(
    *,
    match_path: str | None,
    catalog_row: dict[str, Any] | None,
    registry_warnings: list[str] | None,
    skip_advisory: bool,
    preliminary_signals: dict[str, Any] | None = None,
) -> tuple[bool, str | None]:
    """Return (bound, reason) for a non-frozen-T0 advisory intent hop."""
    if skip_advisory:
        return False, None
    signals = preliminary_signals or {}
    if signals.get("non_soc_or_out_of_scope"):
        return False, None
    if signals.get("action_or_containment_shaped"):
        return False, None
    if sidecar_intent_is_t0(
        match_path,
        catalog_row=catalog_row,
        registry_warnings=registry_warnings,
    ):
        return False, None
    if llm_advisory_recommended(
        match_path,
        catalog_row=catalog_row,
        registry_warnings=registry_warnings,
    ):
        return True, _T2_BOUND_REASON
    return False, None


def cap_turn_deadline_for_t2_advisory(
    *,
    match_path: str | None,
    catalog_row: dict[str, Any] | None,
    registry_warnings: list[str] | None,
    selected_skill: str | None,
    base_deadline: float,
) -> float:
    """Clamp the per-turn wall-clock budget for advisory-eligible non-frozen-T0 rows."""
    if sidecar_intent_is_t0(
        match_path,
        catalog_row=catalog_row,
        registry_warnings=registry_warnings,
    ):
        return base_deadline
    if llm_advisory_recommended(
        match_path,
        catalog_row=catalog_row,
        registry_warnings=registry_warnings,
    ):
        return min(base_deadline, t2_turn_deadline_seconds())
    if str(selected_skill or "").strip() == "guided_investigation":
        return min(base_deadline, t2_turn_deadline_seconds())
    return base_deadline


def enrich_intent_advisory_trace(
    trace: dict[str, Any],
    *,
    bound_reason: str | None,
    bound_timeout_seconds: float | None,
    dropped_reasons: list[str] | None,
    llm_called: bool,
    adjudication_status: str | None = None,
) -> dict[str, Any]:
    """Attach standard latency-hardening trace fields (advisory-only, not authority)."""
    reasons = list(dropped_reasons or [])
    timed_out = "llm_timed_out" in reasons
    deferred = any(
        reason in reasons
        for reason in (
            "insufficient_deadline_reserve",
            "turn_budget_exhausted",
            "llm_intent_advisor_disabled",
            "llm_disabled",
            "no_provider_configured",
        )
    )
    fallback_reason = reasons[0] if reasons else None
    deterministic_fallback = bool(reasons) and not (
        adjudication_status in {"accepted", "promoted", "corrected"} and llm_called and not timed_out
    )
    classification_source = "deterministic"
    if llm_called and not timed_out and adjudication_status in {
        "accepted",
        "promoted",
        "corrected",
    }:
        classification_source = "llm_advisory"
    elif llm_called and timed_out:
        classification_source = "deterministic_fallback_after_timeout"

    enriched = {
        **trace,
        "llm_advisory_status": (
            "timed_out"
            if timed_out
            else ("deferred" if deferred else ("completed" if llm_called else "skipped"))
        ),
        "llm_advisory_timed_out": timed_out,
        "llm_advisory_deferred": deferred,
        "llm_advisory_budget_ms": (
            int(round(bound_timeout_seconds * 1000)) if bound_timeout_seconds is not None else None
        ),
        "llm_advisory_fallback_reason": fallback_reason,
        "advisory_classification_source": classification_source,
        "deterministic_fallback_used": deterministic_fallback,
    }
    if bound_reason is not None:
        enriched["intent_advisor_bound_reason"] = bound_reason
        if bound_timeout_seconds is not None:
            enriched["intent_advisor_bound_timeout_ms"] = int(
                round(bound_timeout_seconds * 1000)
            )
    return enriched
