from __future__ import annotations

from typing import Any

from app.connectors.llm import get_llm_connector
from app.routing.skills import validate_skill


_TOOL_PLANS: dict[str, list[str]] = {
    "alert_summary": ["retrieve_alert_context", "prepare_time_bounded_summary"],
    "spl_generation": ["draft_spl_spec", "validate_spl_before_execution"],
    "attack_discovery": ["classify_auth_pattern", "prepare_spl_spec", "require_spl_validation"],
    "knowledge_recall": ["retrieve_approved_context", "summarize_bounded_reference"],
}


def plan_route(intent: str) -> dict[str, Any]:
    return route_skill_llm_shadow(intent)


def route_skill_llm_shadow(query: str, llm_connector: Any | None = None) -> dict[str, Any]:
    connector = llm_connector or get_llm_connector()
    completion = connector.complete_skill_routing({"query": query})
    skill = validate_skill(completion.skill)
    reasons = [completion.rationale]
    if completion.insufficient_evidence:
        reasons.append("llm reported insufficient evidence")
    return {
        "skill": skill,
        "tool_plan": list(_TOOL_PLANS[skill]),
        "confidence": float(completion.confidence),
        "reasons": reasons,
        "metadata": dict(completion.metadata),
    }
