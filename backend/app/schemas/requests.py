from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


class InvestigationRequest(BaseModel):
    alert_id: str
    summary: str | None = None
