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
from app.chat.contracts.staged_sufficiency import from_understanding_state
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
        entities = _entities_map(query_understanding)
        time_scope = getattr(query_understanding, "time_window", None) or entities.get("time_window")

    ambiguity = _ambiguity_state(intent)
    contract = ResolvedQueryContract(
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
        time_scope=time_scope if isinstance(time_scope, str) else None,
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
    return attach_understanding_authority(contract)


_DERIVED_FIELD_NAMES = (
    "required_capabilities",
    "prohibited_capabilities",
    "evidence_requirements",
)

_GENERIC_ENTITY_VALUES = frozenset({"multiple", "all", "any", "several", "various", "unknown"})


def _entities_map(query_understanding: Any) -> dict[str, Any]:
    raw = getattr(query_understanding, "entities", None)
    if raw is None:
        return {}
    if hasattr(raw, "model_dump"):
        dumped = raw.model_dump()
    elif isinstance(raw, dict):
        dumped = dict(raw)
    else:
        return {}
    return {key: value for key, value in dumped.items() if value not in (None, "", [], {})}


def _is_concrete(value: Any) -> bool:
    if value in (None, "", [], {}):
        return False
    if isinstance(value, (list, tuple, set)):
        return any(_is_concrete(item) for item in value)
    text = str(value).strip().lower()
    return bool(text) and text not in _GENERIC_ENTITY_VALUES


def attach_understanding_authority(contract: ResolvedQueryContract) -> ResolvedQueryContract:
    """Classify T1–T3 locked vs unresolved semantic fields; mark derived fields.

    Does not create a second understanding system. Capabilities and evidence
    requirements stay derived from intent family / later deterministic recompute.
    """
    locked: dict[str, Any] = {
        "intent_family": contract.intent_family,
        "answer_goal": contract.answer_goal,
        "qualification_tier": contract.qualification_tier,
        "qualification_source": contract.qualification_source,
        "ambiguity_state": contract.ambiguity_state,
    }
    if contract.clarification_required:
        locked["clarification_required"] = True
        if contract.clarification_reason:
            locked["clarification_reason"] = contract.clarification_reason
    if contract.prohibited_capabilities:
        locked["prohibited_capabilities"] = sorted(contract.prohibited_capabilities)
    if contract.time_scope:
        locked["time_scope"] = contract.time_scope
    for key, value in (contract.entities or {}).items():
        if key == "time_window" and value and "time_scope" not in locked:
            locked["time_scope"] = value
            continue
        if _is_concrete(value):
            locked[f"entities.{key}"] = value
    if contract.qualification_tier != "T4":
        locked["normalized_goal"] = contract.normalized_goal

    unresolved: list[str] = []
    if contract.qualification_tier == "T4" and not contract.clarification_required:
        unresolved.append("semantic_goal")
        if not any(name.startswith("entities.") for name in locked):
            unresolved.append("investigation_target")

    sufficiency = from_understanding_state(
        required=["semantic_goal"] if contract.qualification_tier == "T4" else [],
        available=sorted(locked.keys()),
        missing=[],
        locked=sorted(locked.keys()),
        unresolved=unresolved,
        clarification_required=contract.clarification_required,
        policy_blocked=contract.ambiguity_state == "policy_blocked",
    )
    return contract.model_copy(
        update={
            "locked_fields": locked,
            "unresolved_fields": unresolved,
            "derived_field_names": list(_DERIVED_FIELD_NAMES),
            "understanding_sufficiency": sufficiency.model_dump(mode="json"),
        }
    )
