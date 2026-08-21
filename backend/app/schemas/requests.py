from typing import Any, Literal

from pydantic import BaseModel, model_validator


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    requested_mcp_server: str | None = None
    requested_mcp_tool: str | None = None
    llm_spl_draft_mode: bool = False
    # COE-provided index/sourcetype slot map for this turn (e.g. from Settings or HIL follow-up).
    source_profile_slots: dict[str, str] | None = None
    # Analyst execution handshake: confirm proposed SPL, provide updated SPL, or reject.
    execution_review_action: str | None = None
    analyst_provided_spl: str | None = None
    # Investigation-plan HIL. These bind the decision to one persisted plan version.
    investigation_review_action: Literal["run", "edit", "cancel"] | None = None
    investigation_handoff_id: str | None = None
    investigation_handoff_version: int | None = None
    investigation_plan_edits: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _investigation_review_is_version_bound(self) -> "ChatRequest":
        if self.investigation_review_action is None:
            return self
        if not self.investigation_handoff_id or not self.investigation_handoff_version:
            raise ValueError("investigation review requires handoff id and version")
        if self.investigation_review_action == "edit" and self.investigation_plan_edits is None:
            raise ValueError("investigation edit requires structured plan edits")
        return self


class InvestigationRequest(BaseModel):
    alert_id: str
    summary: str | None = None
