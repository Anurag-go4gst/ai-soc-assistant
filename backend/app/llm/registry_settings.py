"""Stage 3J-B governed LLM readiness status.

Builds a non-secret view of the ``AI_SOC_LLM_*`` configuration layer for the
upcoming evidence-based synthesis stage. This module never calls a real LLM and
never returns API keys, endpoint credentials, or raw secret values — only
``*_configured`` booleans. ``ai_soc_llm_mode == "disabled"`` forces the layer
off regardless of ``ai_soc_llm_enabled``.
"""

from __future__ import annotations

from typing import Any

from app.config import settings

INSTRUCT_PROVIDER_ID = "foundation_sec_instruct"
REASONING_PROVIDER_ID = "foundation_sec_reasoning"
INSTRUCT_DEFAULT_MODEL = "Foundation-sec-8B-Instruct"
REASONING_DEFAULT_MODEL = "Foundation-sec-8B-Reasoning"

ROLE_DEFAULTS: tuple[dict[str, Any], ...] = (
    {
        "role": "intent_shadow_classifier",
        "preferred_provider": INSTRUCT_PROVIDER_ID,
        "preferred_model": INSTRUCT_DEFAULT_MODEL,
        "mode": "advisory",
        "output": "QueryUnderstandingCandidate JSON",
        "authority": "low",
        "validator_required": True,
        "strict_json": True,
        "temperature": 0.0,
        "max_input_tokens": 2000,
        "max_output_tokens": 800,
        "execution_eligible": False,
    },
    {
        "role": "analyst_response_drafter",
        "preferred_provider": INSTRUCT_PROVIDER_ID,
        "preferred_model": INSTRUCT_DEFAULT_MODEL,
        "mode": "constrained_generation",
        "output": "analyst_response JSON",
        "authority": "draft_only",
        "validator_required": True,
        "strict_json": True,
        "temperature": 0.0,
        "max_input_tokens": 6000,
        "max_output_tokens": 3000,
        "execution_eligible": False,
    },
    {
        "role": "investigation_note_drafter",
        "preferred_provider": INSTRUCT_PROVIDER_ID,
        "preferred_model": INSTRUCT_DEFAULT_MODEL,
        "mode": "constrained_generation",
        "output": "investigation_note JSON/text",
        "authority": "draft_only",
        "validator_required": True,
        "strict_json": True,
        "temperature": 0.0,
        "max_input_tokens": 6000,
        "max_output_tokens": 2000,
        "execution_eligible": False,
    },
    {
        "role": "pattern_reasoner",
        "preferred_provider": REASONING_PROVIDER_ID,
        "preferred_model": REASONING_DEFAULT_MODEL,
        "mode": "advisory_reasoning",
        "output": "reasoning_summary",
        "authority": "advisory",
        "validator_required": True,
        "strict_json": True,
        "temperature": 0.1,
        "max_input_tokens": 8000,
        "max_output_tokens": 2500,
        "execution_eligible": False,
    },
    {
        "role": "mitre_reasoner",
        "preferred_provider": REASONING_PROVIDER_ID,
        "preferred_model": REASONING_DEFAULT_MODEL,
        "mode": "advisory_reasoning",
        "output": "mitre_reasoning_summary",
        "authority": "advisory",
        "validator_required": True,
        "strict_json": True,
        "temperature": 0.1,
        "max_input_tokens": 8000,
        "max_output_tokens": 2500,
        "execution_eligible": False,
    },
    {
        "role": "missing_evidence_reasoner",
        "preferred_provider": REASONING_PROVIDER_ID,
        "preferred_model": REASONING_DEFAULT_MODEL,
        "mode": "advisory_reasoning",
        "output": "missing_evidence_analysis",
        "authority": "advisory",
        "validator_required": True,
        "strict_json": True,
        "temperature": 0.1,
        "max_input_tokens": 8000,
        "max_output_tokens": 2500,
        "execution_eligible": False,
    },
    {
        "role": "risk_rationale_reasoner",
        "preferred_provider": REASONING_PROVIDER_ID,
        "preferred_model": REASONING_DEFAULT_MODEL,
        "mode": "advisory_reasoning",
        "output": "why_not_higher / risk_rationale",
        "authority": "advisory",
        "validator_required": True,
        "strict_json": True,
        "temperature": 0.1,
        "max_input_tokens": 8000,
        "max_output_tokens": 2500,
        "execution_eligible": False,
    },
    {
        "role": "spl_advisory_generator",
        "preferred_provider": INSTRUCT_PROVIDER_ID,
        "preferred_model": INSTRUCT_DEFAULT_MODEL,
        "mode": "candidate_only",
        "output": "candidate_spl",
        "authority": "candidate_only",
        "validator_required": True,
        "strict_json": True,
        "temperature": 0.0,
        "max_input_tokens": 4000,
        "max_output_tokens": 1200,
        "execution_eligible": False,
    },
    {
        "role": "template_render_parameter_assist",
        "preferred_provider": INSTRUCT_PROVIDER_ID,
        "preferred_model": INSTRUCT_DEFAULT_MODEL,
        "mode": "advisory",
        "output": "template_render_extracted_parameters JSON",
        "authority": "advisory",
        "validator_required": True,
        "strict_json": True,
        "temperature": 0.0,
        "max_input_tokens": 2000,
        "max_output_tokens": 400,
        "execution_eligible": False,
    },
    {
        "role": "template_match_semantic_assist",
        "preferred_provider": INSTRUCT_PROVIDER_ID,
        "preferred_model": INSTRUCT_DEFAULT_MODEL,
        "mode": "advisory",
        "output": "template_match_semantic_hints JSON",
        "authority": "advisory",
        "validator_required": True,
        "strict_json": True,
        "temperature": 0.0,
        "max_input_tokens": 2000,
        "max_output_tokens": 400,
        "execution_eligible": False,
    },
    {
        "role": "route_plan_candidate_generator",
        "preferred_provider": INSTRUCT_PROVIDER_ID,
        "preferred_model": INSTRUCT_DEFAULT_MODEL,
        "mode": "candidate_only",
        "output": "route_plan_candidate JSON",
        "authority": "candidate_only",
        "validator_required": True,
        "strict_json": True,
        "temperature": 0.0,
        "max_input_tokens": 4000,
        "max_output_tokens": 1200,
        "execution_eligible": False,
    },
    {
        "role": "analyst_summary_narration",
        "preferred_provider": INSTRUCT_PROVIDER_ID,
        "preferred_model": INSTRUCT_DEFAULT_MODEL,
        "mode": "advisory",
        "output": "analyst_summary_narration JSON",
        "authority": "advisory",
        "validator_required": True,
        "strict_json": True,
        "temperature": 0.0,
        "max_input_tokens": 3000,
        "max_output_tokens": 600,
        "execution_eligible": False,
    },
    {
        "role": "answer_guard_assistant",
        "preferred_provider": REASONING_PROVIDER_ID,
        "preferred_model": REASONING_DEFAULT_MODEL,
        "mode": "planned",
        "output": "guard_assist",
        "authority": "advisory_only",
        "validator_required": "deterministic_guard_first",
        "strict_json": True,
        "temperature": 0.0,
        "max_input_tokens": 8000,
        "max_output_tokens": 1500,
        "execution_eligible": False,
    },
    {
        "role": "mitre_candidate_mapper",
        "preferred_provider": INSTRUCT_PROVIDER_ID,
        "preferred_model": INSTRUCT_DEFAULT_MODEL,
        "mode": "advisory",
        "output": "MitreCandidateMapperPayload JSON",
        "authority": "candidate_review_only",
        "validator_required": True,
        "strict_json": True,
        "temperature": 0.0,
        "max_input_tokens": 2000,
        "max_output_tokens": 800,
        "execution_eligible": False,
    },
)

ROLE_ENV_MAP: dict[str, tuple[str, str]] = {
    "intent_shadow_classifier": ("ai_soc_llm_intent_provider", "ai_soc_llm_intent_model"),
    "analyst_response_drafter": ("ai_soc_llm_synthesis_provider", "ai_soc_llm_synthesis_model"),
    "investigation_note_drafter": ("ai_soc_llm_synthesis_provider", "ai_soc_llm_synthesis_model"),
    "pattern_reasoner": ("ai_soc_llm_reasoning_provider", "ai_soc_llm_reasoning_model"),
    "mitre_reasoner": ("ai_soc_llm_reasoning_provider", "ai_soc_llm_reasoning_model"),
    "missing_evidence_reasoner": ("ai_soc_llm_reasoning_provider", "ai_soc_llm_reasoning_model"),
    "risk_rationale_reasoner": ("ai_soc_llm_reasoning_provider", "ai_soc_llm_reasoning_model"),
    "spl_advisory_generator": ("ai_soc_llm_spl_advisory_provider", "ai_soc_llm_spl_advisory_model"),
    "template_match_semantic_assist": (
        "ai_soc_llm_template_match_provider",
        "ai_soc_llm_template_match_model",
    ),
    "template_render_parameter_assist": (
        "ai_soc_llm_template_render_provider",
        "ai_soc_llm_template_render_model",
    ),
    "route_plan_candidate_generator": (
        "ai_soc_llm_route_plan_provider",
        "ai_soc_llm_route_plan_model",
    ),
    "analyst_summary_narration": (
        "ai_soc_llm_analyst_summary_narration_provider",
        "ai_soc_llm_analyst_summary_narration_model",
    ),
    "answer_guard_assistant": ("ai_soc_llm_guard_provider", "ai_soc_llm_guard_model"),
    "mitre_candidate_mapper": (
        "ai_soc_llm_mitre_candidate_provider",
        "ai_soc_llm_mitre_candidate_model",
    ),
}


def _configured(value: str) -> bool:
    return bool(value and value.strip())


def _provider_entry(
    provider_id: str,
    provider_type: str,
    base_url: str,
    api_key: str,
    model: str,
    *,
    deployment_mode: str,
    max_context_tokens: int,
    max_output_tokens: int,
    supports_json_mode: bool,
    supports_model_listing: bool,
) -> dict[str, Any]:
    base_url_configured = _configured(base_url)
    policy_allowed = deployment_mode != "cloud" or (settings.ai_soc_llm_allow_cloud and not settings.ai_soc_llm_airgap_enforced)
    return {
        "provider_id": provider_id,
        "provider_type": provider_type,
        "base_url_configured": base_url_configured,
        "api_key_configured": _configured(api_key),
        "default_model_configured": _configured(model),
        "model_name": model.strip() or None,
        "max_context_tokens": max_context_tokens,
        "max_output_tokens": max_output_tokens,
        "timeout_seconds": settings.ai_soc_llm_timeout_seconds,
        "temperature": settings.ai_soc_llm_temperature,
        "top_p": 1.0,
        "supports_json_mode": supports_json_mode,
        "supports_model_listing": supports_model_listing,
        "deployment_mode": deployment_mode,
        "policy_allowed": policy_allowed,
        # A governed provider is considered enabled once its endpoint is
        # configured. There is no per-provider toggle env in this stage.
        "enabled": base_url_configured and policy_allowed,
    }


def _configured_provider_ids(providers: list[dict[str, Any]]) -> set[str]:
    return {provider["provider_id"] for provider in providers if provider["enabled"]}


def _configured_model(provider_id: str, providers: list[dict[str, Any]]) -> str | None:
    for provider in providers:
        if provider["provider_id"] == provider_id:
            return provider.get("model_name")
    return None


def _role_entry(role_spec: dict[str, Any], providers: list[dict[str, Any]]) -> dict[str, Any]:
    provider_attr, model_attr = ROLE_ENV_MAP[role_spec["role"]]
    configured_provider = str(getattr(settings, provider_attr)).strip()
    configured_model = str(getattr(settings, model_attr)).strip()
    preferred_provider = role_spec["preferred_provider"]
    provider_ids = _configured_provider_ids(providers)
    fallback_provider = settings.ai_soc_llm_default_provider.strip() or None

    resolved_provider = configured_provider or (preferred_provider if preferred_provider in provider_ids else fallback_provider)
    resolved_model = configured_model or _configured_model(resolved_provider, providers) if resolved_provider else configured_model
    fallback_used = bool(resolved_provider and resolved_provider != preferred_provider)
    return {
        **role_spec,
        "provider": resolved_provider or None,
        "model": resolved_model or role_spec["preferred_model"],
        "enabled": bool(resolved_provider),
        "fallback_used": fallback_used,
        "degraded_role_separation": fallback_used or (resolved_provider is not None and preferred_provider not in provider_ids),
    }


def _role_suitability(providers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    provider_ids = _configured_provider_ids(providers)
    return [
        {
            "provider_id": INSTRUCT_PROVIDER_ID,
            "model_family": INSTRUCT_DEFAULT_MODEL,
            "checks": {
                "connectivity": "untested" if INSTRUCT_PROVIDER_ID not in provider_ids else "suitable_with_guard",
                "json_compliance": "suitable_with_guard",
                "intent_shadow_classifier": "suitable_with_guard",
                "analyst_response_drafter": "suitable_with_guard",
                "investigation_note_drafter": "suitable_with_guard",
                "reasoning_output_format": "not_recommended",
                "spl_advisory_generator": "candidate_only",
                "spl_advisory_recommendation": "not_recommended",
                "template_match_semantic_assist": "suitable_with_guard",
                "template_render_parameter_assist": "suitable_with_guard",
                "route_plan_candidate_generator": "candidate_only",
                "analyst_summary_narration": "suitable_with_guard",
                "final_answer_without_guard": "not_allowed",
            },
        },
        {
            "provider_id": REASONING_PROVIDER_ID,
            "model_family": REASONING_DEFAULT_MODEL,
            "checks": {
                "connectivity": "untested" if REASONING_PROVIDER_ID not in provider_ids else "suitable_with_guard",
                "json_compliance": "suitable_with_guard",
                "pattern_reasoner": "suitable_with_guard",
                "mitre_reasoner": "suitable_with_guard",
                "missing_evidence_reasoner": "suitable_with_guard",
                "risk_rationale_reasoner": "suitable_with_guard",
                "analyst_response_drafter": "optional_not_primary",
                "spl_advisory_generator": "candidate_only",
                "spl_advisory_recommendation": "not_recommended",
                "final_answer_without_guard": "not_allowed",
            },
        },
    ]


def build_llm_governance_status() -> dict[str, Any]:
    """Return the governed LLM readiness block. Secrets are never included."""
    mode = settings.ai_soc_llm_mode.strip().lower()
    llm_enabled = settings.ai_soc_llm_enabled and mode != "disabled"
    # Airgap enforcement always wins over a cloud allowance; resolve safely
    # rather than raising so a misconfiguration cannot open a cloud path.
    cloud_allowed = settings.ai_soc_llm_allow_cloud and not settings.ai_soc_llm_airgap_enforced

    warnings: list[str] = []
    if settings.ai_soc_llm_allow_cloud and settings.ai_soc_llm_airgap_enforced:
        warnings.append("cloud_allowance_overridden_by_airgap_enforcement")
    providers = [
        _provider_entry(
            "openai_compatible",
            "openai_compatible",
            settings.ai_soc_llm_openai_base_url,
            settings.ai_soc_llm_openai_api_key,
            settings.ai_soc_llm_openai_model,
            deployment_mode="cloud",
            max_context_tokens=settings.ai_soc_llm_max_input_tokens,
            max_output_tokens=settings.ai_soc_llm_max_output_tokens,
            supports_json_mode=True,
            supports_model_listing=True,
        ),
        _provider_entry(
            INSTRUCT_PROVIDER_ID,
            "cisco_foundation_sec",
            settings.ai_soc_llm_foundation_sec_instruct_base_url,
            settings.ai_soc_llm_foundation_sec_instruct_api_key,
            settings.ai_soc_llm_foundation_sec_instruct_model,
            deployment_mode="private_gateway",
            max_context_tokens=settings.ai_soc_llm_max_input_tokens,
            max_output_tokens=settings.ai_soc_llm_max_output_tokens,
            supports_json_mode=False,
            supports_model_listing=False,
        ),
        _provider_entry(
            REASONING_PROVIDER_ID,
            "cisco_foundation_sec",
            settings.ai_soc_llm_foundation_sec_reasoning_base_url,
            settings.ai_soc_llm_foundation_sec_reasoning_api_key,
            settings.ai_soc_llm_foundation_sec_reasoning_model,
            deployment_mode="private_gateway",
            max_context_tokens=settings.ai_soc_llm_max_input_tokens,
            max_output_tokens=settings.ai_soc_llm_max_output_tokens,
            supports_json_mode=False,
            supports_model_listing=False,
        ),
        _provider_entry(
            "local",
            "local",
            settings.ai_soc_llm_local_base_url,
            settings.ai_soc_llm_local_api_key,
            settings.ai_soc_llm_local_model,
            deployment_mode="local",
            max_context_tokens=settings.ai_soc_llm_max_input_tokens,
            max_output_tokens=settings.ai_soc_llm_max_output_tokens,
            supports_json_mode=False,
            supports_model_listing=False,
        ),
    ]
    role_mappings = [_role_entry(role_spec, providers) for role_spec in ROLE_DEFAULTS]
    configured_foundation_models = {
        provider["provider_id"]
        for provider in providers
        if provider["provider_id"] in {INSTRUCT_PROVIDER_ID, REASONING_PROVIDER_ID} and provider["enabled"]
    }
    if configured_foundation_models and configured_foundation_models != {INSTRUCT_PROVIDER_ID, REASONING_PROVIDER_ID}:
        warnings.append("foundation_sec_role_separation_degraded_single_model_configured")

    return {
        "llm_enabled": llm_enabled,
        "llm_mode": mode,
        "cloud_allowed": cloud_allowed,
        "cloud_requested": settings.ai_soc_llm_allow_cloud,
        "airgap_enforced": settings.ai_soc_llm_airgap_enforced,
        "default_provider": settings.ai_soc_llm_default_provider.strip() or None,
        "default_model": settings.ai_soc_llm_default_model.strip() or None,
        "final_synthesis_enabled": settings.ai_soc_llm_final_synthesis_enabled,
        "answer_guard_enabled": settings.ai_soc_llm_answer_guard_enabled,
        "context_sufficiency_required": settings.ai_soc_llm_require_context_sufficiency,
        "limits": {
            "timeout_seconds": settings.ai_soc_llm_timeout_seconds,
            "max_input_tokens": settings.ai_soc_llm_max_input_tokens,
            "max_output_tokens": settings.ai_soc_llm_max_output_tokens,
            "temperature": settings.ai_soc_llm_temperature,
            "streaming": settings.ai_soc_llm_streaming,
        },
        "safety": {
            "log_prompts": settings.ai_soc_llm_log_prompts,
            "log_responses": settings.ai_soc_llm_log_responses,
            "redact_secrets": settings.ai_soc_llm_redact_secrets,
            "require_source_refs": settings.ai_soc_llm_require_source_refs,
            "allow_insufficient_evidence_response": settings.ai_soc_llm_allow_insufficient_evidence_response,
        },
        "providers": providers,
        "role_mappings": role_mappings,
        "role_suitability": _role_suitability(providers),
        "authority_note": "Foundation-sec outputs are advisory until validated by deterministic policy and Answer Guard.",
        "deterministic_authorities": [
            "use_case_id",
            "selected_skill",
            "spl_template_selection",
            "spl_validation",
            "mcp_execution_eligibility",
            "severity_label",
            "mitre_mapping_status",
            "sop_citation_source_refs",
            "allowed_actions",
            "blocked_actions",
            "context_sufficiency",
            "answer_guard_result",
        ],
        "warnings": warnings,
        "notes": [
            "Read-only governed LLM readiness. No real LLM is called in this stage.",
            "P6 lab: deterministic synthesis draft and Answer Guard run only when flags are enabled (default off); no live LLM synthesis.",
            "Foundation-sec role mappings are advisory/config-planning only until Stage 3K explicitly wires synthesis.",
            "Foundation-sec outputs are advisory until validated by deterministic policy and Answer Guard.",
            "Endpoint URLs and API keys are never returned, only configured booleans.",
        ],
    }
