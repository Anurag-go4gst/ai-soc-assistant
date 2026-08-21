"""Governed remediation planning contracts (architecture P10).

Remediation is the first lifecycle stage that may propose **writes**, so the
contracts here are deliberately narrower than the investigation ones:

* the reasoning model may emit only :class:`RemediationPlanProposal`, which carries
  no capability authorization and no execution flag;
* :class:`ValidatedRemediationPlan` is the deterministic authority — every step is
  bound to a ``CapabilitySnapshot`` row, and ``execution_authorized`` is pinned
  false on the contract itself;
* :class:`ApprovedRemediationEnvelope` is the immutable record of what the analyst
  actually approved. Connector execution (P11) binds to its version; nothing else
  may widen it.

An unavailable capability is represented honestly as a ``manual_or_alternate``
step. It is never dropped, and never reported as if it had run.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "validated_remediation_plan_v1"
ENVELOPE_SCHEMA_VERSION = "approved_remediation_envelope_v1"

RemediationPlanSource = Literal[
    "deterministic_only",
    "llm_proposed_validated",
    "llm_failed_baseline_only",
]

#: ``execute`` requires an available, registered write capability. Everything else
#: is an honest instruction for a human, not a silent no-op.
RemediationExecutionMode = Literal["execute", "manual_or_alternate"]

RemediationApprovalStatus = Literal[
    "offered",
    "awaiting_approval",
    "edited_revalidated",
    "approved",
    "cancelled",
    "declined",
]


class RemediationStep(BaseModel):
    """One deterministic remediation step bound to a CapabilitySnapshot row."""

    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(min_length=1, max_length=120)
    capability_id: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    execution_mode: RemediationExecutionMode
    availability: Literal["available", "unavailable"]
    reversible: bool = False
    verification: str = Field(min_length=1, max_length=300)
    unavailable_reason: str | None = Field(default=None, max_length=240)

    @field_validator("description", "verification")
    @classmethod
    def _single_line(cls, value: str) -> str:
        return " ".join(value.split())


class RemediationPlanProposal(BaseModel):
    """Advisory reasoning output. It cannot authorize a capability or a write."""

    model_config = ConfigDict(extra="forbid")

    remediation_objective: str | None = Field(default=None, max_length=500)
    proposed_steps: list[str] = Field(default_factory=list, max_length=16)
    capability_requests: list[str] = Field(default_factory=list, max_length=16)
    verification_suggestions: list[str] = Field(default_factory=list, max_length=16)
    rationale: str | None = Field(default=None, max_length=1000)


class ValidatedRemediationPlan(BaseModel):
    """DET-authoritative plan shown for approval. Never itself an authorization."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    remediation_objective: str = Field(min_length=1, max_length=500)
    steps: list[RemediationStep] = Field(default_factory=list, max_length=32)
    manual_only_steps: list[str] = Field(default_factory=list, max_length=32)
    plan_source: RemediationPlanSource = "deterministic_only"
    validation_warnings: list[str] = Field(default_factory=list, max_length=32)
    dropped_reasons: list[str] = Field(default_factory=list, max_length=32)
    derived_from_investigation_status: str | None = None
    derived_from_disposition: str | None = None
    human_approval_required: Literal[True] = True
    execution_authorized: Literal[False] = False


class RemediationPlanEdits(BaseModel):
    """Analyst edits. Steps may be removed or re-described, never invented."""

    model_config = ConfigDict(extra="forbid")

    remediation_objective: str | None = Field(default=None, max_length=500)
    removed_step_ids: list[str] = Field(default_factory=list, max_length=32)
    step_descriptions: dict[str, str] = Field(default_factory=dict)


class ApprovedRemediationEnvelope(BaseModel):
    """Immutable record of the approved plan; P11 execution binds to its version."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = ENVELOPE_SCHEMA_VERSION
    envelope_version: int = Field(ge=1)
    remediation_objective: str = Field(min_length=1, max_length=500)
    approved_steps: list[RemediationStep] = Field(default_factory=list, max_length=32)
    plan_fingerprint: str = Field(min_length=1, max_length=128)
    investigation_envelope_version: int | None = None

    def executable_capability_ids(self) -> list[str]:
        """Capabilities the analyst actually approved for execution."""
        return [
            step.capability_id
            for step in self.approved_steps
            if step.execution_mode == "execute" and step.availability == "available"
        ]


class RemediationPlanSummary(BaseModel):
    """Human-readable card shown before approval — not JSON dumped at the analyst."""

    model_config = ConfigDict(extra="forbid")

    what_will_change: list[str] = Field(default_factory=list, max_length=32)
    why_it_matters: str = Field(min_length=1, max_length=500)
    what_stays_manual: list[str] = Field(default_factory=list, max_length=32)
    how_it_is_verified: list[str] = Field(default_factory=list, max_length=32)


class RemediationApprovalState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: RemediationApprovalStatus
    handoff_id: str | None = None
    handoff_version: int | None = None
    allowed_actions: list[Literal["approve", "edit", "cancel", "create", "decline"]] = Field(
        default_factory=list
    )
    plan_summary: RemediationPlanSummary | None = None
    validated_plan: dict | None = None
    approved_envelope: ApprovedRemediationEnvelope | None = None
    safe_message: str = ""
    revalidation_warnings: list[str] = Field(default_factory=list, max_length=32)
