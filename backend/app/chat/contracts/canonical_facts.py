"""CanonicalFacts — append-only fact spine for node-to-node continuity (plan 5.1)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

FACT_AUTHORITY = "canonical_facts_spine"

FactKind = Literal[
    "entity",
    "timeframe",
    "executed_evidence",
    "negative_evidence",
    "cve_finding",
    "mitre_candidate",
    "mitre_decision",
    "rag_citation",
    "plan_step_outcome",
]

EvidenceClass = Literal[
    "rag",
    "mcp_search",
    "mcp_discovery",
    "cve",
    "mitre",
    "spl",
    "plan",
    "session",
    "unknown",
]


class FactProvenance(BaseModel):
    node: str
    step_id: str | None = None
    evidence_class: EvidenceClass = "unknown"


class CanonicalFact(BaseModel):
    fact_id: str
    kind: FactKind
    payload: dict[str, Any] = Field(default_factory=dict)
    provenance: FactProvenance


class CanonicalFacts(BaseModel):
    schema_version: Literal["v1"] = "v1"
    authority_holder: str = FACT_AUTHORITY
    facts: list[CanonicalFact] = Field(default_factory=list)

    def kinds(self) -> set[str]:
        return {fact.kind for fact in self.facts}

    def facts_by_kind(self, kind: FactKind) -> list[CanonicalFact]:
        return [fact for fact in self.facts if fact.kind == kind]

    def model_dump_canonical(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
