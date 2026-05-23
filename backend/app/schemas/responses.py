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
