from __future__ import annotations

from typing import Any


def compare_routes(llm_shadow: dict[str, Any], deterministic: dict[str, Any]) -> dict[str, Any]:
    skill_match = llm_shadow.get("skill") == deterministic.get("skill")
    tool_plan_match = llm_shadow.get("tool_plan") == deterministic.get("tool_plan")
    return {
        "match": skill_match and tool_plan_match,
        "skill_match": skill_match,
        "tool_plan_match": tool_plan_match,
        "llm_shadow": llm_shadow,
        "planner": llm_shadow,
        "deterministic": deterministic,
        "confidence_delta": float(llm_shadow.get("confidence", 0)) - float(deterministic.get("confidence", 0)),
    }
