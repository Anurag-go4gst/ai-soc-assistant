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
