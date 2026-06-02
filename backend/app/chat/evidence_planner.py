from __future__ import annotations

from typing import Any

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.contracts.intent_classification import IntentClassification


def plan_evidence(
    intent_classification: dict[str, Any] | IntentClassification,
    query_to_intent: dict[str, Any] | None = None,
    routed: dict[str, Any] | None = None,
) -> EvidencePlan:
    """Plan evidence paths from intent only.

    `query_to_intent` and `routed` are accepted for future trace/HIL hints; this
    phase deliberately avoids re-reading user text or legacy route keywords.
    """
    intent = (
        intent_classification
        if isinstance(intent_classification, IntentClassification)
        else IntentClassification.model_validate(intent_classification)
    )
    family = intent.intent_family

    if intent.requires_clarification or family == "clarification_required":
        return EvidencePlan(
            answer_mode="clarification",
            rag_phase="rag_only",
            needs_rag=False,
            needs_spl=False,
            needs_mcp=False,
            needs_mitre=False,
            spl_allowed=False,
            mcp_allowed=False,
            policy_context_required=False,
            policy_context_recommended=False,
            requires_hil=True,
            action_mode=intent.action_mode or "hil_required",
            reasons=["intent_requires_clarification"],
        )

    if family in {"policy_knowledge", "sop_or_playbook"}:
        return EvidencePlan(
            answer_mode="rag_only",
            rag_phase="rag_only",
            needs_rag=True,
            needs_spl=False,
            needs_mcp=False,
            needs_mitre=False,
            spl_allowed=False,
            mcp_allowed=False,
            policy_context_required=True,
            policy_context_recommended=False,
            rag_no_match_behavior="insufficient_policy_context",
            reasons=["policy_context_required"],
        )

    if family == "knowledge_only":
        return EvidencePlan(
            answer_mode="rag_only",
            rag_phase="rag_only",
            needs_rag=True,
            needs_spl=False,
            needs_mcp=False,
            needs_mitre=False,
            spl_allowed=False,
            mcp_allowed=False,
            policy_context_required=False,
            policy_context_recommended=True,
            rag_no_match_behavior="general_guidance_allowed",
            reasons=["knowledge_context_recommended"],
        )

    if family == "spl_generation_only":
        return EvidencePlan(
            answer_mode="live_investigation",
            rag_phase="post_mcp",
            needs_rag=False,
            needs_spl=True,
            needs_mcp=False,
            needs_mitre=False,
            spl_allowed=True,
            mcp_allowed=False,
            policy_context_required=False,
            policy_context_recommended=False,
            reasons=["spl_artifact_requested"],
        )

    if family == "hybrid_investigation_plus_policy":
        return EvidencePlan(
            answer_mode="hybrid",
            rag_phase="pre_mcp",
            needs_rag=True,
            needs_spl=True,
            needs_mcp=True,
            needs_mitre="mitre_mapping" in intent.answer_goal,
            spl_allowed=True,
            mcp_allowed=True,
            policy_context_required=False,
            policy_context_recommended=True,
            requires_hil=intent.requires_hil,
            action_mode=intent.action_mode or "recommend_only",
            reasons=["hybrid_live_results_with_guidance"],
        )

    if family == "mitre_mapping":
        return EvidencePlan(
            answer_mode="live_investigation",
            rag_phase="post_mcp",
            needs_rag=False,
            needs_spl=False,
            needs_mcp=False,
            needs_mitre=True,
            spl_allowed=False,
            mcp_allowed=False,
            policy_context_required=False,
            policy_context_recommended=False,
            requires_hil=intent.requires_hil,
            action_mode=intent.action_mode or "recommend_only",
            reasons=["mitre_mapping_requires_grounding"],
        )

    if family == "mitre_explanation":
        return EvidencePlan(
            answer_mode="rag_only",
            rag_phase="rag_only",
            needs_rag=True,
            needs_spl=False,
            needs_mcp=False,
            needs_mitre=True,
            spl_allowed=False,
            mcp_allowed=False,
            policy_context_required=False,
            policy_context_recommended=True,
            rag_no_match_behavior="general_guidance_allowed",
            reasons=["mitre_explanation_knowledge"],
        )

    return EvidencePlan(
        answer_mode="live_investigation",
        rag_phase="post_mcp",
        needs_rag=False,
        needs_spl=True,
        needs_mcp=True,
        needs_mitre=False,
        spl_allowed=True,
        mcp_allowed=True,
        policy_context_required=False,
        policy_context_recommended=False,
        requires_hil=intent.requires_hil,
        action_mode=intent.action_mode or "recommend_only",
        reasons=["live_investigation"],
    )
