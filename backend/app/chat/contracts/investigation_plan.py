"""Governed investigation planning contracts.

The reasoning model may emit only :class:`InvestigationPlanProposal`. The
deterministic validator produces :class:`ValidatedInvestigationPlan`; neither
contract carries execution authority or a ResourcePlan.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

PlanSource = Literal[
    "deterministic_only",
    "llm_proposed_validated",
    "llm_failed_baseline_only",
]

CapabilityNeed = Literal["required", "recommended", "optional"]
CapabilityAvailability = Literal["available", "unavailable"]
CapabilityAccessMode = Literal["read_only", "manual_or_alternate"]
CapabilityReadWrite = Literal["read_only", "execution_gated"]


class InvestigationCapabilityBinding(BaseModel):
    """A deterministic projection of one CapabilitySnapshot row.

    Optional planned-call fields carry enough information to derive the future
    AUTH0 exact-call grant without reconstructing arguments at trace time.
    """

    model_config = ConfigDict(extra="forbid")

    capability_id: str = Field(min_length=1)
    capability_need: CapabilityNeed
    availability: CapabilityAvailability
    access_mode: CapabilityAccessMode
    purpose: str | None = None
    argument_template: dict[str, Any] | None = None
    planned_arguments: dict[str, Any] | None = None
    unresolved_arguments: list[str] = Field(default_factory=list)
    read_write_classification: CapabilityReadWrite | None = None
    authorization_posture: str | None = None


class InvestigationPlanProposal(BaseModel):
    """Advisory reasoning output. It cannot authorize tools or execution."""

    model_config = ConfigDict(extra="forbid")

    investigation_objective: str | None = None
    hypotheses: list[str] = Field(default_factory=list)
    evidence_needed: list[str] = Field(default_factory=list)
    data_categories: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    capability_requests: list[str] = Field(default_factory=list)
    clarification_needed: bool = False
    clarification_questions: list[str] = Field(default_factory=list)


class InvestigationPlan(BaseModel):
    """What to investigate on guided_hybrid paths — does not invoke tools directly."""

    investigation_objective: str
    hypotheses: list[str] = Field(default_factory=list)
    evidence_needed: list[str] = Field(default_factory=list)
    data_categories: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    capability_bindings: list[InvestigationCapabilityBinding] = Field(default_factory=list)
    authoritative_facts: list[str] = Field(default_factory=list)
    rag_sufficient: bool = False
    env_kb_needed: bool = False
    discovery_needed: bool = False
    environment_constraints: list[str] = Field(default_factory=list)
    candidate_sources: list[str] = Field(default_factory=list)
    read_only_tool_requests: list[str] = Field(default_factory=list)
    safe_spl_template_requests: list[str] = Field(default_factory=list)
    spl_review_requested: bool = False
    spl_review_reason: str | None = None
    clarification_needed: bool = False
    clarification_questions: list[str] = Field(default_factory=list)
    refinement_recommended: bool = False
    refinement_rationale: str | None = None
    blocked_capabilities: list[str] = Field(default_factory=list)
    human_review_required: bool = True
    plan_source: PlanSource = "deterministic_only"
    validation_warnings: list[str] = Field(default_factory=list)
    llm_budget_used: int = 0
    refinement_round: int = 0


class ValidatedInvestigationPlan(InvestigationPlan):
    """DET-authoritative plan shown for approval before any ResourcePlan exists."""

    schema_version: str = "validated_investigation_plan_v1"
    validation_status: Literal["validated"] = "validated"
    planner_role: Literal["investigation_planner"] = "investigation_planner"
