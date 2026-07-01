"""Guided-investigation LLM turn budget and intent-advisor skip policy."""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.llm.turn_llm_budget import TurnLlmBudget


def guided_llm_enabled() -> bool:
    return bool(settings.ai_soc_guided_llm_enabled)


def is_guided_investigation_route(
    *,
    routed_skill: str | None,
    path_type: str | None = None,
) -> bool:
    skill = str(routed_skill or "")
    if skill == "guided_investigation":
        return True
    return str(path_type or "") == "guided_investigation"


def should_skip_intent_advisor_for_guided(
    *,
    routed_skill: str | None,
    query_signals: dict[str, Any] | None,
) -> tuple[bool, str | None]:
    """When guided LLM is on and route is already guided, do not spend the turn on intent shadow."""
    if not guided_llm_enabled():
        return False, None
    if str(routed_skill or "") != "guided_investigation":
        return False, None
    if query_signals and query_signals.get("guidance_request"):
        return True, "guided_hunt_deterministic_routing"
    return True, "guided_route_locked_skip_intent_advisor"


def build_guided_turn_budget() -> TurnLlmBudget:
    """Reserve the full turn for one guided narration/planner hop."""
    max_calls = max(1, int(getattr(settings, "ai_soc_guided_llm_max_calls", 1) or 1))
    deadline = float(getattr(settings, "ai_soc_guided_llm_timeout_seconds", 120.0) or 120.0)
    return TurnLlmBudget(
        max_sidecar_calls=0,
        max_narration_calls=max_calls,
        deadline_seconds=max(30.0, deadline),
    )


def guided_composer_timeout_seconds(budget: TurnLlmBudget) -> float | None:
    """Wall-clock timeout for the guided governed-composer hop."""
    reserve = float(
        getattr(settings, "ai_soc_guided_llm_min_final_reserve_seconds", 90.0) or 90.0
    )
    remaining = budget.remaining_seconds()
    if remaining is None:
        return reserve
    if remaining <= 1.0:
        return None
    return max(1.0, min(reserve, remaining))


def guided_turn_deadline_seconds() -> float:
    return float(getattr(settings, "ai_soc_guided_llm_timeout_seconds", 120.0) or 120.0)
