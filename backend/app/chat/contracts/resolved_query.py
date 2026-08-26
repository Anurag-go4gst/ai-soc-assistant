"""Resolved query understanding contract — pre-route, no skill, no execution authority.

Plan 5 B1: carries what the system understood about the query before route adjudication.
Must not mix in post-route fields (selected skill, RouteContract intent_family, etc.).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.chat.contracts.canonical_planning_input import CatalogueTier
from app.chat.skill_intent_compatibility import CAPABILITY_MCP, CAPABILITY_SPL

SCHEMA_VERSION = "resolved_query_contract_v1"
CONTRACT_VERSION = "2026-08-26"

# Closed capability vocabulary — must align with skill_intent_compatibility (B5 reuses it).
ALLOWED_CAPABILITIES = frozenset({CAPABILITY_SPL, CAPABILITY_MCP})

AmbiguityState = Literal[
    "unambiguous",
    "clarification_required",
    "policy_blocked",
    "insufficient_signals",
]
UnderstandingSource = Literal["deterministic_qualification", "semantic_t4"]
AnswerGoal = Literal[
    "live_results",
    "analyst_action_guidance",
    "policy_citation",
    "spl_artifact",
    "mitre_mapping",
    "mitre_explanation",
    "severity_assessment",
    "procedural_steps",
    "clarification",
    "reference_lookup",
    "reference_explanation",
]

# Post-P10 convergence — requested conditional actions live on Final RQC (not ResourcePlan).
ConditionalActionKind = Literal["remediation", "email_draft"]
ConditionalActionLifecycle = Literal[
    "REQUESTED",
    "PENDING_CONDITION",
    "ELIGIBLE",
    "APPROVED",
    "EXECUTED",
]


class RequestedConditionalAction(BaseModel):
    """User-requested downstream action preserved without granting eligibility/authority."""

    action_kind: ConditionalActionKind
    lifecycle_state: ConditionalActionLifecycle = "REQUESTED"
    predicate_id: str | None = None
    recipient_roles: list[str] = Field(default_factory=list)


class ResolvedQueryContract(BaseModel):
    """Understanding layer output consumed by route adjudication and resource planning."""

    schema_version: str = SCHEMA_VERSION
    contract_version: str = CONTRACT_VERSION

    normalized_goal: str
    intent_family: str
    answer_goal: AnswerGoal
    ambiguity_state: AmbiguityState
    clarification_required: bool = False
    clarification_reason: str | None = None

    required_capabilities: frozenset[str] = Field(default_factory=frozenset)
    prohibited_capabilities: frozenset[str] = Field(default_factory=frozenset)
    evidence_requirements: list[str] = Field(default_factory=list)
    competing_hypotheses: list[str] = Field(default_factory=list)

    entities: dict[str, Any] = Field(default_factory=dict)
    time_scope: str | None = None

    qualification_tier: CatalogueTier
    qualification_source: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    provenance: dict[str, Any] = Field(default_factory=dict)
    understanding_source: UnderstandingSource = "deterministic_qualification"

    # Plan 8 U0 — T1–T3 authority map. T4 may change only unresolved semantic fields.
    # Derived fields are recomputed after final understanding and are not T4 grants.
    locked_fields: dict[str, Any] = Field(default_factory=dict)
    unresolved_fields: list[str] = Field(default_factory=list)
    derived_field_names: list[str] = Field(default_factory=list)
    understanding_sufficiency: dict[str, Any] | None = None

    # Post-P10: structural home for multi-goal conditional intents (Phase 10 path).
    requested_conditional_actions: list[RequestedConditionalAction] = Field(default_factory=list)
    requested_outputs: list[str] = Field(default_factory=list)

    @field_validator("required_capabilities", "prohibited_capabilities", mode="before")
    @classmethod
    def _normalize_capability_set(cls, value: object) -> frozenset[str]:
        if value is None:
            return frozenset()
        if isinstance(value, frozenset):
            items = value
        elif isinstance(value, (set, list, tuple)):
            items = frozenset(str(v) for v in value)
        else:
            raise ValueError("capabilities must be a set, frozenset, list, or tuple")
        unknown = items - ALLOWED_CAPABILITIES
        if unknown:
            raise ValueError(f"unknown capability values: {sorted(unknown)}")
        return items

    @field_validator("prohibited_capabilities")
    @classmethod
    def _no_overlap(cls, prohibited: frozenset[str], info) -> frozenset[str]:
        required = info.data.get("required_capabilities") or frozenset()
        overlap = required & prohibited
        if overlap:
            raise ValueError(f"capability cannot be both required and prohibited: {sorted(overlap)}")
        return prohibited

    def model_post_init(self, __context: Any) -> None:
        if self.clarification_required and not self.clarification_reason:
            raise ValueError("clarification_required=true requires clarification_reason")
