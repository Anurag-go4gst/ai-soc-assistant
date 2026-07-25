"""Reference and knowledge query qualification (T4 → T0 resolution)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RequestedScope = Literal[
    "knowledge_only",
    "environment_status",
    "evidence_correlation",
    "investigation",
    "remediation_recommendation",
    "remediation_execution",
    "composite",
    "clarification",
]

QualificationSource = Literal["deterministic_rule", "classifier"]


class ReferenceQueryQualification(BaseModel):
    reference_types: list[str] = Field(default_factory=list)
    reference_ids: list[str] = Field(default_factory=list)
    requested_scopes: list[RequestedScope] = Field(default_factory=list)
    status_check_required: bool = False
    evidence_correlation_required: bool = False
    action_requested: bool = False
    environment_scope_present: bool = False
    catalogue_candidate: str | None = None
    confidence: float = 0.0
    qualification_source: QualificationSource = "deterministic_rule"

    @property
    def resolves_to_t0(self) -> bool:
        if self.action_requested or self.status_check_required or self.evidence_correlation_required:
            return False
        if self.environment_scope_present:
            return False
        scopes = set(self.requested_scopes)
        if not scopes:
            return False
        return scopes <= {"knowledge_only"}
