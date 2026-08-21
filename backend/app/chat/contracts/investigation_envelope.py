"""Canonical P4 investigation approval and immutable envelope contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


InvestigationReviewAction = Literal["run", "edit", "cancel"]
InvestigationApprovalStatus = Literal[
    "awaiting_approval",
    "edited_revalidated",
    "approved",
    "cancelled",
    "replanning_required",
]


class InvestigationEnvelopeBudget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    hop_limit: int = Field(default=4, ge=1, le=20)
    timeout_seconds: int = Field(default=300, ge=1, le=900)
    cost_resource_limits: dict[str, int | float | str] = Field(
        default_factory=lambda: {"max_tool_calls": 4, "max_parallel_calls": 1}
    )


class InvestigationPlanDeltaPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    automatic_bounded_read_only_delta_allowed: bool = True
    material_scope_expansion_requires_hil: bool = True


class ApprovedInvestigationEnvelope(BaseModel):
    """The single immutable §13.1 read-only investigation envelope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    envelope_version: int = Field(ge=1)
    objective: str = Field(min_length=1, max_length=500)
    targets: list[str] = Field(default_factory=list, max_length=64)
    entities: dict[str, Any] = Field(default_factory=dict)
    time_scope: str | None = Field(default=None, max_length=240)
    approved_evidence_categories: list[str] = Field(default_factory=list, max_length=32)
    allowed_read_only_capabilities: list[str] = Field(default_factory=list, max_length=64)
    source_index_scope: dict[str, list[str]] = Field(default_factory=dict)
    budget: InvestigationEnvelopeBudget = Field(default_factory=InvestigationEnvelopeBudget)
    plan_delta_policy: InvestigationPlanDeltaPolicy = Field(default_factory=InvestigationPlanDeltaPolicy)
    prohibited_actions: list[str] = Field(
        default_factory=lambda: [
            "all_writes",
            "remediation",
            "email_send",
            "firewall_block",
            "account_disable",
            "endpoint_isolation",
            "quarantine",
        ]
    )

    @field_validator("allowed_read_only_capabilities")
    @classmethod
    def _read_only_capabilities_only(cls, values: list[str]) -> list[str]:
        forbidden = ("write", "send", "block", "disable", "isolate", "quarantine", "delete")
        normalized: list[str] = []
        for raw in values:
            value = str(raw or "").strip()
            if not value:
                continue
            lowered = value.lower()
            if lowered.startswith("action:") or any(token in lowered for token in forbidden):
                raise ValueError("investigation envelope capabilities must be read-only")
            if value not in normalized:
                normalized.append(value)
        return normalized

    @model_validator(mode="after")
    def _writes_are_always_prohibited(self) -> "ApprovedInvestigationEnvelope":
        required = {"all_writes", "remediation"}
        if not required.issubset(set(self.prohibited_actions)):
            raise ValueError("all writes and remediation must remain prohibited")
        if not self.plan_delta_policy.material_scope_expansion_requires_hil:
            raise ValueError("material scope expansion must require HIL")
        return self


class InvestigationPlanEdits(BaseModel):
    """Structured analyst edits; material scope changes route back to resolution."""

    model_config = ConfigDict(extra="forbid")

    investigation_objective: str | None = Field(default=None, max_length=500)
    entities: dict[str, Any] | None = None
    time_scope: str | None = Field(default=None, max_length=240)
    evidence_needed: list[str] | None = Field(default=None, max_length=32)
    data_categories: list[str] | None = Field(default=None, max_length=32)
    capability_requests: list[str] | None = Field(default=None, max_length=64)


class InvestigationPlanSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    what_will_be_checked: list[str] = Field(default_factory=list)
    why_it_matters: str
    scope_and_time: list[str] = Field(default_factory=list)
    resources_and_capabilities: list[str] = Field(default_factory=list)


class InvestigationApprovalState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: InvestigationApprovalStatus
    handoff_id: str
    handoff_version: int = Field(ge=1)
    allowed_actions: list[InvestigationReviewAction] = Field(default_factory=list)
    plan_summary: InvestigationPlanSummary
    validated_plan: dict[str, Any]
    approved_envelope: ApprovedInvestigationEnvelope | None = None
    safe_message: str
    revalidation_warnings: list[str] = Field(default_factory=list)

