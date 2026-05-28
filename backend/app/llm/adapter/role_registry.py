from __future__ import annotations

from typing import TypeAlias

from app.llm.adapter.schemas import (
    AnalystResponseDraft,
    QueryUnderstandingCandidate,
    ReasoningAdvisoryResult,
    SeverityRationaleAdvisory,
    SplAdvisoryCandidate,
    TemplateMatchSemanticAssistPayload,
    TemplateRenderParameterAssistPayload,
)
from app.llm.registry_settings import ROLE_DEFAULTS, ROLE_ENV_MAP

AdapterSchema: TypeAlias = type[QueryUnderstandingCandidate | ReasoningAdvisoryResult | AnalystResponseDraft | SplAdvisoryCandidate | SeverityRationaleAdvisory]

ROLE_SCHEMA_REGISTRY: dict[str, AdapterSchema] = {
    "intent_shadow_classifier": QueryUnderstandingCandidate,
    "pattern_reasoner": ReasoningAdvisoryResult,
    "mitre_reasoner": ReasoningAdvisoryResult,
    "missing_evidence_reasoner": ReasoningAdvisoryResult,
    "risk_rationale_reasoner": SeverityRationaleAdvisory,
    "analyst_response_drafter": AnalystResponseDraft,
    "spl_advisory_generator": SplAdvisoryCandidate,
    "template_match_semantic_assist": TemplateMatchSemanticAssistPayload,
    "template_render_parameter_assist": TemplateRenderParameterAssistPayload,
}


def schema_for_role(role: str) -> AdapterSchema:
    try:
        return ROLE_SCHEMA_REGISTRY[role]
    except KeyError as exc:
        raise ValueError(f"unknown LLM adapter role: {role}") from exc


def validate_role_registry() -> list[str]:
    errors: list[str] = []
    configured_roles = {str(item["role"]) for item in ROLE_DEFAULTS}
    env_roles = set(ROLE_ENV_MAP)
    for role in ROLE_SCHEMA_REGISTRY:
        if role not in configured_roles:
            errors.append(f"role_not_in_defaults:{role}")
        if role not in env_roles:
            errors.append(f"role_not_in_env_map:{role}")
    return errors
