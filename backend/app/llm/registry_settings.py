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


def _configured(value: str) -> bool:
    return bool(value and value.strip())


def _provider_entry(provider_id: str, provider_type: str, base_url: str, api_key: str, model: str) -> dict[str, Any]:
    base_url_configured = _configured(base_url)
    return {
        "provider_id": provider_id,
        "provider_type": provider_type,
        "base_url_configured": base_url_configured,
        "api_key_configured": _configured(api_key),
        "default_model_configured": _configured(model),
        # A governed provider is considered enabled once its endpoint is
        # configured. There is no per-provider toggle env in this stage.
        "enabled": base_url_configured,
    }


def _role_entry(role: str, provider: str, model: str) -> dict[str, Any]:
    return {
        "role": role,
        "provider": provider.strip() or None,
        "model": model.strip() or None,
        "enabled": _configured(provider),
    }


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
        "providers": [
            _provider_entry(
                "openai_compatible",
                "openai_compatible",
                settings.ai_soc_llm_openai_base_url,
                settings.ai_soc_llm_openai_api_key,
                settings.ai_soc_llm_openai_model,
            ),
            _provider_entry(
                "foundation_sec_instruct",
                "cisco_foundation_sec",
                settings.ai_soc_llm_foundation_sec_instruct_base_url,
                settings.ai_soc_llm_foundation_sec_instruct_api_key,
                settings.ai_soc_llm_foundation_sec_instruct_model,
            ),
            _provider_entry(
                "foundation_sec_reasoning",
                "cisco_foundation_sec",
                settings.ai_soc_llm_foundation_sec_reasoning_base_url,
                settings.ai_soc_llm_foundation_sec_reasoning_api_key,
                settings.ai_soc_llm_foundation_sec_reasoning_model,
            ),
            _provider_entry(
                "local",
                "local",
                settings.ai_soc_llm_local_base_url,
                settings.ai_soc_llm_local_api_key,
                settings.ai_soc_llm_local_model,
            ),
        ],
        "role_mappings": [
            _role_entry("synthesis", settings.ai_soc_llm_role_synthesis_provider, settings.ai_soc_llm_role_synthesis_model),
            _role_entry("reasoning", settings.ai_soc_llm_role_reasoning_provider, settings.ai_soc_llm_role_reasoning_model),
            _role_entry("router", settings.ai_soc_llm_role_router_provider, settings.ai_soc_llm_role_router_model),
        ],
        "warnings": warnings,
        "notes": [
            "Read-only governed LLM readiness. No real LLM is called in this stage.",
            "Final synthesis and answer guard are not implemented; flags are inert.",
            "Endpoint URLs and API keys are never returned, only configured booleans.",
        ],
    }
