from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


LlmIntentAdjudicationStatus = Literal["skipped", "accepted", "rejected", "corrected"]


class LLMIntentAdvisory(BaseModel):
    intent_family_candidate: str | None = None
    path_type_candidate: str | None = None
    question_ref_candidate: str | None = None
    use_case_id_candidate: str | None = None
    paraphrase_detected: bool = False
    ambiguity_reasons: list[str] = Field(default_factory=list)
    clarification_draft: str | None = None
    evidence_need_hints: list[str] = Field(default_factory=list)
    confidence_metadata: dict[str, Any] = Field(default_factory=dict)
    llm_called: bool = False
    dropped_reasons: list[str] = Field(default_factory=list)
    adapter_warnings: list[str] = Field(default_factory=list)
    adjudication_status: LlmIntentAdjudicationStatus = "skipped"
    adjudication_reason: str | None = None

