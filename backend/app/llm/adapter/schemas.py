from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.actions.capability_policy import ALLOWED_ACTION_TIERS
from app.llm.adapter.validators import (
    validate_mitre_status,
    validate_output_template,
    validate_requested_output_type,
    validate_skill_id,
    validate_source_id,
    validate_use_case_id,
)
from app.risk.severity_policy import ACTION_PRIORITIES
from app.skills.registry import load_skill_registry


class AdapterPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")


class QueryUnderstandingCandidate(AdapterPayload):
    raw_query: str
    primary_intent: str
    requested_output_type: str
    entities: dict[str, Any] = Field(default_factory=dict)
    candidate_use_case_id: str | None = None
    selected_skill: str
    routable_skills: list[str] = Field(default_factory=list)
    pipeline_stages: list[str] = Field(default_factory=list)
    required_sources: list[str] = Field(default_factory=list)
    optional_sources: list[str] = Field(default_factory=list)
    clarification_needed: bool
    clarification_question: str | None = None
    confidence: float | None = None

    @field_validator("requested_output_type")
    @classmethod
    def _requested_output_type(cls, value: str) -> str:
        return validate_requested_output_type(value)

    @field_validator("candidate_use_case_id")
    @classmethod
    def _use_case_id(cls, value: str | None) -> str | None:
        if value in (None, ""):
            return None
        return validate_use_case_id(value)

    @field_validator("selected_skill")
    @classmethod
    def _selected_skill(cls, value: str) -> str:
        return validate_skill_id(value)

    @field_validator("routable_skills")
    @classmethod
    def _routable_skills(cls, values: list[str]) -> list[str]:
        return [validate_skill_id(value) for value in values]

    @field_validator("pipeline_stages")
    @classmethod
    def _pipeline_stages(cls, values: list[str]) -> list[str]:
        allowed = {item.skill_id for item in load_skill_registry() if item.pipeline_stage}
        invalid = [value for value in values if value not in allowed]
        if invalid:
            raise ValueError(f"invalid pipeline stage: {invalid[0]}")
        return values

    @field_validator("required_sources", "optional_sources")
    @classmethod
    def _sources(cls, values: list[str]) -> list[str]:
        return [validate_source_id(value) for value in values]


class ReasoningAdvisoryResult(AdapterPayload):
    reasoning_summary: str
    pattern_characterization: str | None = None
    mitre_reasoning: list[str] = Field(default_factory=list)
    missing_evidence_analysis: list[str] = Field(default_factory=list)
    why_not_higher_or_final: list[str] = Field(default_factory=list)
    investigation_pivots: list[dict[str, Any]] = Field(default_factory=list)
    unsupported_claims_to_avoid: list[str] = Field(default_factory=list)


class AnalystResponseDraft(AdapterPayload):
    severity_label: str | None = None
    finding_title: str | None = None
    analyst_summary: str | None = None
    splunk_results_table: list[dict[str, Any]] = Field(default_factory=list)
    mitre_mappings: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_playbook: dict[str, Any] | None = None
    foundation_sec_analysis: str | None = None
    recommended_actions: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    blocked_actions: list[str] = Field(default_factory=list)

    @field_validator("mitre_mappings")
    @classmethod
    def _mitre_statuses(cls, values: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for item in values:
            if "status" in item:
                item["status"] = validate_mitre_status(str(item["status"]))
        return values


class SplAdvisoryCandidate(AdapterPayload):
    status: str = "candidate_generated"
    confidence_score: float = 0.0
    confidence_label: str = "low"
    detection_family: str = ""
    candidate_spl: str
    index: str | None = None
    sourcetype: str | None = None
    earliest: str | None = None
    latest: str | None = None
    time_window_hours: int | None = None
    result_cap: int | None = None
    unresolved_slots: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    missing_details: list[str] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(default_factory=list)
    validation_notes: list[str] = Field(default_factory=list)
    soc_std_rules_applied: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    execution_eligible: bool = False
    governed: bool = False
    catalog_approved: bool = False


class TemplateMatchSemanticHints(AdapterPayload):
    source_class_hint: str | None = None
    datamodel_hint: str | None = None
    field_aliases: dict[str, str] = Field(default_factory=dict)


class TemplateMatchSemanticAssistPayload(AdapterPayload):
    llm_semantic_hints: TemplateMatchSemanticHints | None = None


class ExtractedRenderParameters(AdapterPayload):
    host: str | None = None
    user: str | None = None
    src_ip: str | None = None
    dest_ip: str | None = None
    result_limit: int | None = None
    time_window: dict[str, str] | None = None


class TemplateRenderParameterAssistPayload(AdapterPayload):
    extracted_parameters: ExtractedRenderParameters | None = None


class RoutePlanCandidateMetric(AdapterPayload):
    type: str
    field: str


class RoutePlanCandidateEvidenceNeeds(AdapterPayload):
    datamodel: str
    dataset: str | None = None
    group_by: list[str] = Field(default_factory=list)
    metric: RoutePlanCandidateMetric
    cim_fields: list[str] = Field(default_factory=list)
    summariesonly: bool | None = None
    lookup_required: bool = False
    detection_required: bool = False
    detection_family: str | None = None


class RoutePlanCandidateLlmPayload(AdapterPayload):
    primary_skill: str
    operation_type: str
    source_class: str
    evidence_needs: RoutePlanCandidateEvidenceNeeds
    time_window: dict[str, str] | str | None = None
    limit: int | None = None
    clarification_questions: list[str] = Field(default_factory=list)
    rationale: str = ""


class AnalystSummaryNarrationPayload(AdapterPayload):
    summary_sentence_1: str
    summary_sentence_2: str | None = None
    technical_trace_bullets: list[str] = Field(min_length=3, max_length=3)


class SeverityRationaleAdvisory(AdapterPayload):
    selected_severity: str
    why_selected: list[str] = Field(default_factory=list)
    why_not_higher: list[str] = Field(default_factory=list)
    missing_evidence_for_higher: list[str] = Field(default_factory=list)
    escalate_if: list[str] = Field(default_factory=list)
    recommended_validation_steps: list[str] = Field(default_factory=list)
    confidence: float | None = None


class ActionRecommendation(AdapterPayload):
    action: str
    priority: str | None = None
    tier: int | None = None

    @field_validator("priority")
    @classmethod
    def _priority(cls, value: str | None) -> str | None:
        if value is not None and value not in ACTION_PRIORITIES:
            raise ValueError(f"invalid action priority: {value}")
        return value

    @field_validator("tier")
    @classmethod
    def _tier(cls, value: int | None) -> int | None:
        if value is not None and value not in ALLOWED_ACTION_TIERS:
            raise ValueError(f"invalid action tier: {value}")
        return value


class OutputTemplateCandidate(AdapterPayload):
    output_template: str

    @model_validator(mode="after")
    def _validate_template(self) -> "OutputTemplateCandidate":
        self.output_template = validate_output_template(self.output_template)
        return self


class MitreCandidateTechnique(AdapterPayload):
    technique_id: str
    technique_name: str
    confidence: str = "low"
    reason: str = ""


class MitreCandidateMapperPayload(AdapterPayload):
    """P5-10: LLM MITRE candidate mapper output schema.

    Advisory only. Never authoritative. IDs must be validated against local
    ATT&CK bundle before use. soc_approved is always False from LLM output.
    """

    primary_techniques: list[MitreCandidateTechnique] = Field(default_factory=list)
    secondary_techniques: list[MitreCandidateTechnique] = Field(default_factory=list)
    not_applicable_reason: str | None = None
    assumptions: list[str] = Field(default_factory=list)
