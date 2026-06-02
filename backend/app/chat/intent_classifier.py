"""Deterministic intent classification for the chat control plane (Stage 1A)."""

from __future__ import annotations

from typing import Any

from app.chat.contracts.intent_classification import (
    ActionMode,
    AnswerGoal,
    ConfidenceBand,
    IntentClassification,
    LlmIntentAssistStatus,
    QueryToIntentResult,
)
from app.chat.query_signals import extract_query_signals
from app.query_understanding.models import QueryUnderstandingResult


def build_candidate_mappings(
    query_understanding: QueryUnderstandingResult | None,
    *,
    routed_skill: str | None = None,
) -> dict[str, Any]:
    if query_understanding is None:
        return {
            "question_ref": None,
            "use_case_ids": [],
            "match_path": "out_of_registry",
            "legacy_skill_hint": routed_skill,
        }
    return {
        "question_ref": query_understanding.mapped_question_ref,
        "use_case_ids": list(query_understanding.mapped_use_case_ids or []),
        "match_path": query_understanding.deterministic_match_path or "out_of_registry",
        "legacy_skill_hint": routed_skill or query_understanding.mapped_primary_skill,
    }


def classify_intent(
    *,
    query: str,
    signals: dict[str, Any],
    candidate_mappings: dict[str, Any],
    query_understanding: QueryUnderstandingResult | None = None,
) -> IntentClassification:
    if signals.get("block_or_contain"):
        return _build_classification(
            intent_family="clarification_required",
            primary_intent="human_review",
            query_type="ask_for_next_action",
            answer_goal=["clarification", "analyst_action_guidance"],
            confidence=0.82,
            requires_clarification=True,
            requires_hil=True,
            action_mode="recommend_only",
            reason="Destructive or containment action requires human review and overrides SPL generation.",
            requested_output_type="ACTION_PLAN",
        )

    if signals.get("spl_generation"):
        return _build_classification(
            intent_family="spl_generation_only",
            primary_intent="spl_generation",
            query_type="ask_for_query_generation",
            answer_goal=["spl_artifact"],
            confidence=0.9,
            requires_clarification=False,
            reason="User requested SPL generation.",
            requested_output_type="SPL",
        )

    if signals.get("mitre_explain"):
        return _build_classification(
            intent_family="mitre_explanation",
            primary_intent="mitre_explanation",
            query_type="ask_for_explanation",
            answer_goal=["mitre_explanation"],
            confidence=0.88,
            requires_clarification=False,
            reason="User asked for MITRE technique explanation.",
            requested_output_type="MITRE_MAPPING",
        )

    if signals.get("mitre_map"):
        needs_clarification = bool(signals.get("mitre_requires_alert_context"))
        return _build_classification(
            intent_family="mitre_mapping",
            primary_intent="mitre_mapping",
            query_type="ask_for_mapping",
            answer_goal=["mitre_mapping"] if not needs_clarification else ["clarification"],
            confidence=0.75 if needs_clarification else 0.85,
            requires_clarification=needs_clarification,
            reason="MITRE mapping request without sufficient alert context."
            if needs_clarification
            else "User requested MITRE mapping.",
            requested_output_type="MITRE_MAPPING",
        )

    if signals.get("procedural_investigation") and not signals.get("live_investigation_verbs"):
        return _build_classification(
            intent_family="knowledge_only",
            primary_intent="knowledge_recall",
            query_type="ask_for_explanation",
            answer_goal=["procedural_steps"],
            confidence=0.86,
            requires_clarification=False,
            reason="User asked for procedural investigation guidance.",
            requested_output_type="INVESTIGATION",
        )

    if signals.get("playbook_procedure") and not signals.get("live_investigation_verbs"):
        return _build_classification(
            intent_family="sop_or_playbook",
            primary_intent="knowledge_recall",
            query_type="sop_or_playbook",
            answer_goal=["procedural_steps", "policy_citation"],
            confidence=0.86,
            requires_clarification=False,
            reason="User asked for SOP/playbook/runbook guidance.",
            requested_output_type="SOP",
        )

    policy_intent = signals.get("policy_terms") or signals.get("escalation_without_policy_word")
    live_data_intent = signals.get("live_investigation_verbs") and (
        signals.get("failed_login") or signals.get("time_window_24h") or "investigate" in signals.get("normalized_query", "")
    )

    if policy_intent and not live_data_intent:
        return _build_classification(
            intent_family="policy_knowledge",
            primary_intent="knowledge_recall",
            query_type="ask_for_policy",
            answer_goal=["policy_citation"],
            confidence=0.88,
            requires_clarification=False,
            reason="User asked for escalation/policy knowledge without a live investigation request.",
            requested_output_type="SOP",
        )

    if signals.get("knowledge_definition") and not signals.get("live_investigation_verbs") and not policy_intent:
        return _build_classification(
            intent_family="knowledge_only",
            primary_intent="knowledge_recall",
            query_type="ask_for_explanation",
            answer_goal=["procedural_steps"],
            confidence=0.84,
            requires_clarification=False,
            reason="Definitional knowledge question.",
            requested_output_type="INVESTIGATION",
        )

    hybrid_markers = (
        live_data_intent
        and (signals.get("analyst_action") or signals.get("playbook_procedure") or signals.get("dga"))
    )
    if hybrid_markers:
        goals: list[AnswerGoal] = ["live_results"]
        if signals.get("analyst_action"):
            goals.append("analyst_action_guidance")
        if signals.get("playbook_procedure"):
            goals.append("procedural_steps")
        return _build_classification(
            intent_family="hybrid_investigation_plus_policy",
            primary_intent="live_investigation",
            secondary_intents=["analyst_action_guidance"] if signals.get("analyst_action") else [],
            query_type="investigation_with_guidance",
            answer_goal=goals,
            confidence=0.87,
            requires_clarification=False,
            reason="Live investigation combined with analyst guidance or procedural playbook context.",
            requested_output_type="INVESTIGATION",
        )

    if live_data_intent:
        return _build_classification(
            intent_family="live_investigation",
            primary_intent="attack_discovery",
            query_type="ask_for_live_results",
            answer_goal=["live_results"],
            confidence=0.86,
            requires_clarification=False,
            reason="User requested live investigative results.",
            requested_output_type="INVESTIGATION",
        )

    return _build_classification(
        intent_family="clarification_required",
        primary_intent="knowledge_recall",
        query_type="ask_for_explanation",
        answer_goal=["clarification"],
        confidence=0.45,
        requires_clarification=True,
        reason="Insufficient deterministic intent signals; clarification recommended.",
        requested_output_type=None,
    )


def build_query_to_intent(
    *,
    query: str,
    query_understanding: QueryUnderstandingResult | None = None,
    routed_skill: str | None = None,
) -> QueryToIntentResult:
    signals = extract_query_signals(query, query_understanding)
    candidate_mappings = build_candidate_mappings(query_understanding, routed_skill=routed_skill)
    intent = classify_intent(
        query=query,
        signals=signals,
        candidate_mappings=candidate_mappings,
        query_understanding=query_understanding,
    )
    conflicts = _intent_conflicts(intent, candidate_mappings, query_understanding)
    llm_status = _llm_intent_assist_status(query_understanding, candidate_mappings)
    return QueryToIntentResult(
        query_signals=signals,
        candidate_mappings=candidate_mappings,
        intent_classification=intent,
        intent_conflicts=conflicts,
        llm_intent_assist_status=llm_status,
    )


def _build_classification(
    *,
    intent_family: str,
    primary_intent: str,
    query_type: str,
    answer_goal: list[AnswerGoal],
    confidence: float,
    requires_clarification: bool,
    reason: str,
    requested_output_type: str | None = None,
    secondary_intents: list[str] | None = None,
    requires_hil: bool = False,
    action_mode: ActionMode | None = None,
) -> IntentClassification:
    return IntentClassification(
        intent_family=intent_family,  # type: ignore[arg-type]
        primary_intent=primary_intent,
        secondary_intents=list(secondary_intents or []),
        query_type=query_type,  # type: ignore[arg-type]
        answer_goal=answer_goal,
        requested_output_type=requested_output_type,
        confidence=confidence,
        confidence_band=_confidence_band(confidence),
        requires_clarification=requires_clarification,
        requires_hil=requires_hil,
        action_mode=action_mode,
        reason=reason,
    )


def _confidence_band(score: float) -> ConfidenceBand:
    if score >= 0.8:
        return "high"
    if score >= 0.55:
        return "medium"
    return "low"


def _intent_conflicts(
    intent: IntentClassification,
    candidate_mappings: dict[str, Any],
    query_understanding: QueryUnderstandingResult | None,
) -> list[dict[str, Any]]:
    if not query_understanding:
        return []
    warnings = list(query_understanding.registry_warnings or [])
    conflicts: list[dict[str, Any]] = []
    if "question_registry_use_case_skill_conflict" in warnings:
        conflicts.append(
            {
                "type": "registry_skill_conflict",
                "registry_skill": candidate_mappings.get("legacy_skill_hint"),
                "intent_family": intent.intent_family,
            }
        )
    legacy = candidate_mappings.get("legacy_skill_hint")
    if legacy == "attack_discovery" and intent.intent_family in {"policy_knowledge", "sop_or_playbook", "knowledge_only"}:
        conflicts.append(
            {
                "type": "intent_over_legacy_skill_hint",
                "legacy_skill_hint": legacy,
                "intent_family": intent.intent_family,
            }
        )
    return conflicts


def _llm_intent_assist_status(
    query_understanding: QueryUnderstandingResult | None,
    candidate_mappings: dict[str, Any],
) -> LlmIntentAssistStatus:
    if query_understanding is None:
        return "skipped"
    match_path = candidate_mappings.get("match_path")
    if match_path in {"near_105_question", "exact_105_question", "exact_105_plus_use_case_catalog"}:
        if query_understanding.llm_advisory_recommended or match_path == "near_105_question":
            return "accepted"
    if query_understanding.llm_advisory_recommended:
        return "attempted"
    return "skipped"
