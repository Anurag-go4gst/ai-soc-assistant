from __future__ import annotations

from pydantic import BaseModel, Field


class SynthesisStatus(BaseModel):
    enabled: bool = False
    status: str = "disabled"
    provider: str | None = None
    model: str | None = None
    reason: str = "Stage 3K evidence-based synthesis is not enabled."
    allowed_inputs: list[str] = Field(default_factory=lambda: ["StructuredContext", "SourceEvidence summaries", "approved RAG excerpts"])
