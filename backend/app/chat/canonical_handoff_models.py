"""Canonical handoff record contract."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

HandoffStatus = Literal[
    "created",
    "awaiting_clarification",
    "awaiting_investigation_plan",
    "investigation_approved",
    "investigation_cancelled",
    "resumed",
    "planning",
    "plan_committed",
    "executing",
    "completed",
    "failed",
    "expired",
    "in_progress",
    "clarification_required",
    "committed",
    "planning_failed",
    "resolution_failed",
    "policy_blocked",
]


class CanonicalHandoffRecord(BaseModel):
    handoff_id: str
    handoff_version: int = 1
    status: HandoffStatus = "created"
    trace_id: str | None = None
    session_id: str | None = None
    turn_id: str | None = None
    original_query: str | None = None
    original_skill: str | None = None
    original_use_case_id: str | None = None
    original_answer_goal: str | None = None
    initial_tier: str | None = None
    resolved_tier: str | None = None
    canonical_planning_input: dict[str, Any] | None = None
    gap_resolution: dict[str, Any] | None = None
    unresolved_fields: list[str] = Field(default_factory=list)
    clarification_reason: str | None = None
    committed_resource_plan_id: str | None = None
    committed_resource_plan: dict[str, Any] | None = None
    committed_evidence_plan: dict[str, Any] | None = None
    duplicate_call_hashes: list[str] = Field(default_factory=list)
    retry_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def storage_key(self) -> str:
        return f"{self.handoff_id}:v{self.handoff_version}"

    def is_expired(self, *, now: datetime | None = None) -> bool:
        return (now or datetime.now(UTC)) >= self.expires_at

    def normalized_status(self) -> str:
        mapping = {
            "in_progress": "planning",
            "clarification_required": "awaiting_clarification",
            "awaiting_investigation_plan": "awaiting_investigation_plan",
            "committed": "plan_committed",
            "planning_failed": "failed",
            "resolution_failed": "failed",
            "policy_blocked": "failed",
        }
        return mapping.get(self.status, self.status)
