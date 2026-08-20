from __future__ import annotations

from pydantic import BaseModel, Field


class UseCaseDefinition(BaseModel):
    use_case_id: str
    display_name: str
    category: str
    intent_patterns: list[str] = Field(default_factory=list)
    # Optional bind constraints (plan 2026-08-19_1130 item 5). Absent / empty
    # lists are a no-op — the row matches exactly as it did before these fields.
    # `exclusion_patterns`: substring veto (same leading-boundary rule as
    # intent_patterns). `requires_signals`: names from extract_query_signals;
    # prefix `!` means the signal must be absent/false.
    exclusion_patterns: list[str] = Field(default_factory=list)
    requires_signals: list[str] = Field(default_factory=list)
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
    # Row-level routing authority (T0/T1 architecture).  Defaults preserve the
    # legacy posture: a catalogue row behaves as deterministic T0 (skip the
    # intent LLM) unless it opts out.  SPL-meta rows (soc_generate_spl,
    # soc_optimize_spl) override these to declare themselves T1 SPL-native.
    registry_tier: str = "catalog_default"
    use_case_type: str | None = None
    t0_exact_authority: bool = True
    llm_advisory_recommended: bool = False
    requires_t2_shape_check: bool = False
    pattern_strength: str | None = None
    must_not_override_detection_family: bool = False
    execution_eligible_default: bool = False
    human_review_required: bool = False


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
    # Bind diagnostics (plan 2026-08-19_1130). `coverage_score` ranks the bind
    # (item 3). `confidence` is a 0–1 squash of that score for QU consumers.
    # `bind_margin` below `_BIND_MARGIN_TOO_CLOSE` (item 4) returns no bind.
    coverage_ratio: float | None = None
    specificity: float | None = None
    coverage_score: float | None = None
    runner_up_score: float | None = None
    bind_margin: float | None = None
