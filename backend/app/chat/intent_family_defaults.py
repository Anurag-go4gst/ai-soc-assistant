"""Shared intent family / answer_goal defaults for known-path stubs."""

from __future__ import annotations

from typing import Any

from app.chat.contracts.intent_classification import IntentClassification

_SKILL_DEFAULTS: dict[str, tuple[str, str]] = {
    "alert_summary": ("alert_summary", "severity_assessment"),
    "attack_discovery": ("hybrid_alert_review", "live_results"),
    "spl_generation": ("spl_generation_only", "spl_artifact"),
    "knowledge_recall": ("knowledge_only", "reference_lookup"),
    "guided_investigation": ("guided_investigation", "procedural_steps"),
}

_USE_CASE_OVERRIDES: dict[str, tuple[str, str]] = {
    "auth_failed_login_spike": ("hybrid_alert_review", "live_results"),
    "dns_beaconing_candidate": ("hybrid_alert_review", "live_results"),
}


def defaults_for_skill(
    skill: str | None,
    *,
    use_case_id: str | None = None,
) -> tuple[str, str]:
    if use_case_id and use_case_id in _USE_CASE_OVERRIDES:
        return _USE_CASE_OVERRIDES[use_case_id]
    return _SKILL_DEFAULTS.get(str(skill or "").strip(), ("live_investigation", "live_results"))


def build_known_path_intent_stub(
    *,
    skill: str,
    use_case_id: str | None = None,
    reason: str = "known_path_stub",
) -> dict[str, Any]:
    family, answer_goal = defaults_for_skill(skill, use_case_id=use_case_id)
    intent = IntentClassification(
        intent_family=family,  # type: ignore[arg-type]
        primary_intent=skill,
        query_type="ask_for_explanation",
        answer_goal=[answer_goal],  # type: ignore[list-item]
        confidence=0.85,
        confidence_band="high",
        requires_clarification=False,
        action_mode="recommend_only",
        reason=reason,
    )
    payload = intent.model_dump()
    payload["llm_intent_status"] = "skipped"
    payload["answer_goal_primary"] = answer_goal
    return payload


def build_t0_knowledge_stub(
    *,
    reference_ids: list[str] | None = None,
    reason: str = "t4_resolved_pure_knowledge",
) -> dict[str, Any]:
    intent = IntentClassification(
        intent_family="reference_knowledge",
        primary_intent="reference_knowledge",
        query_type="ask_for_explanation",
        answer_goal=["reference_lookup"],
        confidence=0.9,
        confidence_band="high",
        requires_clarification=False,
        action_mode="recommend_only",
        reason=reason,
    )
    payload = intent.model_dump()
    payload["llm_intent_status"] = "classifier"
    payload["answer_goal_primary"] = "reference_explanation"
    payload["answer_goal_wire"] = ["reference_lookup"]
    if reference_ids:
        payload["reference_ids"] = list(reference_ids)
    return payload
