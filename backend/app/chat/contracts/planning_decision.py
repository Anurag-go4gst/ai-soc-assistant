from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


PathType = Literal[
    "rag_only",
    "spl_review",
    "spl_review_plus_rag",
    "hybrid_investigation",
    "mitre_context_required",
    "generic_soc_guidance",
    "unsafe_blocked",
    "clarification_required",
    "legacy_or_unsupported",
]

BranchName = Literal[
    "rag",
    "spl",
    "evidence",
    "mitre",
    "severity",
    "hil",
    "clarification",
    "block",
    "unsafe_blocked",
]


class BranchSet(BaseModel):
    branches: list[BranchName] = Field(default_factory=list)


class PlanningDecision(BaseModel):
    path_type: PathType
    branches: list[BranchName] = Field(default_factory=list)
    use_case_id: str | None = None
    question_ref: str | None = None
    runtime_support_status: str | None = None
    crosswalk_lookup_status: str = "not_available"
    live_execution_skill: str | None = None
    planning_or_analytic_skill: str | None = None
    selected_tools: list[str] = Field(default_factory=list)
    blocked_tools: list[str] = Field(default_factory=list)
    clarification_needed: bool = False
    hil_required: bool = False
    reason: str
    authority_source: str = "deterministic_trace_only"
    precedence_applied: list[str] = Field(default_factory=list)
    execution_enabled: bool = False
    planner_path_selection_enabled: bool = False
    planner_runtime_activation_allowed: bool = False

