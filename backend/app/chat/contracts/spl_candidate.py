from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SplCandidateStageResult(BaseModel):
    """Single return contract for the SPL candidate stage (Phase 4).

    Replaces the bare ``(candidate_payload, validation_payload)`` tuple so the LLM
    detection plan and compiler telemetry survive to the workflow node, which is
    solely responsible for persisting them (the compiler must not write state).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    candidate_payload: Any | None = None
    validation_payload: Any | None = None
    detection_plan: dict[str, Any] | None = None
    compiler_telemetry: dict[str, Any] = Field(default_factory=dict)

    def as_legacy_tuple(self) -> tuple[Any | None, Any | None]:
        """Back-compat shim for call sites not yet migrated off the tuple."""
        return self.candidate_payload, self.validation_payload
