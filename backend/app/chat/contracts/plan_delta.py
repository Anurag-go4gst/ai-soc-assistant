"""Append-only, read-only investigation PlanDelta contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PlanDeltaProposal(BaseModel):
    """Advisory reasoning output. It never carries execution authority."""

    model_config = ConfigDict(extra="forbid")

    envelope_version: int = Field(ge=1)
    prior_revision_fingerprint: str | None = None
    objective: str = Field(min_length=1, max_length=500)
    evidence_need: str = Field(min_length=1, max_length=240)
    capability_id: str = Field(min_length=1, max_length=240)
    access_mode: Literal["read_only", "write"] = "read_only"
    targets: list[str] = Field(default_factory=list, max_length=64)
    entities: dict[str, Any] = Field(default_factory=dict)
    time_scope: str | None = Field(default=None, max_length=240)
    source_index_scope: dict[str, list[str]] = Field(default_factory=dict)
    tool_arguments: dict[str, Any] = Field(default_factory=dict)
    hypothesis: str | None = Field(default=None, max_length=500)
    evidence_refs: list[str] = Field(default_factory=list, max_length=32)


class ValidatedPlanDelta(PlanDeltaProposal):
    """DET-accepted append-only revision, still subject to AUTH0/RBAC/HIL."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["validated_plan_delta_v1"] = "validated_plan_delta_v1"
    revision_number: int = Field(ge=1)
    revision_fingerprint: str = Field(min_length=64, max_length=64)
    effective_fingerprint: str = Field(min_length=64, max_length=64)
    exact_call_authorization_required: Literal[True] = True
    execution_authorized: Literal[False] = False


PlanDeltaDecisionStatus = Literal[
    "accepted",
    "rejected",
    "hil_required",
    "remediation_recommended",
    "no_progress",
    "budget_exhausted",
    "reasoner_unavailable",
    "disabled",
]


class PlanDeltaDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PlanDeltaDecisionStatus
    reason: str
    validated_delta: ValidatedPlanDelta | None = None
    remediation_recommendation: str | None = None

