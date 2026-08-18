"""Experience Center envelope — /demo only. Not a production /chat schema."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ProvenanceKind = Literal[
    "experience_center_fixture",
    "ec_scenario_policy",
    "production_validator_read_only",
    "simulated_mcp",
    "simulated_rag",
    "simulated_llm",
    "simulated_phase10_action",
    "ec_fixture_selected",
    "ec_allowlisted_email",
]

SemanticType = Literal[
    "understand",
    "plan",
    "gather",
    "correlate",
    "evaluate",
    "outcome",
    "next",
    "wait",
    "hil",
    "execute",
    "verify",
]


class EcProvenanceStamp(BaseModel):
    kind: ProvenanceKind
    detail: str | None = None


class EcProjectionView(BaseModel):
    title: str
    summary: str
    items: list[str] = Field(default_factory=list)
    provenance: EcProvenanceStamp


class EcProjection(BaseModel):
    """Architecture-shaped views for Layer 2. Not production InvestigationOutcome."""

    understanding: EcProjectionView
    resource_plan: EcProjectionView
    phase_contract: EcProjectionView
    evidence_state: EcProjectionView
    investigation_outcome: EcProjectionView
    provenance: EcProvenanceStamp


class EcFollowUpChip(BaseModel):
    follow_up_id: str
    label: str
    advances_state: bool = True
    group: Literal["continue", "action"] = "continue"
    leads_to_action: bool = False


class EcSessionState(BaseModel):
    session_id: str | None = None
    family: str
    scenario_id: str
    turn: int = 0
    pending_action_id: str | None = None
    awaiting_external: bool = False
    applied_follow_up_ids: list[str] = Field(default_factory=list)


class EcActionRecord(BaseModel):
    action_id: str
    kind: str
    label: str
    state: str
    provenance: Literal["simulated_phase10_action", "ec_allowlisted_email"] = "simulated_phase10_action"
    production_side_effect: bool = False
    receipt: dict[str, Any] | None = None
    verify_result: dict[str, Any] | None = None
    draft: dict[str, Any] | None = None


class EcExecutionResource(BaseModel):
    system: str
    operation: str
    mode: Literal["read", "write", "knowledge"] = "read"


class EcExecutionStage(BaseModel):
    id: str
    title: str
    description: str = ""
    activity: list[str] = Field(default_factory=list)
    semantic_type: SemanticType = "gather"
    resource: EcExecutionResource | None = None
    duration_ms_hint: int | None = None
    evidence_added: list[str] = Field(default_factory=list)
    outcome_change: str | None = None
    action_state: str | None = None
    provenance: ProvenanceKind = "experience_center_fixture"


class EcExecutionJourney(BaseModel):
    """Presentation projection for staged EC playback. Not an orchestrator."""

    journey_id: str
    kind: Literal["initial", "follow_up", "action"] = "initial"
    header: str = "Running governed investigation pipeline"
    follow_up_id: str | None = None
    action_id: str | None = None
    stages: list[EcExecutionStage] = Field(default_factory=list)


class EcSiemCoverageRow(BaseModel):
    investigation_need: str
    siem_status: str
    decision: str


class EcSiemExistingContent(BaseModel):
    object_type: str
    name: str
    status: str
    purpose: str
    coverage: Literal["FULL", "PARTIAL", "NONE", "UNKNOWN"]
    reused: bool = False
    execution_ref: str | None = None


class EcSiemGeneratedSearch(BaseModel):
    evidence_requirement: str
    candidate_created: bool = False
    validator_status: str = "UNKNOWN"
    normalized: bool = False
    execution_authorized: bool = False
    source_evidence_ids: list[str] = Field(default_factory=list)


class EcSiemCoverageAssessment(BaseModel):
    """EC-only projection of SIEM reuse vs gap-driven search. Not production authority."""

    siem: str = "Splunk"
    coverage_status: Literal["FULL", "PARTIAL", "NONE", "UNKNOWN"] = "UNKNOWN"
    existing_content: list[EcSiemExistingContent] = Field(default_factory=list)
    required_evidence: list[dict[str, Any]] = Field(default_factory=list)
    generated_searches: list[EcSiemGeneratedSearch] = Field(default_factory=list)
    remaining_gaps: list[str] = Field(default_factory=list)
    coverage_rows: list[EcSiemCoverageRow] = Field(default_factory=list)


class EcSiemToolTrace(BaseModel):
    purpose: str
    capability: str
    mcp_tool: str
    mode: Literal["READ", "WRITE"] = "READ"
    detail: str | None = None
    candidate_spl: str | None = None
    normalized_spl: str | None = None
    validator_status: str | None = None
    exact_call_authorization: str | None = None
    provenance: ProvenanceKind = "simulated_mcp"


class EcAttackChainStep(BaseModel):
    label: str
    status: str
    detail: str | None = None


class EcEvidenceFindingRow(BaseModel):
    investigation_point: str
    finding: str
    evidence_basis: str


class EcDetectionOpportunity(BaseModel):
    status: Literal["PREPARED", "RECOMMENDED", "DEPLOYED"] = "PREPARED"
    title: str
    summary: str
    recommended_action: str
    deploy_status: str = "not_deployed"
    notes: str | None = None


class EcTelemetrySourceRow(BaseModel):
    source: str
    status: str
    detail: str | None = None


class EcInvestigationScope(BaseModel):
    time_range: str
    telemetry_queried: list[str] = Field(default_factory=list)
    telemetry_sources: list[EcTelemetrySourceRow] = Field(default_factory=list)
    scope_note: str | None = None


class EcInvestigationPivot(BaseModel):
    title: str
    subject: str | None = None
    summary: str


class EcActionReadinessRow(BaseModel):
    action: str
    state: str


class EcEvidenceReuseRow(BaseModel):
    evidence_id: str
    label: str
    origin: str
    status: str
    detail: str | None = None


class ExperienceCenterResponse(BaseModel):
    """EC-owned /demo envelope. Extra keys may pass through for the frozen picker client."""

    model_config = ConfigDict(extra="allow")

    scenario_id: str
    trace_id: str
    message: str
    note: str | None = None
    demo_mode: bool = True
    analyst_summary: str | None = None
    analyst: dict[str, Any] | None = None
    analyst_response: dict[str, Any] | None = None
    selected_skill: str | None = None
    route_source: str = "ec_fixture_selected"
    candidate_spl: dict[str, Any] | None = None
    spl_validation: dict[str, Any] | None = None
    execution: dict[str, Any] | None = None
    human_review: dict[str, Any] | None = None
    source_evidence: list[Any] = Field(default_factory=list)
    ec_stage_latencies: list[Any] | None = None
    ec_projection: EcProjection
    ec_actions: list[EcActionRecord] = Field(default_factory=list)
    ec_followups: list[EcFollowUpChip] = Field(default_factory=list)
    ec_session_state: EcSessionState
    ec_provenance: dict[str, Any]
    ec_execution_journey: EcExecutionJourney | None = None
    ec_siem_coverage: EcSiemCoverageAssessment | None = None
    ec_siem_tool_traces: list[EcSiemToolTrace] = Field(default_factory=list)
    ec_attack_chain: list[EcAttackChainStep] = Field(default_factory=list)
    ec_evidence_findings: list[EcEvidenceFindingRow] = Field(default_factory=list)
    ec_detection_opportunity: EcDetectionOpportunity | None = None
    ec_investigation_scope: EcInvestigationScope | None = None
    ec_investigation_pivot: EcInvestigationPivot | None = None
    ec_action_readiness: list[EcActionReadinessRow] = Field(default_factory=list)
    ec_recommended_investigations: list[str] = Field(default_factory=list)
    ec_evidence_reuse: list[EcEvidenceReuseRow] = Field(default_factory=list)
