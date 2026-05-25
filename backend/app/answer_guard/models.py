from __future__ import annotations

from pydantic import BaseModel, Field


class AnswerGuardStatus(BaseModel):
    enabled: bool = False
    guard_status: str = "disabled"
    passed_checks: list[str] = Field(default_factory=list)
    failed_checks: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None
    analyst_review_required: bool = False
    reason: str = "Stage 3L Answer Guard is not enabled; v1 will block or route to review on failure."
