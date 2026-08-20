"""Typed outcome of canonical planning.

Downstream nodes branch on ``CanonicalPlanningOutcome.status`` — never on the presence
or shape of a partially constructed ``EvidencePlan``. Before this contract existed the
clarification path pushed a 5-key dict into ``state["evidence_plan"]``; every consumer
that reached ``EvidencePlan.model_validate`` then raised ``ValidationError`` with nine
missing required fields, which is what failed the sentinel and 12 clean-answer rows.

Invariants enforced here rather than by convention:

===========================  ==============  ==============  =========================
``status``                   ``EvidencePlan``  ``ResourcePlan``  also required
===========================  ==============  ==============  =========================
``planned``                  required        required        ``canonical_input``
``clarification_required``   absent          absent          ``clarification`` + handoff
``awaiting_investigation_plan`` absent       absent          ``canonical_input`` (P0+)
``policy_blocked``           optional        absent          ``policy_reason``
any failure status           absent          absent          ``failure``
===========================  ==============  ==============  =========================
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CanonicalPlanningStatus = Literal[
    "planned",
    "clarification_required",
    "awaiting_investigation_plan",
    "resolution_failed",
    "planning_failed",
    "policy_blocked",
    "unsupported",
    "execution_failed",
    "persistence_failed",
]

#: Statuses that represent a terminal, non-executable failure.
FAILURE_STATUSES: frozenset[str] = frozenset(
    {
        "resolution_failed",
        "planning_failed",
        "unsupported",
        "execution_failed",
        "persistence_failed",
    }
)

#: Statuses that must never carry a committed ResourcePlan.
NON_EXECUTING_STATUSES: frozenset[str] = FAILURE_STATUSES | {
    "clarification_required",
    "awaiting_investigation_plan",
    "policy_blocked",
}


class ClarificationRequest(BaseModel):
    """What the analyst is being asked, and what is still unresolved."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)
    unresolved_fields: list[str] = Field(min_length=1)
    handoff_id: str = Field(min_length=1)
    handoff_version: int = Field(ge=1)
    reason: str = ""


class PlanningFailure(BaseModel):
    """Typed failure detail — never rendered as a successful answer."""

    model_config = ConfigDict(extra="forbid")

    category: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    detail: str | None = None


class CanonicalPlanningOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: CanonicalPlanningStatus
    canonical_input: dict[str, Any] | None = None
    evidence_plan: dict[str, Any] | None = None
    resource_plan: dict[str, Any] | None = None
    clarification: ClarificationRequest | None = None
    failure: PlanningFailure | None = None
    policy_reason: str | None = None

    @property
    def is_planned(self) -> bool:
        return self.status == "planned"

    @property
    def is_executable(self) -> bool:
        """Only a committed plan from a ``planned`` outcome may reach execution."""
        return self.status == "planned" and self.resource_plan is not None

    @model_validator(mode="after")
    def _enforce_outcome_rules(self) -> CanonicalPlanningOutcome:
        if self.status == "planned":
            if self.evidence_plan is None:
                raise ValueError("planned outcome requires evidence_plan")
            if self.resource_plan is None:
                raise ValueError("planned outcome requires a committed resource_plan")
            if self.canonical_input is None:
                raise ValueError("planned outcome requires canonical_input")
            return self

        if self.resource_plan is not None:
            raise ValueError(f"{self.status} outcome must not carry a resource_plan")

        if self.status == "clarification_required":
            if self.clarification is None:
                raise ValueError("clarification_required outcome requires clarification")
            if self.evidence_plan is not None:
                # Reinstating this is what produced the sentinel ValidationError.
                raise ValueError("clarification_required outcome must not carry an evidence_plan")
            return self

        if self.status == "awaiting_investigation_plan":
            # P0 wait-state: Final RQC + owner bound; no EvidencePlan / ResourcePlan yet.
            if self.evidence_plan is not None:
                raise ValueError("awaiting_investigation_plan outcome must not carry an evidence_plan")
            if self.canonical_input is None:
                raise ValueError("awaiting_investigation_plan outcome requires canonical_input")
            return self

        if self.status == "policy_blocked":
            if not self.policy_reason:
                raise ValueError("policy_blocked outcome requires policy_reason")
            return self

        if self.failure is None:
            raise ValueError(f"{self.status} outcome requires typed failure")
        if self.evidence_plan is not None:
            raise ValueError(f"{self.status} outcome must not carry an evidence_plan")
        return self


def planned_outcome(
    *,
    canonical_input: dict[str, Any],
    evidence_plan: dict[str, Any],
    resource_plan: dict[str, Any],
) -> CanonicalPlanningOutcome:
    return CanonicalPlanningOutcome(
        status="planned",
        canonical_input=canonical_input,
        evidence_plan=evidence_plan,
        resource_plan=resource_plan,
    )


def clarification_outcome(
    *,
    canonical_input: dict[str, Any] | None,
    question: str,
    unresolved_fields: list[str],
    handoff_id: str,
    handoff_version: int,
    reason: str = "",
) -> CanonicalPlanningOutcome:
    return CanonicalPlanningOutcome(
        status="clarification_required",
        canonical_input=canonical_input,
        clarification=ClarificationRequest(
            question=question,
            unresolved_fields=list(unresolved_fields),
            handoff_id=handoff_id,
            handoff_version=handoff_version,
            reason=reason,
        ),
    )


def awaiting_investigation_plan_outcome(
    *,
    canonical_input: dict[str, Any],
) -> CanonicalPlanningOutcome:
    """P0: investigation-shaped Final RQC waits for plan proposal / envelope (no ResourcePlan)."""
    return CanonicalPlanningOutcome(
        status="awaiting_investigation_plan",
        canonical_input=canonical_input,
    )


def policy_blocked_outcome(
    *,
    canonical_input: dict[str, Any] | None,
    policy_reason: str,
    evidence_plan: dict[str, Any] | None = None,
) -> CanonicalPlanningOutcome:
    return CanonicalPlanningOutcome(
        status="policy_blocked",
        canonical_input=canonical_input,
        policy_reason=policy_reason,
        evidence_plan=evidence_plan,
    )


def failure_outcome(
    status: CanonicalPlanningStatus,
    *,
    category: str,
    reason: str,
    canonical_input: dict[str, Any] | None = None,
    detail: str | None = None,
) -> CanonicalPlanningOutcome:
    if status not in FAILURE_STATUSES:
        raise ValueError(f"{status} is not a failure status")
    return CanonicalPlanningOutcome(
        status=status,
        canonical_input=canonical_input,
        failure=PlanningFailure(category=category, reason=reason, detail=detail),
    )


def outcome_from_state(state: dict[str, Any]) -> CanonicalPlanningOutcome | None:
    """Read the outcome back off pipeline state, tolerating the dict round-trip.

    Prefer ``read_canonical_planning_outcome`` for dispatch, validation, and gate
    paths — it distinguishes absent from malformed. This helper remains for tests
    and transitional callers that expect ``None`` on absent keys only.
    """
    raw = state.get("canonical_planning_outcome")
    if isinstance(raw, CanonicalPlanningOutcome):
        return raw
    if isinstance(raw, dict):
        return CanonicalPlanningOutcome.model_validate(raw)
    return None
