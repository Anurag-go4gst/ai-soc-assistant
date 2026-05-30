"""Stage 3M-S4: Demo Foundation-Sec / HF shadow provider (lineage only)."""

from __future__ import annotations

import pytest

from app.api.routes_scenarios import run_demo_scenario_fixture
from app.config import settings
from app.demo.llm_shadow_provider import (
    DROP_EXECUTION_CLAIM,
    DROP_RAW_SPL,
    DROP_REMEDIATION_ACTION,
    DROP_UNSUPPORTED_MITRE,
    DemoLlmShadowContext,
    FakeDemoLlmShadowProvider,
    govern_demo_llm_shadow,
    run_demo_llm_shadow,
)
from app.demo.scenarios import run_demo_scenario


def test_default_disabled_makes_no_shadow_output() -> None:
    assert settings.demo_llm_shadow_enabled is False
    payload = run_demo_scenario("failed_login_spike_app01")
    stages = payload["investigation_lineage"]["stages"]
    assert not any(stage["stage_id"] == "demo_foundation_sec_shadow" for stage in stages)


def test_fake_provider_adds_lineage_without_changing_analyst_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "demo_llm_shadow_enabled", True)
    monkeypatch.setattr(settings, "demo_llm_shadow_provider", "fake")

    before = run_demo_scenario_fixture("failed_login_spike_app01")
    after = run_demo_scenario_fixture("failed_login_spike_app01")

    assert before.selected_skill == after.selected_skill == "attack_discovery"
    assert before.message == after.message
    assert before.analyst_summary == after.analyst_summary
    assert before.route_plan_shadow is None
    assert after.route_plan_shadow is None

    shadow_stage = next(
        stage
        for stage in after.investigation_lineage.stages
        if stage.stage_id == "demo_foundation_sec_shadow"
    )
    assert shadow_stage.technical_output["called"] is True
    assert shadow_stage.technical_output["provider"] == "fake"
    assert shadow_stage.technical_output["deterministic_wins"] is True
    assert shadow_stage.technical_output["raw_model_route_proposal"] is not None


def test_deterministic_skill_remains_authoritative(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "demo_llm_shadow_enabled", True)
    monkeypatch.setattr(settings, "demo_llm_shadow_provider", "fake")
    response = run_demo_scenario_fixture("failed_login_spike_app01")
    assert response.selected_skill == "attack_discovery"


def test_raw_spl_in_model_output_is_dropped() -> None:
    raw = FakeDemoLlmShadowProvider(fixture_key="bad_spl").generate(
        DemoLlmShadowContext(
            scenario_id="test",
            query="q",
            selected_skill="attack_discovery",
        )
    )
    _route, narration, dropped = govern_demo_llm_shadow(
        raw,
        DemoLlmShadowContext(scenario_id="test", query="q", selected_skill="attack_discovery"),
    )
    assert DROP_RAW_SPL in dropped
    assert narration is None


def test_execution_claim_in_model_output_is_dropped() -> None:
    raw = FakeDemoLlmShadowProvider(fixture_key="bad_execution").generate(
        DemoLlmShadowContext(scenario_id="test", query="q", selected_skill="attack_discovery")
    )
    _route, narration, dropped = govern_demo_llm_shadow(
        raw,
        DemoLlmShadowContext(scenario_id="test", query="q", selected_skill="attack_discovery"),
    )
    assert DROP_EXECUTION_CLAIM in dropped


def test_remediation_action_in_model_output_is_dropped() -> None:
    raw = FakeDemoLlmShadowProvider(fixture_key="bad_remediation").generate(
        DemoLlmShadowContext(scenario_id="test", query="q", selected_skill="attack_discovery")
    )
    _route, _narration, dropped = govern_demo_llm_shadow(
        raw,
        DemoLlmShadowContext(scenario_id="test", query="q", selected_skill="attack_discovery"),
    )
    assert DROP_REMEDIATION_ACTION in dropped


def test_unsupported_mitre_is_dropped_when_governed_context_provided() -> None:
    raw = FakeDemoLlmShadowProvider(fixture_key="bad_mitre").generate(
        DemoLlmShadowContext(scenario_id="test", query="q", selected_skill="attack_discovery")
    )
    _route, _narration, dropped = govern_demo_llm_shadow(
        raw,
        DemoLlmShadowContext(
            scenario_id="test",
            query="q",
            selected_skill="attack_discovery",
            governed_mitre_ids=("T1110.001",),
        ),
    )
    assert DROP_UNSUPPORTED_MITRE in dropped


def test_huggingface_provider_not_used_in_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "demo_llm_shadow_enabled", True)
    monkeypatch.setattr(settings, "demo_llm_shadow_provider", "huggingface")
    result = run_demo_llm_shadow(
        DemoLlmShadowContext(scenario_id="x", query="q", selected_skill="attack_discovery"),
    )
    assert result is not None
    assert result.called is False
    assert result.provider == "huggingface"


def test_run_demo_llm_shadow_never_imports_chat_or_mcp_execution() -> None:
    import inspect

    import app.demo.llm_shadow_provider as module

    source = inspect.getsource(module)
    assert "routes_chat" not in source
    assert "mcp_execution_gate" not in source
    assert "get_mcp_connector" not in source
