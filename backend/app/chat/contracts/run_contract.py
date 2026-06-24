"""RouteContract and RunContract — canonical post-adjudication / post-execution truth."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AUTHORITY_HOLDER = "canonical_run_contract"

SplContractStatus = Literal["not_required", "ready_for_review", "blocked", "review_required"]


class RouteContract(BaseModel):
    """Routing slice after adjudication and effective-skill resolution."""

    canonical_skill: str
    legacy_skill: str | None = None
    legacy_authoritative: bool = False
    authority_holder: str = AUTHORITY_HOLDER
    path_type: str | None = None
    intent_family: str | None = None
    live_data_request: bool = False
    guidance_request: bool = False
    route_source: str | None = None
    adjudication_authority_source: str | None = None


class SourceEvidenceSummary(BaseModel):
    """Wire helper for bundle tests and debug surfaces.

    ``evidence_count`` is the total number of *packaged* records (collected
    telemetry + review/metadata artifacts), retained for backward compatibility.
    Display/lineage text must use ``collected_evidence_count`` and
    ``review_artifact_count`` instead, never ``evidence_count``.
    """

    status: str | None = None
    source_evidence_available: bool = False
    evidence_count: int = 0
    collected_evidence_count: int = 0
    review_artifact_count: int = 0
    candidate_artifact_count: int = 0
    produced_answer_sections: list[str] = Field(default_factory=list)


class RunContract(BaseModel):
    """Full final-run state for preview, HIL, evidence buckets, and render gates."""

    execution_needed_for_answer: bool = False
    mcp_needed_for_live_answer: bool = False
    execution_status: str = "skipped"
    execution_authorized: bool = False
    mcp_allowed: bool = False
    collected_evidence_count: int = 0
    source_evidence_available: bool = False
    effective_hil_required: bool = False
    allow_live_result_language: bool = False
    allow_results_table: bool = False
    allow_mitre_mapping: bool = False
    allow_severity_assessment: bool = False
    spl_candidate_present: bool = False
    spl_candidate_renderable: bool = False
    spl_validated: bool = False
    spl_normalized: bool = False
    spl_execution_eligible: bool = False
    spl_status: SplContractStatus = "not_required"
    spl_block_reason: str | None = None
    routing: RouteContract
    candidate_artifact_refs: list[str] = Field(default_factory=list)
    governance_refs: list[str] = Field(default_factory=list)
    source_evidence_summary: SourceEvidenceSummary | None = None

    def model_dump_canonical(self) -> dict[str, Any]:
        """JSON-serializable dict with nested routing contract."""
        return self.model_dump(mode="json")
