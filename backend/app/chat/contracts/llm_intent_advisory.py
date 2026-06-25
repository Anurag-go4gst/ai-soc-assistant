from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


LlmIntentAdjudicationStatus = Literal["skipped", "accepted", "rejected", "corrected", "promoted"]


class LLMIntentAdvisory(BaseModel):
    intent_family_candidate: str | None = None
    path_type_candidate: str | None = None
    question_ref_candidate: str | None = None
    use_case_id_candidate: str | None = None
    paraphrase_detected: bool = False
    ambiguity_reasons: list[str] = Field(default_factory=list)
    clarification_draft: str | None = None
    evidence_need_hints: list[str] = Field(default_factory=list)
    entity_slots_candidate: dict[str, Any] = Field(default_factory=dict)
    entity_slot_confidence: dict[str, float] = Field(default_factory=dict)
    entity_slot_reasons: dict[str, str] = Field(default_factory=dict)
    confidence_metadata: dict[str, Any] = Field(default_factory=dict)
    llm_called: bool = False
    dropped_reasons: list[str] = Field(default_factory=list)
    adapter_warnings: list[str] = Field(default_factory=list)
    adjudication_status: LlmIntentAdjudicationStatus = "skipped"
    adjudication_reason: str | None = None
    provider_label: str | None = None

    def get(self, key: str, default: Any = None) -> Any:
        """Read-only dict compatibility for legacy trace/test consumers.

        Live node boundaries retain this validated model; callers that only read
        optional advisory fields can migrate without a flag-day conversion.
        """
        return getattr(self, key, default)
