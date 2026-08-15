"""Shared staged sufficiency result — adapter over existing deterministic checks.

Plan 8 S0: one conceptual vocabulary for UNDERSTANDING and EVIDENCE sufficiency.
This object is a projection, not a planner, router, policy engine, or LLM authority.
Existing qualification, known-completeness, and context-sufficiency rules stay in
force; later items (U0, D0) consume this adapter rather than replacing those rules.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

SCHEMA_VERSION = "staged_sufficiency_v1"

SufficiencyStage = Literal["UNDERSTANDING", "EVIDENCE"]
SufficiencyStatus = Literal["SUFFICIENT", "PARTIAL", "INSUFFICIENT", "BLOCKED"]
SufficiencyNextAction = Literal["CONTINUE", "CALL_T4", "CLARIFY", "DEGRADE", "BLOCK"]

_EVIDENCE_STATUS_BY_MODE: dict[str, SufficiencyStatus] = {
    "full_answer": "SUFFICIENT",
    "knowledge_only_answer": "SUFFICIENT",
    "partial_answer": "PARTIAL",
    "spl_review_only": "PARTIAL",
    "insufficient_evidence": "INSUFFICIENT",
    "analyst_review_required": "INSUFFICIENT",
    "blocked_by_policy": "BLOCKED",
}

_EVIDENCE_NEXT_BY_STATUS: dict[SufficiencyStatus, SufficiencyNextAction] = {
    "SUFFICIENT": "CONTINUE",
    "PARTIAL": "CONTINUE",
    "INSUFFICIENT": "DEGRADE",
    "BLOCKED": "BLOCK",
}


class StagedSufficiencyResult(BaseModel):
    """Deterministic staged sufficiency projection. No execution or route authority."""

    schema_version: str = SCHEMA_VERSION
    stage: SufficiencyStage
    status: SufficiencyStatus
    required: list[str] = Field(default_factory=list)
    available: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    locked: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    next_action: SufficiencyNextAction

    @model_validator(mode="after")
    def _derive_and_constrain(self) -> StagedSufficiencyResult:
        expected = derive_next_action(
            stage=self.stage,
            status=self.status,
            unresolved=self.unresolved,
            reason_codes=self.reason_codes,
        )
        if self.next_action != expected:
            object.__setattr__(self, "next_action", expected)
        if self.stage == "EVIDENCE" and self.next_action == "CALL_T4":
            raise ValueError("EVIDENCE sufficiency cannot request CALL_T4")
        return self


def derive_next_action(
    *,
    stage: SufficiencyStage,
    status: SufficiencyStatus,
    unresolved: list[str] | tuple[str, ...] = (),
    reason_codes: list[str] | tuple[str, ...] = (),
) -> SufficiencyNextAction:
    """Pure policy projection. No LLM, route, or capability grant."""
    reasons = set(reason_codes)
    if status == "BLOCKED" or "policy_blocked" in reasons or "blocked_by_policy" in reasons:
        return "BLOCK"
    if "clarification_required" in reasons or status == "INSUFFICIENT" and stage == "UNDERSTANDING":
        if "clarification_required" in reasons or "user_only_missing" in reasons:
            return "CLARIFY"
        if stage == "UNDERSTANDING":
            return "CLARIFY"
        return "DEGRADE"
    if (
        stage == "UNDERSTANDING"
        and status in {"PARTIAL", "INSUFFICIENT"}
        and unresolved
        and "clarification_required" not in reasons
    ):
        return "CALL_T4"
    if status == "INSUFFICIENT":
        return "DEGRADE"
    return "CONTINUE"


def from_context_sufficiency(envelope: dict[str, Any]) -> StagedSufficiencyResult:
    """Project Stage 3J context-sufficiency output. Does not replace the gate."""
    mode = str(envelope.get("status") or "insufficient_evidence")
    status = _EVIDENCE_STATUS_BY_MODE.get(mode, "INSUFFICIENT")
    missing = [str(item) for item in (envelope.get("missing_evidence") or [])]
    reasons = [str(item) for item in (envelope.get("reasons") or [])]
    if mode == "blocked_by_policy":
        reasons = [*reasons, "blocked_by_policy"]
    if mode == "analyst_review_required":
        reasons = [*reasons, "clarification_required"]
        status = "INSUFFICIENT"
    next_action = derive_next_action(
        stage="EVIDENCE",
        status=status,
        unresolved=(),
        reason_codes=reasons,
    )
    available: list[str] = []
    if mode in {"full_answer", "partial_answer"}:
        available.append("execution_evidence")
    if mode == "knowledge_only_answer":
        available.append("rag_evidence")
    if mode == "spl_review_only":
        available.append("candidate_spl_advisory")
    return StagedSufficiencyResult(
        stage="EVIDENCE",
        status=status,
        required=list(missing) if missing and status != "SUFFICIENT" else [],
        available=available,
        missing=missing,
        locked=[],
        unresolved=[],
        reason_codes=sorted(set(reasons)),
        next_action=next_action,
    )


def from_understanding_state(
    *,
    required: list[str] | None = None,
    available: list[str] | None = None,
    missing: list[str] | None = None,
    locked: list[str] | None = None,
    unresolved: list[str] | None = None,
    clarification_required: bool = False,
    policy_blocked: bool = False,
    completeness_status: str | None = None,
) -> StagedSufficiencyResult:
    """Project existing known-completeness / RQC fields into UNDERSTANDING sufficiency.

    Does not evaluate new understanding rules. U0 owns job-aware locked/unresolved
    classification; this adapter only shapes already-decided lists.
    """
    required_fields = list(required or [])
    available_fields = list(available or [])
    missing_fields = list(missing or [])
    locked_fields = list(locked or [])
    unresolved_fields = list(unresolved or [])
    reasons: list[str] = []
    if policy_blocked:
        reasons.append("policy_blocked")
        status: SufficiencyStatus = "BLOCKED"
    elif clarification_required or completeness_status == "clarification_required":
        reasons.append("clarification_required")
        status = "INSUFFICIENT"
    elif missing_fields and not unresolved_fields:
        reasons.append("missing_required_fields")
        status = "INSUFFICIENT"
    elif unresolved_fields:
        reasons.append("unresolved_semantic_fields")
        status = "PARTIAL"
    elif completeness_status == "incomplete":
        reasons.append("completeness_incomplete")
        status = "PARTIAL"
    else:
        status = "SUFFICIENT"
    next_action = derive_next_action(
        stage="UNDERSTANDING",
        status=status,
        unresolved=unresolved_fields,
        reason_codes=reasons,
    )
    return StagedSufficiencyResult(
        stage="UNDERSTANDING",
        status=status,
        required=required_fields,
        available=available_fields,
        missing=missing_fields,
        locked=locked_fields,
        unresolved=unresolved_fields,
        reason_codes=sorted(set(reasons)),
        next_action=next_action,
    )
