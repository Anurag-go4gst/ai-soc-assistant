from pydantic import BaseModel


class WorkflowStep(BaseModel):
    order: int
    name: str
    status: str
    required_connectors: list[str]
    safety_gates: list[str]


class WorkflowPlan(BaseModel):
    trace_id: str
    skill: str
    tool_plan: list[str]
    status: str
    execution_enabled: bool
    steps: list[WorkflowStep]
    required_connectors: list[str]
    safety_gates: list[str]
    required_sources: list[str] = []
    available_sources: list[str] = []
    missing_sources: list[str] = []
    message: str


class CandidateSplEnvelope(BaseModel):
    trace_id: str
    skill: str
    user_query: str
    candidate_spl: str
    generation_mode: str
    confidence: float
    assumptions: list[str]
    warnings: list[str]


class SplValidationEnvelope(BaseModel):
    approved: bool
    normalized_spl: str | None = None
    reject_reasons: list[str]
    warnings: list[str]
    enforced_limits: dict[str, object]
    policy_version: str


class ExecutionEnvelope(BaseModel):
    status: str
    execution_intent: str
    selected_mcp_server: str | None = None
    selected_mcp_tool: str | None = None
    tool_selection_status: str
    tool_selection_reason: str
    executed_spl: str | None = None
    result_count: int
    results_preview: list[dict[str, object]]
    block_reason: str | None = None
    duration_ms: int


class HumanReviewEnvelope(BaseModel):
    required: bool
    review_type: str
    reason: str
    reviewer_role: str
    allowed_actions: list[str]
    safe_message_for_user: str
    sop_reference: str | None = None
    sop_excerpt: str | None = None
    sop_action_hint: str | None = None


class SourceEvidenceEnvelope(BaseModel):
    evidence_id: str
    trace_id: str
    source_type: str
    source_name: str
    tool_name: str | None = None
    collection_status: str
    query_or_request_summary: str | None = None
    executed_spl: str | None = None
    result_count: int
    fields_returned: list[str]
    preview_rows: list[dict[str, object]]
    raw_result_hash: str | None = None
    raw_result_stored: bool
    time_range: str | None = None
    warnings: list[str]
    sensitivity_flags: list[str]
    created_at: str


class StructuredFact(BaseModel):
    fact_id: str
    statement: str
    source_refs: list[str]
    derivation: str
    confidence: float | None = None


class StructuredContextPackage(BaseModel):
    trace_id: str
    query: str
    selected_skill: str
    source_evidence_refs: list[str]
    structured_facts: list[StructuredFact]
    entity_summary: dict[str, object]
    metrics: dict[str, object]
    timeline_candidates: list[dict[str, object]]
    mitre_candidates: list[dict[str, object]]
    tool_outputs_summary: list[dict[str, object]]
    policy_context_refs: list[str]
    assumptions: list[str]
    warnings: list[str]
    missing_evidence: list[str]
    allowed_conclusions: list[str]
    prohibited_conclusions: list[str]
    context_quality: str
    synthesis_allowed: bool = False


class ContextSufficiencyEnvelope(BaseModel):
    status: str
    synthesis_allowed: bool
    reasons: list[str]
    missing_evidence: list[str]
    human_review: HumanReviewEnvelope | None = None


class PlaceholderResponse(BaseModel):
    trace_id: str
    message: str
    note: str
    user_query: str | None = None
    selected_skill: str | None = None
    tool_plan: list[str] | None = None
    confidence: float | None = None
    routing_mode: str | None = None
    disagreement: bool | None = None
    disagreement_reason: str | None = None
    workflow_plan: WorkflowPlan | None = None
    candidate_spl: CandidateSplEnvelope | None = None
    spl_validation: SplValidationEnvelope | None = None
    execution: ExecutionEnvelope | None = None
    human_review: HumanReviewEnvelope | None = None
    source_evidence: list[SourceEvidenceEnvelope] = []
    structured_context: StructuredContextPackage | None = None
    context_sufficiency: ContextSufficiencyEnvelope | None = None
