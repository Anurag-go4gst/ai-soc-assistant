from pydantic import BaseModel


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
