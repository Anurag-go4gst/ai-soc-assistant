"""Pydantic models for the Stage 3K-Q4 pattern coverage manifest."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CoverageReadiness(StrEnum):
    COE_SYNTHETIC_FIXTURE = "coe_synthetic_fixture"
    SOURCE_READY = "source_ready"
    IOC_DEPENDENT = "ioc_dependent"
    DETECTION_DEPENDENT = "detection_dependent"
    DEPENDENCY_MISSING = "dependency_missing"
    BLOCKED_MISSING_CONTEXT = "blocked_missing_context"


CoverageGroup = Literal[
    "template_only",
    "ioc_dependent",
    "detection_dependent",
    "multi_signal",
    "negative_cannot_route",
]


class CoverageGovernance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_authorized: bool = False
    spl_execution_enabled: bool = False
    mcp_execution_enabled: bool = False
    llm_final_synthesis_enabled: bool = False
    answer_guard_enabled: bool = False
    sample_only: bool = False
    execution_eligible: bool = False


class PatternCoverageEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coverage_id: str
    question_ref: str
    question: str
    coverage_group: CoverageGroup
    primary_skill: str
    sub_invocations: list[dict[str, Any]] = Field(default_factory=list)
    route_plan_shape: dict[str, Any]
    template_ref: str | None = None
    lookup_ref: str | None = None
    detection_family: str | None = None
    detection_ref: str | None = None
    evidence_contract_ref: str
    readiness: CoverageReadiness
    clarification_required: list[str] = Field(default_factory=list)
    expected_route_status: str
    expected_blockers: list[str] = Field(default_factory=list)
    governance: CoverageGovernance
    notes: str = ""


class PatternCoverageManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pack_version: str
    coe_synthetic_fixture: bool = True
    captured_live_run: bool = False
    production_execution: bool = False
    entries: list[PatternCoverageEntry]
