"""Plan 7 tracked development-profile reconstruction contract."""

from __future__ import annotations

from pathlib import Path

from app.config import Settings

_REPO = Path(__file__).resolve().parents[3]
_PROFILE = _REPO / "env" / "profiles" / "development.env.example"

_TARGET = {
    "LANGGRAPH_ORCHESTRATION_ENABLED": "true",
    "AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED": "true",
    "AI_SOC_PIPELINE_DISPATCH_V2_ENABLED": "false",
    "AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED": "true",
    "AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS": "120",
    "AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED": "false",
}


def _profile_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in _PROFILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def test_development_profile_reconstructs_plan7_target_authority() -> None:
    values = _profile_values()
    assert {key: values.get(key) for key in _TARGET} == _TARGET


def test_profile_alignment_does_not_change_global_code_defaults() -> None:
    fields = Settings.model_fields
    assert fields["ai_soc_resource_plan_execution_enabled"].default is False
    assert fields["ai_soc_pipeline_dispatch_v2_enabled"].default is False
    assert fields["ai_soc_t4_semantic_understanding_enabled"].default is False
    assert fields["ai_soc_t4_semantic_understanding_timeout_seconds"].default == 2.0
    assert fields["ai_soc_live_capability_enforcement_enabled"].default is False
