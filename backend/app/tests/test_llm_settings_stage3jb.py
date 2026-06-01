from __future__ import annotations

import json

import pytest

from app.api.routes_settings import (
    LlmProviderDraft,
    LlmRoleMappingDraft,
    LlmSettingsDraftCheckRequest,
    check_llm_settings_draft,
)
from app.config import ConfigError, Settings, _validate, settings
from app.llm.registry_settings import build_llm_governance_status


def _fresh_settings(**overrides: object) -> Settings:
    # _env_file=None keeps the test hermetic from a developer's local .env.
    return Settings(_env_file=None, **overrides)


def test_governance_block_present_in_status() -> None:
    block = build_llm_governance_status()
    for key in (
        "llm_enabled",
        "llm_mode",
        "cloud_allowed",
        "airgap_enforced",
        "default_provider",
        "default_model",
        "final_synthesis_enabled",
        "answer_guard_enabled",
        "context_sufficiency_required",
        "providers",
        "role_mappings",
        "role_suitability",
        "deterministic_authorities",
        "safety",
    ):
        assert key in block


def test_mode_enum_accepts_valid_modes() -> None:
    for mode in ("mock", "local", "openai_compatible", "cisco_foundation_sec", "disabled"):
        validated = _validate(_fresh_settings(ai_soc_llm_mode=mode))
        assert validated.ai_soc_llm_mode == mode


def test_mode_enum_rejects_invalid_mode() -> None:
    with pytest.raises(ConfigError):
        _validate(_fresh_settings(ai_soc_llm_mode="gpt_supreme"))


def test_airgap_overrides_cloud_allowance_safely(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_allow_cloud", True)
    monkeypatch.setattr(settings, "ai_soc_llm_airgap_enforced", True)
    block = build_llm_governance_status()
    assert block["cloud_allowed"] is False
    assert block["cloud_requested"] is True
    assert "cloud_allowance_overridden_by_airgap_enforcement" in block["warnings"]


def test_final_synthesis_defaults_false() -> None:
    assert _fresh_settings().ai_soc_llm_final_synthesis_enabled is False
    assert build_llm_governance_status()["final_synthesis_enabled"] is False


def test_answer_guard_defaults_false() -> None:
    assert _fresh_settings().ai_soc_llm_answer_guard_enabled is False
    assert build_llm_governance_status()["answer_guard_enabled"] is False


def test_foundation_sec_role_strategy_is_read_only_and_guarded() -> None:
    block = build_llm_governance_status()
    roles = {role["role"]: role for role in block["role_mappings"]}
    assert roles["intent_shadow_classifier"]["preferred_provider"] == "foundation_sec_instruct"
    assert roles["pattern_reasoner"]["preferred_provider"] == "foundation_sec_reasoning"
    assert roles["spl_advisory_generator"]["execution_eligible"] is False
    assert roles["answer_guard_assistant"]["mode"] == "planned"
    assert "severity_label" in block["deterministic_authorities"]
    assert "mcp_execution_eligibility" in block["deterministic_authorities"]


def test_context_sufficiency_required_defaults_true() -> None:
    assert _fresh_settings().ai_soc_llm_require_context_sufficiency is True
    assert build_llm_governance_status()["context_sufficiency_required"] is True


def test_disabled_mode_forces_llm_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "disabled")
    assert build_llm_governance_status()["llm_enabled"] is False


def test_api_key_fields_return_only_booleans(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_openai_base_url", "https://llm.example.invalid/v1")
    monkeypatch.setattr(settings, "ai_soc_llm_openai_api_key", "sk-super-secret-3jb-value")
    monkeypatch.setattr(settings, "ai_soc_llm_openai_model", "gpt-fake")
    block = build_llm_governance_status()
    openai = next(p for p in block["providers"] if p["provider_id"] == "openai_compatible")
    assert openai["api_key_configured"] is True
    assert openai["base_url_configured"] is True
    assert openai["default_model_configured"] is True
    assert "api_key" not in openai
    assert "sk-super-secret-3jb-value" not in json.dumps(block)


def test_governance_status_does_not_leak_secret_values(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_foundation_sec_instruct_api_key", "secret-instruct-token-3jb")
    monkeypatch.setattr(settings, "ai_soc_llm_local_api_key", "secret-local-token-3jb")
    monkeypatch.setattr(settings, "ai_soc_llm_openai_base_url", "https://user:secret-pass-3jb@llm.example.invalid/v1")
    text = json.dumps(build_llm_governance_status())
    for forbidden in ("secret-instruct-token-3jb", "secret-local-token-3jb", "secret-pass-3jb"):
        assert forbidden not in text


def test_llm_draft_check_passes_and_never_persists() -> None:
    result = check_llm_settings_draft(
        LlmSettingsDraftCheckRequest(
            mode="openai_compatible",
            providers=[LlmProviderDraft(provider_id="openai_compatible", base_url="https://llm.example.invalid/v1", api_key="sk-draft-secret", model="m")],
        )
    )
    assert result["validation_status"] == "pass"
    assert result["not_persisted"] is True
    assert result["saved"] is False
    assert result["providers"][0]["api_key_configured"] is True
    assert "sk-draft-secret" not in json.dumps(result)


def test_llm_draft_check_accepts_role_mapping_without_execution() -> None:
    result = check_llm_settings_draft(
        LlmSettingsDraftCheckRequest(
            mode="cisco_foundation_sec",
            providers=[
                LlmProviderDraft(provider_id="foundation_sec_instruct", base_url="https://foundation.example.invalid/instruct", model="Foundation-sec-8B-Instruct"),
                LlmProviderDraft(provider_id="foundation_sec_reasoning", base_url="https://foundation.example.invalid/reasoning", model="Foundation-sec-8B-Reasoning"),
            ],
            role_mappings=[
                LlmRoleMappingDraft(role="intent_shadow_classifier", provider="foundation_sec_instruct", model="Foundation-sec-8B-Instruct"),
                LlmRoleMappingDraft(role="pattern_reasoner", provider="foundation_sec_reasoning", model="Foundation-sec-8B-Reasoning"),
            ],
        )
    )
    assert result["validation_status"] == "pass"
    assert result["role_mappings"][0]["execution_eligible"] is False
    assert result["role_mappings"][1]["validator_required"] is True
    assert result["saved"] is False


def test_llm_draft_check_rejects_invalid_mode_and_limits() -> None:
    result = check_llm_settings_draft(
        LlmSettingsDraftCheckRequest(mode="gpt_supreme", timeout_seconds=0, temperature=9.0)
    )
    assert result["validation_status"] == "fail"
    assert "invalid_mode" in result["validation_errors"]
    assert "timeout_seconds_must_be_positive" in result["validation_errors"]
    assert "temperature_out_of_range" in result["validation_errors"]


def test_llm_draft_check_airgap_overrides_cloud() -> None:
    result = check_llm_settings_draft(
        LlmSettingsDraftCheckRequest(mode="mock", allow_cloud=True, airgap_enforced=True)
    )
    assert result["cloud_allowed"] is False
    assert "cloud_allowance_overridden_by_airgap_enforcement" in result["warnings"]


def test_llm_draft_check_flags_inert_synthesis_and_guard() -> None:
    result = check_llm_settings_draft(
        LlmSettingsDraftCheckRequest(mode="mock", final_synthesis_enabled=True, answer_guard_enabled=True)
    )
    assert "final_synthesis_lab_deterministic_draft_only_no_live_llm" in result["warnings"]
    assert "answer_guard_runs_on_synthesis_draft_when_synthesis_enabled" in result["warnings"]
