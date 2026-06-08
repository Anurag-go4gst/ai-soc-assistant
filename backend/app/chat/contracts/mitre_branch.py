from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


MitreBranchStatus = Literal["skipped", "completed", "requires_context", "not_applicable"]
MitreTechniqueStatus = Literal[
    "candidate",
    "evidence_supported",
    "requires_validation",
    "not_claimed",
    "ruled_out",
]


class MitreTechniqueEvidenceStatus(BaseModel):
    technique_id: str
    status: MitreTechniqueStatus
    reason: str
    evidence_keys: list[str] = Field(default_factory=list)


class MitreBranchResult(BaseModel):
    branch_name: str = "mitre"
    status: MitreBranchStatus
    branch_authority: str = "planner_mitre_branch"
    ran: bool = False
    reason: str
    use_case_id: str | None = None
    question_ref: str | None = None
    mitre_decision: dict[str, object] | None = None
    technique_statuses: list[MitreTechniqueEvidenceStatus] = Field(default_factory=list)
    evidence_supported_mitre: list[str] = Field(default_factory=list)
    candidate_mitre: list[str] = Field(default_factory=list)
    requires_validation_mitre: list[str] = Field(default_factory=list)
    not_claimed_mitre: list[str] = Field(default_factory=list)
    ruled_out_mitre: list[str] = Field(default_factory=list)
    metadata_only_candidates: list[str] = Field(default_factory=list)
