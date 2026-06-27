from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


AnswerMode = Literal["rag_only", "live_investigation", "hybrid", "clarification", "guided_investigation"]
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
    required_evidence_keys: list[str] = Field(default_factory=list)
    optional_evidence_keys: list[str] = Field(default_factory=list)
    present_evidence_keys: list[str] = Field(default_factory=list)
    missing_required_evidence: list[str] = Field(default_factory=list)
    enrichment_driven: bool = False
    checklist: list[str] = Field(default_factory=list)
    investigation_workflow: list[str] = Field(default_factory=list)
    answer_rules: list[str] = Field(default_factory=list)
    required_sources: list[str] = Field(default_factory=list)
    optional_sources: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    recommended_pivots: list[str] = Field(default_factory=list)
    unsupported_claims_avoid: list[str] = Field(default_factory=list)
    needs_hil: bool = False
    needs_clarification: bool = False
    evidence_plan_reason: str | None = None
    use_case_id: str | None = None
    runtime_support_status: str | None = None
    mitre_candidates_metadata_only: list[str] = Field(default_factory=list)
    row_authority_summary: dict | None = None
    normalized_slot_summary: dict | None = None
    source_profile_binding_summary: dict | None = None
    answer_pack_summary: dict | None = None
    promotion_lifecycle_summary: dict | None = None
    # WS0 T0.2: composed step plan (None until the composer attaches one);
    # legacy booleans above remain the wire contract for existing consumers.
    resource_plan: dict | None = None
    evidence_legs: list[dict] = Field(default_factory=list)
    correlation: dict | None = None
