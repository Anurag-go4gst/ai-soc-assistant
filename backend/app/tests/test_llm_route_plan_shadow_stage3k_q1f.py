"""Stage 3K-Q1F LLM route-plan shadow tests (stub LLM only)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from app.api.routes_chat import chat
from app.config import settings
from app.llm.registry_settings import (
    INSTRUCT_DEFAULT_MODEL,
    INSTRUCT_PROVIDER_ID,
    REASONING_DEFAULT_MODEL,
    REASONING_PROVIDER_ID,
    build_llm_governance_status,
)
from app.llm.sidecar_governance import REASONING_REJECTION_ROUTING
from app.routing.llm_route_plan_candidate import (
    DROP_SCHEMA_INVALID,
    DROP_SPL_IN_CANDIDATE,
    DROP_UNKNOWN_DATAMODEL,
    expand_route_plan_candidate_payload,
    generate_llm_route_plan_candidate,
)
from app.routing.llm_route_plan_json import extract_route_plan_candidate_json
from app.routing.route_plan_models import ROUTE_PLAN_GENERATOR_ROLE
from app.routing.route_plan_preflight import preflight_route_plan
from app.schemas.requests import ChatRequest
from app.tests.support.chat_visible import assert_governed_spl_review_posture
from app.tests.test_route_plan_stage3k_r2 import (
    _patch_common_chat_dependencies,
    _valid_route_plan_candidate,
)


def _minimal_llm_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "primary_skill": "aggregate_and_rank",
        "operation_type": "top_n",
        "source_class": "okta_authentication_logs",
        "evidence_needs": {
            "datamodel": "Authentication",
            "group_by": ["user"],
            "metric": {"type": "count", "field": "failed_login_count"},
        },
        "time_window": None,
        "limit": 10,
        "clarification_questions": [],
        "rationale": "Top failed logins by user.",
    }
    payload.update(overrides)
    return payload


def _enable_route_plan_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "mock")
    monkeypatch.setattr(settings, "ai_soc_llm_route_plan_provider", INSTRUCT_PROVIDER_ID)
    monkeypatch.setattr(settings, "ai_soc_llm_route_plan_model", INSTRUCT_DEFAULT_MODEL)


def test_llm_disabled_skips_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "disabled")
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", True)

    result = generate_llm_route_plan_candidate(
        "Top failed logins",
        preflight=preflight_route_plan("Top failed logins"),
        llm_raw_output_provider=lambda: json.dumps(_minimal_llm_payload()),
    )

    assert result.llm_called is False
    assert result.llm_candidate_route_plan_available is False


def test_valid_candidate_passes_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_route_plan_llm(monkeypatch)
    payload = _minimal_llm_payload()
    result = generate_llm_route_plan_candidate(
        "Top failed logins",
        preflight=preflight_route_plan("Top failed logins"),
        llm_raw_output_provider=lambda: json.dumps(payload),
    )

    assert result.llm_called is True
    assert result.llm_candidate_route_plan_available is True
    assert result.validation is not None
    assert result.validation.is_valid is True


def test_schema_invalid_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_route_plan_llm(monkeypatch)
    result = generate_llm_route_plan_candidate(
        "query",
        preflight=preflight_route_plan("query"),
        llm_raw_output_provider=lambda: json.dumps({"primary_skill": "aggregate_and_rank"}),
    )

    assert result.llm_called is True
    assert DROP_SCHEMA_INVALID in result.llm_candidate_dropped_reasons


def test_markdown_fence_extraction_then_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_route_plan_llm(monkeypatch)
    payload = _minimal_llm_payload()
    raw = f"```json\n{json.dumps(payload)}\n```"
    result = generate_llm_route_plan_candidate(
        "query",
        preflight=preflight_route_plan("query"),
        llm_raw_output_provider=lambda: raw,
    )

    assert result.llm_candidate_route_plan_available is True
    assert "json_extracted_from_markdown_fence" in result.extraction_warnings


def test_unknown_datamodel_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_route_plan_llm(monkeypatch)
    payload = _minimal_llm_payload(
        evidence_needs={
            "datamodel": "NotARealModel",
            "group_by": ["user"],
            "metric": {"type": "count", "field": "failed_login_count"},
        }
    )
    result = generate_llm_route_plan_candidate(
        "query",
        preflight=preflight_route_plan("query"),
        llm_raw_output_provider=lambda: json.dumps(payload),
    )

    assert DROP_UNKNOWN_DATAMODEL in result.llm_candidate_dropped_reasons


def test_detection_ref_stripped_by_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_route_plan_llm(monkeypatch)
    payload = _minimal_llm_payload()
    payload["evidence_needs"]["detection_ref"] = "evil_detection"
    result = generate_llm_route_plan_candidate(
        "query",
        preflight=preflight_route_plan("query"),
        llm_raw_output_provider=lambda: json.dumps(payload),
    )

    assert result.llm_candidate_route_plan_available is True
    assert any("detection_ref" in note for note in result.adapter_warnings)


def test_spl_in_candidate_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_route_plan_llm(monkeypatch)
    payload = _minimal_llm_payload(rationale="index=main | stats count by user | head 10")
    result = generate_llm_route_plan_candidate(
        "query",
        preflight=preflight_route_plan("query"),
        llm_raw_output_provider=lambda: json.dumps(payload),
    )

    assert DROP_SPL_IN_CANDIDATE in result.llm_candidate_dropped_reasons


def test_reasoning_model_rejected_for_routing_role(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_route_plan_llm(monkeypatch)

    def _governance_with_reasoning_role() -> dict[str, Any]:
        status = build_llm_governance_status()
        roles = []
        for item in status["role_mappings"]:
            if item.get("role") == ROUTE_PLAN_GENERATOR_ROLE:
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
            result = generate_llm_route_plan_candidate(
                "query",
                preflight=preflight_route_plan("query"),
                llm_raw_output_provider=lambda: json.dumps(_minimal_llm_payload()),
            )

    assert result.rejected_reason == REASONING_REJECTION_ROUTING
    assert result.llm_called is False


def test_chat_llm_shadow_candidate_does_not_change_analyst_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_route_plan_llm(monkeypatch)
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery", disable_deterministic_route_plan=True)

    payload = _minimal_llm_payload()

    def provider() -> str:
        return json.dumps(payload)

    monkeypatch.setattr(
        "app.api.routes_chat.generate_llm_route_plan_candidate",
        lambda query, **kwargs: generate_llm_route_plan_candidate(
            query,
            preflight=kwargs["preflight"],
            llm_raw_output_provider=provider,
            deterministic_primary_skill=kwargs.get("deterministic_primary_skill"),
        ),
    )

    response = chat(ChatRequest(message="Top source IPs by failed login count in the last hour."))

    assert_governed_spl_review_posture(response)
    assert response.route_plan_shadow is not None
    assert response.route_plan_shadow.llm_called is True
    assert response.route_plan_shadow.llm_candidate_route_plan_available is True
    assert response.route_plan_shadow.deterministic_route_plan_wins is True
    assert response.route_plan_shadow.execution_authorized is False
    assert response.route_plan_shadow.mcp_called is False
    assert response.route_plan_shadow.spl_executed is False


def test_chat_test_hook_still_works_when_llm_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", True)
    _patch_common_chat_dependencies(
        monkeypatch,
        skill="attack_discovery",
        disable_deterministic_route_plan=True,
    )
    monkeypatch.setattr("app.api.routes_chat._route_plan_shadow_candidate", lambda query: _valid_route_plan_candidate())

    response = chat(ChatRequest(message="Top source IPs by failed login count in the last hour."))

    assert response.route_plan_shadow is not None
    assert response.route_plan_shadow.candidate_available is True
    assert response.route_plan_shadow.candidate_reason == "test_or_mock_candidate"
    assert response.route_plan_shadow.template_match_attempted is True


def test_lineage_includes_llm_route_plan_hop(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_route_plan_llm(monkeypatch)
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery", disable_deterministic_route_plan=True)

    def provider() -> str:
        return json.dumps(_minimal_llm_payload())

    monkeypatch.setattr(
        "app.api.routes_chat.generate_llm_route_plan_candidate",
        lambda query, **kwargs: generate_llm_route_plan_candidate(
            query,
            preflight=kwargs["preflight"],
            llm_raw_output_provider=provider,
            deterministic_primary_skill=kwargs.get("deterministic_primary_skill"),
        ),
    )

    response = chat(ChatRequest(message="Top source IPs by failed login count in the last hour."))
    stage_ids = [stage.stage_id for stage in response.investigation_lineage.stages]
    assert "llm_route_plan_candidate" in stage_ids


def test_expand_preserves_evidence_needs_for_template_match() -> None:
    adapted = _minimal_llm_payload()
    plan = expand_route_plan_candidate_payload(adapted)
    assert plan["evidence_needs"]["datamodel"] == "Authentication"
    assert plan["pattern_id"] == "top_failed_okta_login_users"


def test_extract_route_plan_json_wrapper_only() -> None:
    payload = _minimal_llm_payload()
    raw = f"Notes:\n```json\n{json.dumps(payload)}\n```\nThanks."
    extraction = extract_route_plan_candidate_json(raw)
    assert extraction.parsed_ok is True
    assert extraction.payload == payload
