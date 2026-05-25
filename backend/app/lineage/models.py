from __future__ import annotations

from pydantic import BaseModel, Field


class LineageStage(BaseModel):
    stage_id: str
    status: str
    visible_label: str
    explanation: str
    technical_output: dict[str, object] = Field(default_factory=dict)
    produced_answer_sections: list[str] = Field(default_factory=list)
    current_mode_source: str
    production_equivalent: str


class InvestigationLineage(BaseModel):
    lineage_id: str
    stages: list[LineageStage] = Field(default_factory=list)
    summary: str
