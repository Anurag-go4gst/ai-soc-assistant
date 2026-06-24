from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.chat.contracts.llm_intent_advisory import LLMIntentAdvisory


IntentFamily = Literal[
    "policy_knowledge",
    "live_investigation",
    "spl_generation_only",
    "spl_generation_and_run",
    "hybrid_investigation_plus_policy",
    "hybrid_alert_review",
    "mitre_mapping",
    "mitre_explanation",
    "knowledge_only",
    "clarification_required",
    "sop_or_playbook",
    "guided_investigation",
    "alert_summary",
]
QueryType = Literal[
    "ask_for_policy",
    "ask_for_live_results",
    "ask_for_query_generation_and_execution",
    "ask_for_query_generation",
    "ask_for_mapping",
    "ask_for_explanation",
    "ask_for_next_action",
    "investigation_with_guidance",
    "sop_or_playbook",
]
AnswerGoal = Literal[
    "live_results",
    "analyst_action_guidance",
    "policy_citation",
    "spl_artifact",
    "mitre_mapping",
    "mitre_explanation",
    "severity_assessment",
    "procedural_steps",
    "clarification",
]
ConfidenceBand = Literal["high", "medium", "low"]
LlmIntentAssistStatus = Literal["skipped", "attempted", "accepted", "rejected", "corrected", "promoted"]
ActionMode = Literal["recommend_only", "execute_action_not_allowed", "hil_required"]


class IntentClassification(BaseModel):
    intent_family: IntentFamily
    primary_intent: str
    secondary_intents: list[str] = Field(default_factory=list)
    query_type: QueryType
    answer_goal: list[AnswerGoal]
    requested_output_type: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_band: ConfidenceBand
    requires_clarification: bool
    requires_hil: bool = False
    action_mode: ActionMode | None = None
    reason: str


class QueryToIntentResult(BaseModel):
    query_signals: dict[str, Any]
    candidate_mappings: dict[str, Any]
    intent_classification: IntentClassification
    intent_conflicts: list[dict[str, Any]] = Field(default_factory=list)
    llm_intent_assist_status: LlmIntentAssistStatus = "skipped"
    llm_intent_advisory: LLMIntentAdvisory | None = None
