from __future__ import annotations

from pydantic import BaseModel, Field


class SkillDefinition(BaseModel):
    skill_id: str
    display_name: str
    purpose: str
    routable: bool
    pipeline_stage: bool
    input_contract: str
    output_contract: str
    allowed_tools: list[str] = Field(default_factory=list)
    blocked_tools: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)
    supported_use_cases: list[str] = Field(default_factory=list)
    default_workflow: list[str] = Field(default_factory=list)
    hil_policy: str
    action_tier_allowed: int


class SkillChain(BaseModel):
    chain_id: str
    selected_skill: str
    stages: list[str] = Field(default_factory=list)
    routable_skill: str
    pipeline_stages: list[str] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    selection_reason: str


class SkillSelectionResult(BaseModel):
    selected_skill: str
    selected_use_case_id: str | None = None
    selected_chain: SkillChain
    decision_source: str
    selection_status: str
    rule_based_skill: str
    registry_primary_skill: str | None = None
    llm_assisted_skill: str | None = None
    alternatives: list[str] = Field(default_factory=list)
    policy_notes: list[str] = Field(default_factory=list)
