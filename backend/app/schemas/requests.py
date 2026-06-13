from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    requested_mcp_server: str | None = None
    requested_mcp_tool: str | None = None
    llm_spl_draft_mode: bool = False
    # COE-provided index/sourcetype slot map for this turn (e.g. from Settings or HIL follow-up).
    source_profile_slots: dict[str, str] | None = None


class InvestigationRequest(BaseModel):
    alert_id: str
    summary: str | None = None
