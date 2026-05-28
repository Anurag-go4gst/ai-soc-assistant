"""Stage 3K-Q1G analyst-summary shadow narration tests (stub LLM only)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from app.api.routes_chat import chat
from app.api.routes_scenarios import run_demo_scenario_fixture
from app.config import settings
from app.llm.registry_settings import (
    INSTRUCT_DEFAULT_MODEL,
    INSTRUCT_PROVIDER_ID,
    REASONING_DEFAULT_MODEL,
    REASONING_PROVIDER_ID,
    build_llm_governance_status,
)
from app.llm.sidecar_governance import REASONING_REJECTION_NARRATION
from app.schemas.requests import ChatRequest
from app.synthesis.analyst_summary_llm_assist import (
    ANALYST_SUMMARY_NARRATION_ROLE,
    DROP_LENGTH_EXCEEDED,
    DROP_UNSUPPORTED_CLAIM,
    apply_analyst_summary_shadow,
    build_structured_narration_input,
    narrate_analyst_summary,
)
from app.tests.test_route_plan_stage3k_r2 import _patch_common_chat_dependencies


def _valid_narration_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "summary_sentence_1": "Shadow route-plan metadata was recorded without execution.",
        "summary_sentence_2": None,
        "technical_trace_bullets": [
            "Preflight and route-plan shadow statuses are advisory only.",
            "Template match shadow uses deterministic matcher output.",
            "Rendered SPL hash may be present; SPL text is never returned here.",
        ],
    }
    payload.update(overrides)
    return payload


def _sample_route_plan_shadow() -> dict[str, Any]:
    return {
        "enabled": True,
        "mode": "dormant_shadow",
        "preflight_status": "passed",
        "route_status": "route_ready",
        "primary_skill": "aggregate_and_rank",
        "pattern_id": "top_failed_okta_login_users",
        "candidate_available": True,
        "candidate_reason": "test_or_mock_candidate",
        "missing_slots": [],
        "normalized_plan_available": True,
        "execution_authorized": False,
        "spl_executed": False,
        "mcp_called": False,
        "template_match_attempted": True,
        "template_match_shadow_status": "matched",
        "matched_template_id": "top_failed_okta_login_users",
        "rendered_spl_available": True,
        "rendered_spl_sha256": "abc123",
        "warnings": [],
    }


def _enable_narration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_shadow_narration_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "mock")
    monkeypatch.setattr(settings, "ai_soc_llm_analyst_summary_narration_provider", INSTRUCT_PROVIDER_ID)
    monkeypatch.setattr(settings, "ai_soc_llm_analyst_summary_narration_model", INSTRUCT_DEFAULT_MODEL)


def test_shadow_off_leaves_narration_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_shadow_narration_enabled", False)
    shadow = _sample_route_plan_shadow()
    apply_analyst_summary_shadow(shadow)
    assert shadow["analyst_summary_shadow_available"] is False


def test_shadow_on_valid_narration_populates_shadow(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_narration(monkeypatch)
    shadow = _sample_route_plan_shadow()
    payload = _valid_narration_payload()

    apply_analyst_summary_shadow(
        shadow,
        llm_raw_output_provider=lambda: json.dumps(payload),
    )

    assert shadow["analyst_summary_shadow_available"] is True
    assert shadow["analyst_summary_shadow_source"] == "llm_shadow"
    assert "without execution" in (shadow["analyst_summary_shadow_text"] or "")
    assert len(shadow["analyst_summary_trace_bullets"]) == 3


def test_forbidden_phrase_ready_to_run_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_narration(monkeypatch)
    payload = _valid_narration_payload(
        summary_sentence_1="The query is ready to run in Splunk immediately.",
    )
    result = narrate_analyst_summary(
        build_structured_narration_input(_sample_route_plan_shadow()),
        llm_raw_output_provider=lambda: json.dumps(payload),
    )
    assert result.accepted is False
    assert "forbidden_phrase_ready_to_run" in result.dropped_reasons


def test_length_exceeded_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_narration(monkeypatch)
    payload = _valid_narration_payload(summary_sentence_1="x" * 241)
    result = narrate_analyst_summary(
        build_structured_narration_input(_sample_route_plan_shadow()),
        llm_raw_output_provider=lambda: json.dumps(payload),
    )
    assert DROP_LENGTH_EXCEEDED in result.dropped_reasons


def test_unsupported_ip_claim_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_narration(monkeypatch)
    payload = _valid_narration_payload(
        summary_sentence_1="Attacker 1.2.3.4 was observed across authentication logs.",
    )
    result = narrate_analyst_summary(
        build_structured_narration_input(_sample_route_plan_shadow()),
        llm_raw_output_provider=lambda: json.dumps(payload),
    )
    assert DROP_UNSUPPORTED_CLAIM in result.dropped_reasons


def test_reasoning_model_rejected_for_narration_role(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_narration(monkeypatch)

    def _governance_with_reasoning_role() -> dict[str, Any]:
        status = build_llm_governance_status()
        roles = []
        for item in status["role_mappings"]:
            if item.get("role") == ANALYST_SUMMARY_NARRATION_ROLE:
                roles.append(
                    {
                        **item,
                        "provider": REASONING_PROVIDER_ID,
                        "model": REASONING_DEFAULT_MODEL,
                        "enabled": True,
                    }
                )
            else:
                roles.append(item)
        return {**status, "role_mappings": roles}

    with patch("app.llm.sidecar_governance.build_llm_governance_status", _governance_with_reasoning_role):
        result = narrate_analyst_summary(
            build_structured_narration_input(_sample_route_plan_shadow()),
            llm_raw_output_provider=lambda: json.dumps(_valid_narration_payload()),
        )

    assert REASONING_REJECTION_NARRATION in result.dropped_reasons


def test_chat_analyst_fields_unchanged_with_narration(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")
    baseline = chat(ChatRequest(message="Top source IPs by failed login count in the last hour."))

    _enable_narration(monkeypatch)
    monkeypatch.setattr(
        "app.synthesis.analyst_summary_llm_assist.apply_analyst_summary_shadow",
        lambda shadow, **kwargs: apply_analyst_summary_shadow(
            shadow,
            llm_raw_output_provider=lambda: json.dumps(_valid_narration_payload()),
        ),
    )

    with_narration = chat(ChatRequest(message="Top source IPs by failed login count in the last hour."))

    assert with_narration.message == baseline.message
    assert with_narration.note == baseline.note
    assert with_narration.selected_skill == baseline.selected_skill
    assert with_narration.analyst_response == baseline.analyst_response
    assert with_narration.route_plan_shadow is not None
    assert with_narration.route_plan_shadow.analyst_summary_shadow_available is True


def test_lineage_includes_analyst_summary_shadow_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")
    _enable_narration(monkeypatch)
    monkeypatch.setattr(
        "app.synthesis.analyst_summary_llm_assist.apply_analyst_summary_shadow",
        lambda shadow, **kwargs: apply_analyst_summary_shadow(
            shadow,
            llm_raw_output_provider=lambda: json.dumps(_valid_narration_payload()),
        ),
    )

    response = chat(ChatRequest(message="Top source IPs by failed login count in the last hour."))
    stage_ids = [stage.stage_id for stage in response.investigation_lineage.stages]
    assert "analyst_summary_shadow" in stage_ids


def test_experience_center_demo_unchanged() -> None:
    response = run_demo_scenario_fixture("failed_login_spike_app01")
    assert response.demo_mode is True
    assert response.route_plan_shadow is None
