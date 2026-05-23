from __future__ import annotations

import os
import re
from dataclasses import dataclass


SUPPORTED_PROVIDER_TYPES = {
    "mock",
    "openai_compatible",
    "ollama",
    "vllm",
    "sglang",
    "tgi",
    "llamacpp",
    "cisco_compatible",
    "custom_http",
}
SUPPORTED_AUTH_MODES = {"none", "bearer", "api_key", "basic"}
SUPPORTED_MODEL_ROLES = {"instruct", "reasoning", "embedding", "reranker", "teacher", "general"}
SUPPORTED_FAMILIES = {"foundation_sec", "llama", "kimi", "qwen", "mistral", "deepseek", "other"}


@dataclass(frozen=True)
class LlmProviderConfig:
    name: str
    enabled: bool = False
    provider_type: str = "mock"
    base_url: str = ""
    api_key: str = ""
    auth_mode: str = "none"
    model: str = ""
    model_role: str = "general"
    family: str = "other"
    context_tokens: int | None = None
    max_output_tokens: int | None = None
    supports_streaming: bool = False
    supports_json_mode: bool = False
    supports_tool_calling: bool = False
    concurrency_limit: int = 2
    health_path: str = ""
    models_path: str = ""
    chat_completions_path: str = "/chat/completions"


@dataclass(frozen=True)
class LlmProviderStatus:
    name: str
    type: str
    family: str
    model_role: str
    enabled: bool
    implemented: bool
    configured: bool
    available: bool
    model: str
    base_url_configured: bool
    api_key_configured: bool
    auth_mode: str
    context_tokens: int | None
    max_output_tokens: int | None
    supports_streaming: bool
    supports_json_mode: bool
    supports_tool_calling: bool
    concurrency_limit: int
    last_error: str | None = None


@dataclass(frozen=True)
class LlmRegistryStatus:
    providers_configured: list[str]
    default_provider: str
    router_provider: str
    synthesis_provider: str
    reasoning_provider: str
    teacher_provider: str
    global_concurrency: int
    concurrency_per_provider: int
    timeout_seconds: int
    health_canary_enabled: bool
    providers: list[LlmProviderStatus]
    role_resolution: dict[str, str | None]

    @property
    def configured(self) -> bool:
        return any(provider.configured for provider in self.providers)

    @property
    def available(self) -> bool:
        return any(provider.available for provider in self.providers)

    @property
    def implemented(self) -> bool:
        return all(provider.implemented for provider in self.providers)


def load_llm_registry_status() -> LlmRegistryStatus:
    provider_names = _csv_env("LLM_PROVIDERS")
    if not provider_names and _env("LLM_MODE", "mock").lower() == "mock":
        provider_names = ["mock"]

    concurrency_per_provider = _int_env("LLM_CONCURRENCY_PER_PROVIDER", 2)
    status_by_name = {
        name: _status_for_provider(_load_provider_config(name, concurrency_per_provider))
        for name in provider_names
    }

    default_provider = _env("LLM_DEFAULT_PROVIDER", "mock")
    router_provider = _env("LLM_ROUTER_PROVIDER", default_provider)
    synthesis_provider = _env("LLM_SYNTHESIS_PROVIDER", default_provider)
    reasoning_provider = _env("LLM_REASONING_PROVIDER", "")
    teacher_provider = _env("LLM_TEACHER_PROVIDER", "")

    role_resolution = {
        "router": _resolve_role(router_provider, status_by_name),
        "synthesis": _resolve_role(synthesis_provider, status_by_name),
        "reasoning": _resolve_role(reasoning_provider, status_by_name),
        "teacher": _resolve_role(teacher_provider, status_by_name),
        "general": _resolve_role(default_provider, status_by_name),
    }

    return LlmRegistryStatus(
        providers_configured=provider_names,
        default_provider=default_provider,
        router_provider=router_provider,
        synthesis_provider=synthesis_provider,
        reasoning_provider=reasoning_provider,
        teacher_provider=teacher_provider,
        global_concurrency=_int_env("LLM_GLOBAL_CONCURRENCY", 4),
        concurrency_per_provider=concurrency_per_provider,
        timeout_seconds=_int_env("LLM_TIMEOUT_SECONDS", 30),
        health_canary_enabled=_bool_env("LLM_HEALTH_CANARY_ENABLED", False),
        providers=list(status_by_name.values()),
        role_resolution=role_resolution,
    )


def _load_provider_config(name: str, default_concurrency: int) -> LlmProviderConfig:
    prefix = f"LLM_PROVIDER_{_env_key(name)}_"
    is_default_mock = name == "mock" and _env("LLM_MODE", "mock").lower() == "mock"
    return LlmProviderConfig(
        name=name,
        enabled=_bool_env(prefix + "ENABLED", is_default_mock),
        provider_type=_env(prefix + "TYPE", "mock").lower(),
        base_url=_env(prefix + "BASE_URL"),
        api_key=_env(prefix + "API_KEY"),
        auth_mode=_env(prefix + "AUTH_MODE", "none").lower(),
        model=_env(prefix + "MODEL", "mock-model" if name == "mock" else ""),
        model_role=_env(prefix + "MODEL_ROLE", "general").lower(),
        family=_env(prefix + "FAMILY", "other").lower(),
        context_tokens=_optional_int_env(prefix + "CONTEXT_TOKENS"),
        max_output_tokens=_optional_int_env(prefix + "MAX_OUTPUT_TOKENS"),
        supports_streaming=_bool_env(prefix + "SUPPORTS_STREAMING", False),
        supports_json_mode=_bool_env(prefix + "SUPPORTS_JSON_MODE", False),
        supports_tool_calling=_bool_env(prefix + "SUPPORTS_TOOL_CALLING", False),
        concurrency_limit=_int_env(prefix + "CONCURRENCY_LIMIT", default_concurrency),
        health_path=_env(prefix + "HEALTH_PATH"),
        models_path=_env(prefix + "MODELS_PATH"),
        chat_completions_path=_env(prefix + "CHAT_COMPLETIONS_PATH", "/chat/completions"),
    )


def _status_for_provider(config: LlmProviderConfig) -> LlmProviderStatus:
    implemented = True
    last_error: str | None = None
    type_valid = config.provider_type in SUPPORTED_PROVIDER_TYPES
    auth_valid = config.auth_mode in SUPPORTED_AUTH_MODES
    role_valid = config.model_role in SUPPORTED_MODEL_ROLES
    family_valid = config.family in SUPPORTED_FAMILIES

    if not type_valid:
        implemented = False
        last_error = "unsupported_llm_provider_type"
    elif not auth_valid:
        implemented = False
        last_error = "unsupported_llm_auth_mode"
    elif not role_valid:
        implemented = False
        last_error = "unsupported_llm_model_role"

    family = config.family if family_valid else "other"
    base_url_required = config.provider_type != "mock"
    base_url_configured = bool(config.base_url.strip())
    auth_configured = config.auth_mode == "none" or bool(config.api_key.strip())
    model_configured = bool(config.model.strip())
    configured = bool(config.enabled and model_configured and auth_configured and implemented and (base_url_configured or not base_url_required))

    if config.enabled and not model_configured and last_error is None:
        last_error = "missing_model"
    if config.enabled and base_url_required and not base_url_configured and last_error is None:
        last_error = "missing_base_url"
    if config.enabled and not auth_configured and last_error is None:
        last_error = "missing_auth_configuration"

    return LlmProviderStatus(
        name=config.name,
        type=config.provider_type,
        family=family,
        model_role=config.model_role if role_valid else "unsupported",
        enabled=config.enabled,
        implemented=implemented,
        configured=configured,
        available=configured,
        model=config.model,
        base_url_configured=base_url_configured,
        api_key_configured=bool(config.api_key.strip()),
        auth_mode=config.auth_mode if auth_valid else "unsupported",
        context_tokens=config.context_tokens,
        max_output_tokens=config.max_output_tokens,
        supports_streaming=config.supports_streaming,
        supports_json_mode=config.supports_json_mode,
        supports_tool_calling=False,
        concurrency_limit=max(config.concurrency_limit, 1),
        last_error=last_error,
    )


def _resolve_role(provider_name: str, providers: dict[str, LlmProviderStatus]) -> str | None:
    if not provider_name:
        return None
    provider = providers.get(provider_name)
    if provider and provider.available:
        return provider.name
    fallback = _env(f"LLM_PROVIDER_{_env_key(provider_name)}_FALLBACK_PROVIDER")
    if fallback:
        fallback_provider = providers.get(fallback)
        if fallback_provider and fallback_provider.available:
            return fallback_provider.name
    return None


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _csv_env(name: str) -> list[str]:
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _optional_int_env(name: str) -> int | None:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _env_key(name: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")
