from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    requested_mcp_server: str | None = None
    requested_mcp_tool: str | None = None


class InvestigationRequest(BaseModel):
    alert_id: str
    summary: str | None = None
