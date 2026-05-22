from typing import Any

from pydantic import BaseModel, Field


class InvestigationState(BaseModel):
    trace_id: str
    alert_id: str | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    route: str | None = None
