from __future__ import annotations

from pydantic import BaseModel, Field


class UseCaseDefinition(BaseModel):
    use_case_id: str
    display_name: str
    category: str
    intent_patterns: list[str] = Field(default_factory=list)
    example_queries: list[str] = Field(default_factory=list)
    required_entities: list[str] = Field(default_factory=list)
    optional_entities: list[str] = Field(default_factory=list)
    default_time_window: str | None = None
    primary_skill: str
    secondary_skills: list[str] = Field(default_factory=list)
    required_sources: list[str] = Field(default_factory=list)
    optional_sources: list[str] = Field(default_factory=list)
    default_spl_template: str | None = None
    rag_collections: list[str] = Field(default_factory=list)
    mitre_candidates: list[str] = Field(default_factory=list)
    severity_policy: str | None = None
    action_capability_tier: int
    output_template: str


class UseCaseSelection(BaseModel):
    use_case_id: str
    display_name: str
    category: str
    primary_skill: str
    confidence: float
    matched_patterns: list[str] = Field(default_factory=list)
    default_spl_template: str | None = None
    output_template: str
    required_sources: list[str] = Field(default_factory=list)
    optional_sources: list[str] = Field(default_factory=list)
    action_capability_tier: int
