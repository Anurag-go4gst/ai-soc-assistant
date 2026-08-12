"""Build ResolvedQueryContract from deterministic inputs — no provisional route."""

from __future__ import annotations

from typing import Any

from app.chat.contracts.canonical_planning_input import CatalogueTier
from app.chat.contracts.intent_classification import IntentClassification, QueryToIntentResult
from app.chat.contracts.resolved_query import (
    AmbiguityState,
    AnswerGoal,
    ResolvedQueryContract,
    UnderstandingSource,
)
from app.chat.intent_classifier import build_query_to_intent
from app.chat.skill_intent_compatibility import (
    CAPABILITY_MCP,
    CAPABILITY_SPL,
    _INTENT_NO_CAPABILITY,
    _INTENT_REQUIRED_CAPABILITIES,
)

_FAMILY_TO_ANSWER_GOAL: dict[str, AnswerGoal] = {
    "alert_summary": "severity_assessment",
    "knowledge_only": "policy_citation",
    "reference_knowledge": "reference_explanation",
    "clarification_required": "clarification",
    "spl_generation_only": "spl_artifact",
    "live_investigation": "live_results",
    "guided_investigation": "procedural_steps",
    "mitre_explanation": "mitre_explanation",
    "mitre_mapping": "mitre_mapping",
    "hybrid_alert_review": "live_results",
    "hybrid_investigation_plus_policy": "analyst_action_guidance",
    "policy_knowledge": "policy_citation",
    "sop_or_playbook": "procedural_steps",
    "cve_investigation": "reference_lookup",
    "github_investigation": "procedural_steps",
}


def capabilities_for_intent_family(intent_family: str) -> tuple[frozenset[str], frozenset[str]]:
    """Required and prohibited capabilities implied by an intent family.

    Reuses Plan 3 B2 tables — not a second capability authority.
    """
    if intent_family in _INTENT_REQUIRED_CAPABILITIES:
        return _INTENT_REQUIRED_CAPABILITIES[intent_family], frozenset()
    if intent_family in _INTENT_NO_CAPABILITY:
        return frozenset(), frozenset({CAPABILITY_SPL, CAPABILITY_MCP})
    return frozenset(), frozenset()


def _capabilities_for_family(intent_family: str) -> tuple[frozenset[str], frozenset[str]]:
    return capabilities_for_intent_family(intent_family)


def _ambiguity_state(intent: IntentClassification) -> AmbiguityState:
    if intent.requires_clarification:
        if intent.primary_intent == "human_review":
            return "policy_blocked" if intent.intent_family == "clarification_required" else "clarification_required"
        return "clarification_required"
    if intent.intent_family == "clarification_required":
        return "clarification_required"
    return "unambiguous"


_VALID_ANSWER_GOALS = frozenset(
    {
        "live_results",
        "analyst_action_guidance",
        "policy_citation",
        "spl_artifact",
        "mitre_mapping",
        "mitre_explanation",
        "severity_assessment",
        "procedural_steps",
        "clarification",
        "reference_lookup",
        "reference_explanation",
    }
)


def _answer_goal(intent: IntentClassification) -> AnswerGoal:
    primary = getattr(intent, "answer_goal_primary", None)
    if isinstance(primary, str) and primary in _VALID_ANSWER_GOALS:
        return primary  # type: ignore[return-value]
    goals = intent.answer_goal or []
    if goals and str(goals[0]) in _VALID_ANSWER_GOALS:
        return str(goals[0])  # type: ignore[return-value]
    return _FAMILY_TO_ANSWER_GOAL.get(intent.intent_family, "analyst_action_guidance")


def build_resolved_query_contract(
    *,
    query: str,
    query_understanding: Any | None = None,
    qualification_tier: CatalogueTier,
    qualification_source: str,
    understanding_source: UnderstandingSource = "deterministic_qualification",
    query_to_intent: QueryToIntentResult | dict[str, Any] | None = None,
    evidence_requirements: list[str] | None = None,
    provenance: dict[str, Any] | None = None,
) -> ResolvedQueryContract:
    """Produce pre-route understanding without reading the provisional routed skill."""
    if query_to_intent is None:
        q2i = build_query_to_intent(
            query=query,
            query_understanding=query_understanding,
            routed_skill=None,
            routing_provenance=None,
        )
    elif isinstance(query_to_intent, QueryToIntentResult):
        q2i = query_to_intent
    else:
        q2i = QueryToIntentResult.model_validate(query_to_intent)

    intent = q2i.intent_classification
    required, prohibited = _capabilities_for_family(intent.intent_family)
    entities: dict[str, Any] = {}
    time_scope: str | None = None
    if query_understanding is not None:
        entities = dict(getattr(query_understanding, "entities", None) or {})
        time_scope = getattr(query_understanding, "time_window", None)

    ambiguity = _ambiguity_state(intent)
    return ResolvedQueryContract(
        normalized_goal=query.strip(),
        intent_family=intent.intent_family,
        answer_goal=_answer_goal(intent),
        ambiguity_state=ambiguity,
        clarification_required=bool(intent.requires_clarification),
        clarification_reason=intent.reason if intent.requires_clarification else None,
        required_capabilities=required,
        prohibited_capabilities=prohibited,
        evidence_requirements=list(evidence_requirements or []),
        entities=entities,
        time_scope=time_scope,
        qualification_tier=qualification_tier,
        qualification_source=qualification_source,
        confidence=float(intent.confidence),
        provenance={
            **(provenance or {}),
            "match_path": (q2i.candidate_mappings or {}).get("match_path"),
            "llm_intent_assist_status": q2i.llm_intent_assist_status,
        },
        understanding_source=understanding_source,
    )
