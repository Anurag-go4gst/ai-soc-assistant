"""InvestigationPlan contract for guided hybrid investigation (REV4)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PlanSource = Literal[
    "deterministic_only",
    "llm_proposed_validated",
    "llm_failed_baseline_only",
]


class InvestigationPlan(BaseModel):
    """What to investigate on guided_hybrid paths — does not invoke tools directly."""

    investigation_objective: str
    hypotheses: list[str] = Field(default_factory=list)
    evidence_needed: list[str] = Field(default_factory=list)
    data_categories: list[str] = Field(default_factory=list)
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
