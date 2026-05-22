from __future__ import annotations

from typing import Any

from app.config import settings
from app.routing.skills import valid_skill


def adjudicate_route(comparison: dict[str, Any], threshold: float | None = None) -> dict[str, Any]:
    deterministic = comparison["deterministic"]
    llm_shadow = comparison.get("llm_shadow") or comparison.get("planner")
    selected, reason = select_route(deterministic, llm_shadow, threshold)
    return {"selected": selected, "reason": reason}


def select_route(
    deterministic: dict[str, Any],
    llm_shadow: dict[str, Any],
    threshold: float | None = None,
) -> tuple[dict[str, Any], str]:
    threshold = settings.routing_deterministic_threshold if threshold is None else threshold
    deterministic_confidence = float(deterministic.get("confidence", 0))
    llm_confidence = float(llm_shadow.get("confidence", 0))

    if deterministic_confidence >= threshold:
        return deterministic, "deterministic router confidence reached threshold"

    if valid_skill(llm_shadow.get("skill")) and llm_confidence > deterministic_confidence and llm_confidence >= threshold:
        return llm_shadow, "deterministic confidence low; llm shadow had higher valid confidence"

    return {
        "skill": "knowledge_recall",
        "tool_plan": ["needs_clarification"],
        "confidence": max(deterministic_confidence, llm_confidence),
        "reasons": ["insufficient evidence; needs clarification before tool execution"],
    }, "both routers below confidence threshold"
