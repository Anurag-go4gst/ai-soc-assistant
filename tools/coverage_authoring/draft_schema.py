"""Draft document wrapper for Q4A coverage authoring."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.coverage.coverage_models import PatternCoverageEntry

GENERATED_BY = "stage3k_q4a_coverage_drafter"


class CoverageDraftDocument(BaseModel):
    """Author-time draft file; not loaded by runtime /chat."""

    model_config = ConfigDict(extra="forbid")

    draft_only: bool = True
    generated_by: str = GENERATED_BY
    requires_human_review: bool = True
    promoted_to_manifest: bool = False
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    validation_warnings: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)
    entry: PatternCoverageEntry

    def to_json_dict(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        entry = data.pop("entry")
        return {**data, "entry": entry}
