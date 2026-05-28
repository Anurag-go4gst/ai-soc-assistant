"""Stage 3K-Q1D template renderer LLM-assist sidecar tests (stub adapter only)."""

from __future__ import annotations

import json
import time

import pytest

from app.config import settings
from app.llm.registry_settings import REASONING_PROVIDER_ID
from app.spl.template_registry import get_spl_template
from app.spl.template_renderer import render_template
from app.spl.template_renderer_llm_assist import (
    TEMPLATE_RENDER_PARAMETER_ASSIST_ROLE,
    render_template_with_parameter_assist,
    sanitize_template_render_llm_payload,
)


def _route_window() -> dict[str, str]:
    return {"earliest": "earliest=-24h", "latest": "latest=now"}


def test_sidecar_disabled_matches_deterministic_render(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", False)
    template = get_spl_template("sample_auth_failed_login_top_users_tstats")
    assert template is not None
    baseline = render_template(template, {"result_limit": 10}, route_window=_route_window())
    result = render_template_with_parameter_assist(
        template,
        {"result_limit": 10},
        route_window=_route_window(),
        shadow_enabled=False,
    )

    def _core(dump: dict) -> dict:
        return {k: v for k, v in dump.items() if k not in {"parameter_extraction_llm", "llm_assist_enabled", "disagreements"}}

    assert _core(result.model_dump()) == _core(baseline.model_dump())


def test_route_plan_wins_on_result_limit_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "mock")

    payload = json.dumps({"extracted_parameters": {"result_limit": 99}})
    template = get_spl_template("sample_auth_failed_login_top_users_tstats")
    assert template is not None
    result = render_template_with_parameter_assist(
        template,
        {"result_limit": 10},
        route_window=_route_window(),
        llm_raw_output_provider=lambda: payload,
    )

    assert result.render_ok is True
    assert result.bound_parameters["result_limit"] == 10
    assert any(item["field"] == "result_limit" for item in result.disagreements)


def test_spl_fragment_stripped_from_extraction() -> None:
    payload = json.dumps(
        {
            "extracted_parameters": {
                "host": "search index=secret | stats count",
            }
        }
    )
    template = get_spl_template("sample_network_top_outbound_src_tstats")
    sanitized, notes = sanitize_template_render_llm_payload(payload, template=template)

    assert sanitized is None or "host" not in (sanitized.get("extracted_parameters") or {})
    assert "spl_in_extraction_forbidden" in notes


def test_invalid_ip_dropped() -> None:
    payload = json.dumps({"extracted_parameters": {"src_ip": "not-an-ip"}})
    template = get_spl_template("sample_network_top_outbound_src_tstats")
    sanitized, notes = sanitize_template_render_llm_payload(payload, template=template)

    extracted = (sanitized or {}).get("extracted_parameters") or {}
    assert "src_ip" not in extracted
    assert any("invalid_ip" in note for note in notes)


def test_template_id_stripped() -> None:
    payload = json.dumps(
        {
            "template_id": "sample_auth_failed_login_top_users_tstats",
            "extracted_parameters": {"result_limit": 25},
        }
    )
    template = get_spl_template("sample_auth_failed_login_top_users_tstats")
    sanitized, notes = sanitize_template_render_llm_payload(payload, template=template)

    assert sanitized is not None
    assert "template_id" not in sanitized
    assert any("forbidden" in note or "dropped_field" in note for note in notes)


def test_result_limit_above_policy_dropped() -> None:
    payload = json.dumps({"extracted_parameters": {"result_limit": 9999}})
    template = get_spl_template("sample_auth_failed_login_top_users_tstats")
    sanitized, notes = sanitize_template_render_llm_payload(payload, template=template)

    extracted = (sanitized or {}).get("extracted_parameters") or {}
    assert "result_limit" not in extracted
    assert "result_limit_exceeds_policy" in notes


def test_reasoning_model_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "mock")
    monkeypatch.setattr(settings, "ai_soc_llm_template_render_provider", REASONING_PROVIDER_ID)
    monkeypatch.setattr(settings, "ai_soc_llm_template_render_model", "Foundation-sec-8B-Reasoning")

    template = get_spl_template("sample_auth_failed_login_top_users_tstats")
    assert template is not None
    result = render_template_with_parameter_assist(
        template,
        {},
        route_window=_route_window(),
        llm_raw_output_provider=lambda: json.dumps({"extracted_parameters": {"result_limit": 25}}),
    )

    assert result.parameter_extraction_llm is not None
    assert result.parameter_extraction_llm.get("rejected_reason") == "reasoning_model_not_allowed_for_rendering"


def test_sidecar_timeout_proceeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "mock")

    def slow() -> str:
        time.sleep(2.0)
        return json.dumps({"extracted_parameters": {"result_limit": 25}})

    template = get_spl_template("sample_auth_failed_login_top_users_tstats")
    assert template is not None
    result = render_template_with_parameter_assist(
        template,
        {},
        route_window=_route_window(),
        llm_raw_output_provider=slow,
    )

    assert result.llm_assist_timed_out is True
    assert result.render_ok is True


def test_render_still_passes_validator_with_sidecar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "mock")

    payload = json.dumps(
        {
            "extracted_parameters": {
                "result_limit": 25,
                "time_window": {"earliest": "earliest=-1h", "latest": "latest=now"},
            }
        }
    )
    template = get_spl_template("sample_auth_failed_login_top_users_tstats")
    assert template is not None
    result = render_template_with_parameter_assist(
        template,
        {"result_limit": 10},
        route_window=_route_window(),
        llm_raw_output_provider=lambda: payload,
    )

    assert result.validator_approved is True
    assert result.execution_eligible is False


def test_adapter_role_registered() -> None:
    from app.llm.adapter.role_registry import schema_for_role

    schema = schema_for_role(TEMPLATE_RENDER_PARAMETER_ASSIST_ROLE)
    assert schema.__name__ == "TemplateRenderParameterAssistPayload"
