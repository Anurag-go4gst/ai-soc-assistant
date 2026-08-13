"""Advisory T4 semantic proposal — understanding only, no skill, no execution authority."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.chat.contracts.resolved_query import ALLOWED_CAPABILITIES, AmbiguityState, AnswerGoal


class SemanticT4Proposal(BaseModel):
    """Closed schema for one bounded T4 semantic hop. Extra keys (incl. skill) fail closed."""

    model_config = ConfigDict(extra="forbid")

    normalized_goal: str | None = None
    intent_family: str | None = None
    answer_goal: AnswerGoal | None = None
    ambiguity_state: AmbiguityState | None = None
    clarification_required: bool | None = None
    clarification_reason: str | None = None
    required_capabilities: list[str] = Field(default_factory=list)
    prohibited_capabilities: list[str] = Field(default_factory=list)
    evidence_requirements: list[str] = Field(default_factory=list)
    entities: dict[str, Any] = Field(default_factory=dict)
    time_scope: str | None = None
    confidence: float | None = None

    def capability_sets(self) -> tuple[frozenset[str], frozenset[str]]:
        required = frozenset(self.required_capabilities)
        prohibited = frozenset(self.prohibited_capabilities)
        unknown = (required | prohibited) - ALLOWED_CAPABILITIES
        if unknown:
            raise ValueError(f"unknown capability values: {sorted(unknown)}")
        overlap = required & prohibited
        if overlap:
            raise ValueError(f"capability cannot be both required and prohibited: {sorted(overlap)}")
        return required, prohibited
