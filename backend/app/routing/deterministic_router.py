from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.routing.skills import validate_skill


@dataclass(frozen=True)
class RouteRule:
    skill: str
    tool_plan: tuple[str, ...]
    confidence: float
    reason: str
    any_keywords: tuple[str, ...]
    all_keywords: tuple[str, ...] = ()


AUTH_ROUTE_RULES: tuple[RouteRule, ...] = (
    RouteRule(
        skill="alert_summary",
        tool_plan=("retrieve_alert_context", "prepare_time_bounded_summary"),
        confidence=0.90,
        reason="account lockout alert/time-series wording",
        any_keywords=("lockout", "lockouts", "account_locked", "locked"),
    ),
    RouteRule(
        skill="spl_generation",
        tool_plan=("draft_spl_spec", "validate_spl_before_execution"),
        confidence=0.88,
        reason="explicit SPL generation request",
        any_keywords=("generate spl", "write spl", "produce spl", "create spl", "spl query"),
    ),
    RouteRule(
        skill="attack_discovery",
        tool_plan=("classify_auth_pattern", "prepare_spl_spec", "require_spl_validation"),
        confidence=0.86,
        reason="failed login or brute-force investigation wording",
        any_keywords=("failed login", "failed logins", "failure", "failures", "brute force", "abnormally high"),
    ),
    RouteRule(
        skill="attack_discovery",
        tool_plan=("classify_auth_pattern", "prepare_spl_spec", "require_spl_validation"),
        confidence=0.84,
        reason="success-after-failures or unusual-source investigation wording",
        any_keywords=("successful logins", "successful login", "new source", "unusual source", "unusual source ips"),
    ),
    RouteRule(
        skill="knowledge_recall",
        tool_plan=("retrieve_approved_context", "summarize_bounded_reference"),
        confidence=0.82,
        reason="top-volume knowledge/statistical recall wording",
        any_keywords=("top users", "most authentication events", "event volume", "which users had the most"),
    ),
)

LOW_CONFIDENCE_ROUTE: dict[str, Any] = {
    "skill": "knowledge_recall",
    "tool_plan": ["needs_clarification"],
    "confidence": 0.20,
    "reasons": ["insufficient evidence to select a specialized skill"],
}


def route_intent(intent: str) -> dict[str, Any]:
    return route_skill_deterministic(intent)


def route_skill_deterministic(query: str, rules: tuple[RouteRule, ...] = AUTH_ROUTE_RULES) -> dict[str, Any]:
    normalized = " ".join(query.lower().split())
    for rule in rules:
        if _matches(rule, normalized):
            validate_skill(rule.skill)
            return {
                "skill": rule.skill,
                "tool_plan": list(rule.tool_plan),
                "confidence": rule.confidence,
                "reasons": [rule.reason],
            }
    return dict(LOW_CONFIDENCE_ROUTE)


def _matches(rule: RouteRule, normalized_query: str) -> bool:
    if rule.all_keywords and not all(keyword in normalized_query for keyword in rule.all_keywords):
        return False
    return any(keyword in normalized_query for keyword in rule.any_keywords)
