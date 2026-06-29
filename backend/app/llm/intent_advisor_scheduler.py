"""Intent-advisor scheduling policy: protected reserve, T0 override, trace fields."""

from __future__ import annotations

import time
from typing import Any

from app.config import settings
from app.llm.sidecar_clients import INTENT_ROLE, build_failover_client_for_role
from app.llm.turn_llm_budget import (
    TurnLlmBudget,
    downstream_optional_reserve_seconds,
    intent_advisor_reserve_seconds,
)
from app.query_understanding.models import QueryUnderstandingResult


def intent_advisor_provider_configured() -> bool:
    """True when the intent advisor sidecar can invoke a configured provider."""
    if not settings.ai_soc_llm_intent_advisor_enabled:
        return False
    if not settings.ai_soc_llm_enabled or settings.ai_soc_llm_mode.strip().lower() == "disabled":
        return False
    return build_failover_client_for_role(INTENT_ROLE) is not None


def should_prioritize_intent_advisor(
    query: str,
    query_understanding: QueryUnderstandingResult | None,
    candidate_mappings: dict[str, Any],
    preliminary_signals: dict[str, Any],
) -> bool:
    """Override Tier-T0 skip when live log retrieval needs entity-slot assistance."""
    del query, query_understanding  # reserved for future shape checks
    if preliminary_signals.get("guidance_request"):
        return False
    if preliminary_signals.get("non_soc_or_out_of_scope"):
        return False
    if preliminary_signals.get("action_or_containment_shaped"):
        return False
    match_path = str(candidate_mappings.get("match_path") or "").strip()
    if match_path not in {"", "out_of_registry", "llm_promoted_with_registry_validation"}:
        return False
    return bool(
        preliminary_signals.get("explicit_log_search")
        or preliminary_signals.get("live_data_request")
        or preliminary_signals.get("ambiguous_t2_query")
        or preliminary_signals.get("meaningful_t2_entities")
        or preliminary_signals.get("explicit_spl_authoring")
        or preliminary_signals.get("spl_authoring_shaped")
    )


def build_intent_scheduling_trace(
    *,
    budget: TurnLlmBudget,
    skip_policy: str | None,
    provider_configured: bool,
    elapsed_before_call_ms: int | None = None,
    fallback_reason_if_skipped: str | None = None,
    route_selected_after_skip: str | None = None,
) -> dict[str, Any]:
    remaining = budget.remaining_seconds()
    intent_reserve = intent_advisor_reserve_seconds()
    downstream_reserve = downstream_optional_reserve_seconds()
    return {
        "intent_advisor_deadline_remaining_ms": (
            int(round(remaining * 1000)) if remaining is not None else None
        ),
        "intent_advisor_required_reserve_ms": int(round(intent_reserve * 1000)),
        "intent_advisor_elapsed_before_call_ms": elapsed_before_call_ms,
        "intent_advisor_provider_configured": provider_configured,
        "intent_advisor_skip_policy": skip_policy,
        "downstream_budget_reserved_ms": int(round(downstream_reserve * 1000)),
        "fallback_reason_if_intent_skipped": fallback_reason_if_skipped,
        "route_selected_after_intent_skip": route_selected_after_skip,
    }


def intent_advisor_hop_blocked(budget: TurnLlmBudget) -> str | None:
    """Budget gate for intent advisor using the protected intent reserve."""
    if budget.sidecar_calls >= budget.max_sidecar_calls:
        return "turn_budget_exhausted"
    if budget.time_budget_exhausted():
        return "turn_budget_exhausted"
    reserve = intent_advisor_reserve_seconds()
    if not budget.can_start_call(reserve_seconds=reserve):
        return "insufficient_deadline_reserve"
    return None


def intent_elapsed_before_call_ms(budget: TurnLlmBudget) -> int:
    return int(max(0.0, (time.monotonic() - budget.started_at) * 1000))
