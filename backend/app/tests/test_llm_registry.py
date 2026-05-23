import json

from app.connectors.llm.registry import load_llm_registry_status


def test_multiple_providers_and_roles_parse(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDERS", "foundation_sec_instruct,foundation_sec_reasoning,llama_local,kimi_local,enterprise_gateway")
    monkeypatch.setenv("LLM_DEFAULT_PROVIDER", "foundation_sec_instruct")
    monkeypatch.setenv("LLM_ROUTER_PROVIDER", "foundation_sec_instruct")
    monkeypatch.setenv("LLM_SYNTHESIS_PROVIDER", "foundation_sec_instruct")
    monkeypatch.setenv("LLM_REASONING_PROVIDER", "foundation_sec_reasoning")
    monkeypatch.setenv("LLM_TEACHER_PROVIDER", "enterprise_gateway")

    _provider(monkeypatch, "FOUNDATION_SEC_INSTRUCT", "cisco_compatible", "foundation_sec", "instruct", "foundation-sec-instruct")
    _provider(monkeypatch, "FOUNDATION_SEC_REASONING", "cisco_compatible", "foundation_sec", "reasoning", "foundation-sec-reasoning")
    _provider(monkeypatch, "LLAMA_LOCAL", "ollama", "llama", "general", "llama-local")
    _provider(monkeypatch, "KIMI_LOCAL", "openai_compatible", "kimi", "general", "kimi-local")
    _provider(monkeypatch, "ENTERPRISE_GATEWAY", "openai_compatible", "other", "teacher", "teacher-model")

    status = load_llm_registry_status()

    assert status.role_resolution["router"] == "foundation_sec_instruct"
    assert status.role_resolution["synthesis"] == "foundation_sec_instruct"
    assert status.role_resolution["reasoning"] == "foundation_sec_reasoning"
    assert status.role_resolution["teacher"] == "enterprise_gateway"
    assert status.health_canary_enabled is False
    assert all(provider.supports_tool_calling is False for provider in status.providers)


def test_open_weight_families_parse(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDERS", "llama_local,kimi_local,qwen_local,mistral_local,deepseek_local,other_local")
    for family in ("llama", "kimi", "qwen", "mistral", "deepseek", "other"):
        env_name = f"{family.upper()}_LOCAL" if family != "other" else "OTHER_LOCAL"
        _provider(monkeypatch, env_name, "openai_compatible", family, "general", f"{family}-model")

    families = {provider.family for provider in load_llm_registry_status().providers}
    assert {"llama", "kimi", "qwen", "mistral", "deepseek", "other"} <= families


def test_unsupported_provider_type_reports_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDERS", "bad_provider")
    monkeypatch.setenv("LLM_PROVIDER_BAD_PROVIDER_ENABLED", "true")
    monkeypatch.setenv("LLM_PROVIDER_BAD_PROVIDER_TYPE", "not_real")
    monkeypatch.setenv("LLM_PROVIDER_BAD_PROVIDER_MODEL", "bad-model")

    provider = load_llm_registry_status().providers[0]

    assert provider.implemented is False
    assert provider.available is False
    assert provider.last_error == "unsupported_llm_provider_type"


def test_api_keys_are_not_exposed_and_concurrency_parses(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDERS", "enterprise_gateway")
    monkeypatch.setenv("LLM_GLOBAL_CONCURRENCY", "8")
    monkeypatch.setenv("LLM_PROVIDER_ENTERPRISE_GATEWAY_ENABLED", "true")
    monkeypatch.setenv("LLM_PROVIDER_ENTERPRISE_GATEWAY_TYPE", "openai_compatible")
    monkeypatch.setenv("LLM_PROVIDER_ENTERPRISE_GATEWAY_BASE_URL", "https://llm.example.invalid/v1")
    monkeypatch.setenv("LLM_PROVIDER_ENTERPRISE_GATEWAY_AUTH_MODE", "api_key")
    monkeypatch.setenv("LLM_PROVIDER_ENTERPRISE_GATEWAY_API_KEY", "sk-secret-value")
    monkeypatch.setenv("LLM_PROVIDER_ENTERPRISE_GATEWAY_MODEL", "gateway-model")
    monkeypatch.setenv("LLM_PROVIDER_ENTERPRISE_GATEWAY_CONCURRENCY_LIMIT", "3")
    monkeypatch.setenv("LLM_PROVIDER_ENTERPRISE_GATEWAY_SUPPORTS_TOOL_CALLING", "true")

    status = load_llm_registry_status()
    provider = status.providers[0]

    assert status.global_concurrency == 8
    assert provider.concurrency_limit == 3
    assert provider.api_key_configured is True
    assert provider.supports_tool_calling is False
    assert "sk-secret-value" not in json.dumps(status, default=lambda obj: getattr(obj, "__dict__", str(obj)))


def test_role_fallback_must_be_explicit(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDERS", "router_model,fallback_model")
    monkeypatch.setenv("LLM_ROUTER_PROVIDER", "router_model")
    monkeypatch.setenv("LLM_PROVIDER_ROUTER_MODEL_ENABLED", "true")
    monkeypatch.setenv("LLM_PROVIDER_ROUTER_MODEL_TYPE", "openai_compatible")
    monkeypatch.setenv("LLM_PROVIDER_ROUTER_MODEL_MODEL", "router")
    monkeypatch.setenv("LLM_PROVIDER_FALLBACK_MODEL_ENABLED", "true")
    monkeypatch.setenv("LLM_PROVIDER_FALLBACK_MODEL_TYPE", "mock")
    monkeypatch.setenv("LLM_PROVIDER_FALLBACK_MODEL_MODEL", "fallback")

    assert load_llm_registry_status().role_resolution["router"] is None

    monkeypatch.setenv("LLM_PROVIDER_ROUTER_MODEL_FALLBACK_PROVIDER", "fallback_model")
    assert load_llm_registry_status().role_resolution["router"] == "fallback_model"


def _provider(monkeypatch, env_name: str, provider_type: str, family: str, role: str, model: str) -> None:
    prefix = f"LLM_PROVIDER_{env_name}_"
    monkeypatch.setenv(prefix + "ENABLED", "true")
    monkeypatch.setenv(prefix + "TYPE", provider_type)
    monkeypatch.setenv(prefix + "BASE_URL", f"https://{env_name.lower().replace('_', '-')}.example.invalid/v1")
    monkeypatch.setenv(prefix + "AUTH_MODE", "api_key")
    monkeypatch.setenv(prefix + "API_KEY", f"{env_name.lower()}-secret")
    monkeypatch.setenv(prefix + "MODEL", model)
    monkeypatch.setenv(prefix + "MODEL_ROLE", role)
    monkeypatch.setenv(prefix + "FAMILY", family)
    monkeypatch.setenv(prefix + "CONTEXT_TOKENS", "32768")
    monkeypatch.setenv(prefix + "MAX_OUTPUT_TOKENS", "4096")

