"""COE tracked-profile reconstruction of Plan 7/8 application authority.

T4 timeout is intentionally absent from the COE seed. The 2.0s code default is
rejected when the COE profile enables T4; the operator must supply a value in
``.env``. This test does not choose or document a COE SLO.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.chat.contracts.pipeline_dispatch import legacy_dispatch_v2_authority_enabled
from app.config import ConfigError, Settings, _validate, coe_t4_missing_explicit_timeout

_REPO = Path(__file__).resolve().parents[3]
_COE_PROFILE = _REPO / "env" / "profiles" / "coe.env.example"
_DEV_PROFILE = _REPO / "env" / "profiles" / "development.env.example"

_AUTHORITY = {
    "LANGGRAPH_ORCHESTRATION_ENABLED": "true",
    "AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED": "true",
    "AI_SOC_PIPELINE_DISPATCH_V2_ENABLED": "false",
    "AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED": "true",
    "AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED": "false",
    "MCP_MODE": "mock",
}


def _profile_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def test_coe_profile_reconstructs_approved_authority_posture() -> None:
    values = _profile_values(_COE_PROFILE)
    assert {key: values.get(key) for key in _AUTHORITY} == _AUTHORITY


def test_coe_profile_does_not_ship_a_t4_timeout_slo() -> None:
    values = _profile_values(_COE_PROFILE)
    assert "AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS" not in values


def test_coe_profile_keeps_mcp_mock_without_live_credentials() -> None:
    values = _profile_values(_COE_PROFILE)
    assert values.get("MCP_MODE") == "mock"
    assert values.get("SPLUNK_MCP_BASE_URL", "") == ""
    assert values.get("SPLUNK_MCP_TOKEN", "") == ""
    assert values.get("MCP_GLOBAL_EXECUTION_ENABLED") == "true"
    assert values.get("MCP_SERVER_MOCK_EXECUTION_ENABLED") == "true"


def test_coe_t4_on_with_code_default_timeout_fails_closed() -> None:
    with pytest.raises(ConfigError, match="explicit"):
        _validate(
            Settings(
                ai_soc_env_profile="coe",
                ai_soc_t4_semantic_understanding_enabled=True,
                ai_soc_t4_semantic_understanding_timeout_seconds=2.0,
            )
        )


def test_coe_t4_on_accepts_operator_supplied_timeout_without_claiming_slo() -> None:
    # 3.0 is a fixture so the gate can distinguish "not the 2.0 default".
    # It is not a COE SLO and must not be copied into the profile.
    validated = _validate(
        Settings(
            ai_soc_env_profile="coe",
            ai_soc_t4_semantic_understanding_enabled=True,
            ai_soc_t4_semantic_understanding_timeout_seconds=3.0,
        )
    )
    assert coe_t4_missing_explicit_timeout(validated) is False
    assert validated.ai_soc_t4_semantic_understanding_timeout_seconds == 3.0


def test_resource_plan_on_fences_v2_even_if_v2_flag_is_true(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", True)
    assert legacy_dispatch_v2_authority_enabled() is False


def test_development_profile_timeout_and_authority_unchanged() -> None:
    values = _profile_values(_DEV_PROFILE)
    assert values.get("AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED") == "true"
    assert values.get("AI_SOC_PIPELINE_DISPATCH_V2_ENABLED") == "false"
    assert values.get("AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED") == "true"
    assert values.get("AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS") == "120"
    assert values.get("MCP_MODE") == "mock"


def test_code_defaults_unchanged() -> None:
    fields = Settings.model_fields
    assert fields["ai_soc_resource_plan_execution_enabled"].default is False
    assert fields["ai_soc_pipeline_dispatch_v2_enabled"].default is False
    assert fields["ai_soc_t4_semantic_understanding_enabled"].default is False
    assert fields["ai_soc_t4_semantic_understanding_timeout_seconds"].default == 2.0
    assert fields["mcp_mode"].default == "mock"
    assert fields["mcp_global_execution_enabled"].default is False


def test_non_coe_profile_is_not_blocked_on_code_default_timeout() -> None:
    validated = _validate(
        Settings(
            ai_soc_env_profile="development",
            ai_soc_t4_semantic_understanding_enabled=True,
            ai_soc_t4_semantic_understanding_timeout_seconds=2.0,
        )
    )
    assert validated.ai_soc_env_profile == "development"
    assert coe_t4_missing_explicit_timeout(validated) is False
