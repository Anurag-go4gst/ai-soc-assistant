"""Reconstruct query_to_intent from a persisted clarification handoff on resume."""

from __future__ import annotations

from typing import Any

from app.chat.canonical_handoff_models import CanonicalHandoffRecord
from app.chat.intent_classifier import _family_from_promoted_skill, build_query_to_intent

_CLARIFICATION_STUB_GOALS = frozenset({"clarification"})

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
        "reference_lookup",
    }
)

_CANONICAL_GOAL_ALIASES = {
    "live_investigation": "live_results",
    "guided_investigation": "analyst_action_guidance",
    "reference_explanation": "reference_lookup",
}


def normalize_resume_answer_goal(goal: str) -> str:
    """Map routing/canonical goal strings onto IntentClassification answer goals."""
    normalized = str(goal or "").strip()
    if not normalized or normalized in _CLARIFICATION_STUB_GOALS:
        return ""
    if normalized in _CANONICAL_GOAL_ALIASES:
        return _CANONICAL_GOAL_ALIASES[normalized]
    if normalized in _VALID_ANSWER_GOALS:
        return normalized
    return ""


def resume_answer_goal_for_skill(primary_skill: str) -> str:
    skill = str(primary_skill or "").strip().lower()
    if skill == "guided_investigation":
        return "analyst_action_guidance"
    if skill in {"knowledge_recall", "retrieve_approved_context"}:
        return "reference_lookup"
    if skill in {"spl_generation", "spl_search", "aggregate_and_rank", "threshold_anomaly"}:
        return "spl_artifact"
    return "live_results"


def _resume_answer_goal(
    *,
    primary_skill: str,
    routing: dict[str, Any],
    original_answer_goal: str | None,
) -> str:
    """Restore the pre-clarification answer goal; turn-1 routing keeps clarification stubs."""
    stored = normalize_resume_answer_goal(str(original_answer_goal or ""))
    if stored:
        return stored
    routing_goal = normalize_resume_answer_goal(str(routing.get("answer_goal") or ""))
    if routing_goal:
        return routing_goal
    return resume_answer_goal_for_skill(primary_skill)


def query_to_intent_contract_error(q2i: Any) -> str | None:
    """Return a stable failure reason when the query_to_intent contract is incomplete."""
    if not isinstance(q2i, dict):
        return "missing_query_to_intent"
    signals = q2i.get("query_signals")
    if not isinstance(signals, dict):
        return "missing_query_signals"
    intent = q2i.get("intent_classification")
    if not isinstance(intent, dict):
        return "missing_intent_classification"
    if not (intent.get("primary_intent") or intent.get("intent_family")):
        return "incomplete_intent_classification"
    return None


def build_intent_classification_from_handoff(
    *,
    resumed_record: CanonicalHandoffRecord,
    routing: dict[str, Any],
) -> dict[str, Any] | None:
    primary_skill = str(
        resumed_record.original_skill
        or routing.get("original_skill")
        or routing.get("primary_skill")
        or ""
    ).strip()
    if not primary_skill:
        return None
    answer_goal = _resume_answer_goal(
        primary_skill=primary_skill,
        routing=routing,
        original_answer_goal=resumed_record.original_answer_goal,
    )
    intent_family = _family_from_promoted_skill(
        primary_skill,
        routing.get("match_path"),
    )
    return {
        "intent_family": intent_family,
        "primary_intent": primary_skill,
        "answer_goal_primary": answer_goal,
        "answer_goal": [answer_goal] if answer_goal else [],
        "query_type": "investigation_with_guidance",
        "confidence": 0.8,
        "confidence_band": "high",
        "llm_intent_status": routing.get("intent_source", "diversion"),
        "requires_clarification": False,
        "requires_hil": False,
        "action_mode": "recommend_only",
        "reason": "handoff_resume",
    }


def reconstruct_query_to_intent_for_resume(
    *,
    resumed_record: CanonicalHandoffRecord,
    merged_canonical: dict[str, Any],
    query: str,
    query_understanding: Any,
    routed: dict[str, Any],
) -> dict[str, Any] | None:
    """Rebuild the full query_to_intent contract from persisted handoff state."""
    routing = dict(merged_canonical.get("routing") or {})
    intent_classification = build_intent_classification_from_handoff(
        resumed_record=resumed_record,
        routing=routing,
    )
    if intent_classification is None:
        return None
    resume_q2i = build_query_to_intent(
        query=query,
        query_understanding=query_understanding,
        routed_skill=str(routed.get("skill") or intent_classification.get("primary_intent")),
        routing_provenance=routed.get("routing_provenance")
        if isinstance(routed.get("routing_provenance"), dict)
        else None,
    )
    payload = resume_q2i.model_dump()
    payload["intent_classification"] = intent_classification
    payload["handoff_resume"] = True
    payload["resume_provenance"] = {
        "handoff_id": resumed_record.handoff_id,
        "handoff_version": resumed_record.handoff_version,
        "original_skill": resumed_record.original_skill,
        "original_use_case_id": resumed_record.original_use_case_id,
        "original_answer_goal": resumed_record.original_answer_goal,
        "initial_tier": resumed_record.initial_tier,
        "resolved_tier": resumed_record.resolved_tier,
        "gap_resolution": resumed_record.gap_resolution,
    }

    detail = dict(merged_canonical.get("detail_state") or {})
    field_values = dict(detail.get("field_values") or {})
    if field_values:
        signals = dict(payload.get("query_signals") or {})
        signals["handoff_field_values"] = field_values
        payload["query_signals"] = signals

    candidate_mappings = dict(payload.get("candidate_mappings") or {})
    if routing.get("match_path") and not candidate_mappings.get("match_path"):
        candidate_mappings["match_path"] = routing.get("match_path")
    if resumed_record.original_use_case_id and not candidate_mappings.get("mapped_use_case_id"):
        candidate_mappings["mapped_use_case_id"] = resumed_record.original_use_case_id
    if routing.get("use_case_id") and not candidate_mappings.get("mapped_use_case_id"):
        candidate_mappings["mapped_use_case_id"] = routing.get("use_case_id")
    payload["candidate_mappings"] = candidate_mappings

    if query_to_intent_contract_error(payload):
        return None
    return payload
