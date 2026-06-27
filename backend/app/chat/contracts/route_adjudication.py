from __future__ import annotations

from pydantic import BaseModel


class RouteAdjudication(BaseModel):
    deterministic_route: str | None = None
    llm_suggested_route: str | None = None
    shadow_plan_status: str | None = None
    final_route: str
    final_use_case_id: str | None = None
    authority_source: str
    reason: str
    row_authority_status: str | None = None
    row_authority_decision: str | None = None
    row_authority_applied: bool = False
    row_authority_note: str | None = None
    row_authority_fallback_reason: str | None = None
