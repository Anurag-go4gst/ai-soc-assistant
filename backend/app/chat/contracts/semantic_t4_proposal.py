"""Advisory T4 semantic proposal — understanding only, no skill, no execution authority.

Frozen production proposal contract (Cisco 8B-validated). T4 may emit only these
fields as semantic meaning. Deterministic merge remains authority for RQC,
capabilities, route, SPL, MCP, RBAC, HIL, and policy.

See docs/ai/t4_semantic_prompting_playbook.md before changing this schema.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.chat.contracts.resolved_query import ALLOWED_CAPABILITIES, AmbiguityState, AnswerGoal

FROZEN_SEMANTIC_T4_PROPOSAL_FIELDS: tuple[str, ...] = (
    "normalized_goal",
    "evidence_requirements",
    "competing_hypotheses",
    "semantic_ambiguity",
    "clarification_required",
    "clarification_reason",
    "semantic_confidence",
)

FROZEN_SEMANTIC_AMBIGUITY_VALUES: tuple[str, ...] = (
    "unambiguous",
    "clarification_required",
)

# Unresolved semantic fills still merged when present. Not frozen-contract fields.
OPTIONAL_UNRESOLVED_FILLS: tuple[str, ...] = ("entities", "time_scope")

SemanticAmbiguity = Literal["unambiguous", "clarification_required"]


class SemanticT4Proposal(BaseModel):
    """Closed schema for one bounded T4 semantic hop. Extra keys (incl. skill) fail closed."""

    model_config = ConfigDict(extra="forbid")

    normalized_goal: str | None = None
    evidence_requirements: list[str] = Field(default_factory=list)
    competing_hypotheses: list[str] = Field(default_factory=list)
    semantic_ambiguity: SemanticAmbiguity | None = None
    clarification_required: bool | None = None
    clarification_reason: str | None = None
    semantic_confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    # Optional unresolved fills (production merge). Not part of the frozen offered contract.
    entities: dict[str, Any] = Field(default_factory=dict)
    time_scope: str | None = None

    # Legacy / merge-reject-only. Never offered in the frozen schema. Kept so a
    # model that still emits them is rejected by merge rather than silently dropped
    # without a governance reason.
    intent_family: str | None = None
    answer_goal: AnswerGoal | None = None
    ambiguity_state: AmbiguityState | None = None
    required_capabilities: list[str] = Field(default_factory=list)
    prohibited_capabilities: list[str] = Field(default_factory=list)
    confidence: float | None = None

    @model_validator(mode="before")
    @classmethod
    def _alias_frozen_names(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        ambiguity = out.get("semantic_ambiguity")
        if ambiguity in FROZEN_SEMANTIC_AMBIGUITY_VALUES and "ambiguity_state" not in out:
            out["ambiguity_state"] = ambiguity
        legacy_ambiguity = out.get("ambiguity_state")
        if (
            "semantic_ambiguity" not in out
            and legacy_ambiguity in FROZEN_SEMANTIC_AMBIGUITY_VALUES
        ):
            out["semantic_ambiguity"] = legacy_ambiguity
        if "semantic_confidence" in out and "confidence" not in out:
            out["confidence"] = out["semantic_confidence"]
        if "confidence" in out and "semantic_confidence" not in out:
            out["semantic_confidence"] = out["confidence"]
        return out

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
