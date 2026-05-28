"""Stage 3K-Q3 vetted detection registry models."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class VettingStatus(StrEnum):
    APPROVED = "approved"
    PROVISIONAL = "provisional"
    DEPRECATED = "deprecated"
    UNVETTED = "unvetted"


DetectionSource = Literal["correlation_search", "escu", "soc_approved_logic"]
RiskClass = Literal["behavioral", "sequence", "threshold"]


class DetectionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detection_ref: str
    family: str
    description: str
    source: DetectionSource
    vetting_status: VettingStatus
    last_reviewed: date
    risk_class: RiskClass = "behavioral"
    required_inputs: list[str] = Field(default_factory=list)
    evidence_output_contract_ref: str = ""
    requires_human_validation: bool = True


class DetectionRegistryDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coe_synthetic_fixture: bool = True
    captured_live_run: bool = False
    production_execution: bool = False
    detections: list[DetectionRecord]


class DetectionBindingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bound: bool = False
    detection_ref: str | None = None
    family: str | None = None
    vetting_status: VettingStatus | None = None
    requires_human_validation: bool | None = None
    reasons: list[str] = Field(default_factory=list)
    unbound_reason: str | None = None

    def model_dump(self) -> dict[str, Any]:
        data = super().model_dump()
        if self.vetting_status is not None:
            data["vetting_status"] = self.vetting_status.value
        return data
