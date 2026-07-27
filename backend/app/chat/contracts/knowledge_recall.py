"""Typed knowledge_recall DetailTool contract."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

KnowledgeSource = Literal[
    "CVE",
    "MITRE",
    "ATLAS",
    "internal_sop",
    "internal_policy",
    "product_knowledge",
    "vendor_advisory",
    "playbook",
    "reference_registry",
    "other",
]

RetrievalMode = Literal["reference_lookup", "semantic_search", "exact_id"]
KnowledgeRecallStatus = Literal["success", "partial", "empty", "unavailable", "error"]


class KnowledgeFact(BaseModel):
    fact_id: str
    text: str
    source: KnowledgeSource
    reference_id: str | None = None


class KnowledgeCitation(BaseModel):
    source: KnowledgeSource
    reference_id: str | None = None
    title: str | None = None
    url: str | None = None


class KnowledgeRecallRequest(BaseModel):
    query: str
    reference_ids: list[str] = Field(default_factory=list)
    sources: list[KnowledgeSource] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    max_results: int = 10
    retrieval_mode: RetrievalMode = "reference_lookup"


class KnowledgeRecallResult(BaseModel):
    status: KnowledgeRecallStatus
    facts: list[KnowledgeFact] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    citations: list[KnowledgeCitation] = Field(default_factory=list)
    source_names: list[str] = Field(default_factory=list)
    source_versions: dict[str, str] = Field(default_factory=dict)
    retrieved_at: str | None = None
    confidence: float = 0.0
    limitations: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    tool_call_id: str | None = None
