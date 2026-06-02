from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


AnswerMode = Literal["rag_only", "live_investigation", "hybrid", "clarification"]
RagPhase = Literal["rag_only", "pre_mcp", "post_mcp"]
ActionMode = Literal["recommend_only", "execute_action_not_allowed", "hil_required"]
RagNoMatchBehavior = Literal["insufficient_policy_context", "general_guidance_allowed"]


class EvidencePlan(BaseModel):
    answer_mode: AnswerMode
    rag_phase: RagPhase
    needs_rag: bool
    needs_spl: bool
    needs_mcp: bool
    needs_mitre: bool
    spl_allowed: bool
    mcp_allowed: bool
    policy_context_required: bool
    policy_context_recommended: bool
    requires_hil: bool = False
    action_mode: ActionMode = "recommend_only"
    rag_no_match_behavior: RagNoMatchBehavior | None = None
    reasons: list[str] = Field(default_factory=list)
