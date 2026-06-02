"""Normalized MITRE registry metadata schema (metadata only — not observed evidence)."""

from __future__ import annotations

from enum import Enum
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

MITRE_REGISTRY_SCHEMA_VERSION = "2026-06-control-plane-v1"
MITRE_REGISTRY_ROLE = "metadata_not_evidence"


class MitreVisibilityPolicy(str, Enum):
    trace_only = "trace_only"
    answer_if_requested = "answer_if_requested"
    answer_if_supported = "answer_if_supported"


class MitreRegistryMetadata(BaseModel):
    """Governed MITRE mapping metadata for a 105 question or 42 use-case row."""

    schema_version: str = Field(default=MITRE_REGISTRY_SCHEMA_VERSION)
    registry_role: str = Field(default=MITRE_REGISTRY_ROLE)
    mitre_permitted: list[str] = Field(default_factory=list)
    mitre_candidate: list[str] = Field(default_factory=list)
    mitre_blocked: list[str] = Field(default_factory=list)
    mitre_requires_evidence: bool = True
    mitre_requires_alert_context: bool = False
    mitre_visibility_policy: MitreVisibilityPolicy = MitreVisibilityPolicy.trace_only
    source_question_ref: str | None = None
    source_use_case_id: str | None = None
    mapping_rationale: str | None = None

    @field_validator("mitre_permitted", "mitre_candidate", "mitre_blocked", mode="before")
    @classmethod
    def _normalize_technique_ids(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            if not item:
                continue
            upper = str(item).strip().upper()
            if upper and upper not in seen:
                seen.add(upper)
                normalized.append(upper)
        return normalized

    @model_validator(mode="after")
    def _validate_non_overlapping_sets(self) -> Self:
        permitted = set(self.mitre_permitted)
        candidate = set(self.mitre_candidate)
        blocked = set(self.mitre_blocked)
        if permitted & blocked:
            overlap = sorted(permitted & blocked)
            raise ValueError(f"mitre_permitted overlaps mitre_blocked: {overlap}")
        if candidate & blocked:
            overlap = sorted(candidate & blocked)
            raise ValueError(f"mitre_candidate overlaps mitre_blocked: {overlap}")
        return self

    def all_mapped_technique_ids(self) -> list[str]:
        """Union of permitted and candidate IDs (registry-level allow list)."""
        seen: set[str] = set()
        ordered: list[str] = []
        for tid in [*self.mitre_permitted, *self.mitre_candidate]:
            if tid not in seen:
                seen.add(tid)
                ordered.append(tid)
        return ordered

    def techniques_missing_from_attack_subset(self, attack_subset_ids: set[str]) -> list[str]:
        """Permitted/candidate techniques not in mitre_attack_subset.json (audit warning only)."""
        missing: list[str] = []
        for tid in self.all_mapped_technique_ids():
            if tid not in attack_subset_ids:
                missing.append(tid)
        return missing

    def blocked_missing_from_attack_subset(self, attack_subset_ids: set[str]) -> list[str]:
        """Blocked IDs absent from attack subset (defensive block list — informational)."""
        return [tid for tid in self.mitre_blocked if tid not in attack_subset_ids]
