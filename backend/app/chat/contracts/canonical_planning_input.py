"""Canonical planner boundary contract — sole input to the final evidence planner."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = "canonical_planning_input_v1"
CONTRACT_VERSION = "2026-07-25"

CatalogueTier = Literal["T0", "T1", "T2", "T3", "T4"]
ProcessingLane = Literal["known", "guided", "knowledge_short_circuit", "clarification"]
IntentSource = Literal["stub", "classifier", "short_circuit", "diversion"]
ResolutionStatus = Literal[
    "not_attempted",
    "complete",
    "complete_with_limitations",
    "clarification_required",
    "policy_blocked",
    "resolution_failed",
    "resolved_without_tools",
    "unsupported",
]


class TraceContext(BaseModel):
    trace_id: str | None = None
    turn_id: str | None = None
    handoff_id: str
    handoff_version: int = 1
    parent_decision_id: str | None = None


class MessageContext(BaseModel):
    content_reference: str
    normalized_query: str
    conversation_context_reference: str | None = None


class RoutingContext(BaseModel):
    initial_tier: CatalogueTier
    resolved_tier: CatalogueTier
    match_path: str
    observed_match_path: str | None = None
    effective_match_path: str | None = None
    catalogue_tier: CatalogueTier
    processing_lane: ProcessingLane
    route_reason: str
    use_case_id: str | None = None
    primary_skill: str
    original_skill: str | None = None
    intent_family: str
    intent_source: IntentSource
    answer_goal: str


class QueryUnderstandingSnapshot(BaseModel):
    entities: dict[str, Any] = Field(default_factory=dict)
    signals: dict[str, Any] = Field(default_factory=dict)
    time_window: str | None = None
    reference_ids: list[str] = Field(default_factory=list)
    candidate_use_cases: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class DetailState(BaseModel):
    planner_required_fields: list[str] = Field(default_factory=list)
    tool_discoverable_fields: list[str] = Field(default_factory=list)
    user_only_fields: list[str] = Field(default_factory=list)
    optional_fields: list[str] = Field(default_factory=list)
    present_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    field_values: dict[str, Any] = Field(default_factory=dict)
    field_sources: dict[str, str] = Field(default_factory=dict)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)


class GuidedResolutionSnapshot(BaseModel):
    attempted: bool = False
    resolution_id: str | None = None
    selected_tools: list[str] = Field(default_factory=list)
    tool_statuses: dict[str, str] = Field(default_factory=dict)
    resolved_fields: list[str] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)
    resolution_status: ResolutionStatus = "not_attempted"
    retry_count: int = 0
    clarification_required: bool = False


class PlanningGoal(BaseModel):
    requested_outcomes: list[str] = Field(default_factory=list)
    evidence_requirements: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class GovernanceContext(BaseModel):
    safe: bool = True
    rag_allowed: bool = False
    spl_generation_allowed: bool = False
    spl_execution_allowed: bool = False
    mcp_allowed: bool = False
    action_allowed: bool = False
    remediation_allowed: bool = False
    approval_required: bool = False


class ProvenanceContext(BaseModel):
    prompt_template_id: str | None = None
    prompt_template_version: str | None = None
    rendered_prompt_hash: str | None = None
    model_id: str | None = None
    policy_version: str | None = None
    source_versions: dict[str, str] = Field(default_factory=dict)


class CanonicalPlanningInput(BaseModel):
    schema_version: str = SCHEMA_VERSION
    contract_version: str = CONTRACT_VERSION
    trace: TraceContext
    message: MessageContext
    routing: RoutingContext
    query_understanding: QueryUnderstandingSnapshot
    detail_state: DetailState
    guided_resolution: GuidedResolutionSnapshot
    planning_goal: PlanningGoal
    governance: GovernanceContext
    provenance: ProvenanceContext = Field(default_factory=ProvenanceContext)
