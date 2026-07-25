"""Gap-resolution planner output — not an executable ResourcePlan."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.chat.contracts.canonical_planning_input import ResolutionStatus

FieldSource = Literal[
    "user",
    "catalogue_default",
    "knowledge_recall",
    "live_telemetry",
    "model_inference",
    "detail_tool",
]


class FieldProvenance(BaseModel):
    value: Any
    source: FieldSource
    confidence: float = 1.0
    timestamp: str | None = None
    tool_call_id: str | None = None


class FieldConflict(BaseModel):
    field: str
    existing_value: Any
    new_value: Any
    existing_source: str
    new_source: str
    resolution_status: Literal["unresolved", "kept_existing", "accepted_new", "clarification_required"] = (
        "unresolved"
    )


class GapResolutionResult(BaseModel):
    resolution_id: str
    handoff_id: str
    original_skill: str | None = None
    original_answer_goal: str | None = None
    known_details: dict[str, FieldProvenance] = Field(default_factory=dict)
    requested_missing_details: list[str] = Field(default_factory=list)
    selected_tools: list[str] = Field(default_factory=list)
    tool_results: dict[str, Any] = Field(default_factory=dict)
    tool_statuses: dict[str, str] = Field(default_factory=dict)
    resolved_details: dict[str, FieldProvenance] = Field(default_factory=dict)
    unresolved_details: list[str] = Field(default_factory=list)
    conflicts: list[FieldConflict] = Field(default_factory=list)
    field_sources: dict[str, str] = Field(default_factory=dict)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    resolution_status: ResolutionStatus = "not_attempted"
    clarification_required: bool = False
    limitations: list[str] = Field(default_factory=list)
    retry_count: int = 0
    tool_call_ids: list[str] = Field(default_factory=list)
