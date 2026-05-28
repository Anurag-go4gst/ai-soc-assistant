"""Stage 3K-Q1C template matcher LLM-assist sidecar tests (stub adapter only)."""

from __future__ import annotations

import json
import time

import pytest

from app.config import settings
from app.llm.registry_settings import REASONING_PROVIDER_ID
from app.spl.template_matcher import match_route_plan_to_template
from app.spl.template_matcher_llm_assist import (
    TEMPLATE_MATCH_SEMANTIC_ASSIST_ROLE,
    match_route_plan_with_semantic_assist,
    sanitize_template_match_llm_payload,
)


def _aggregate_plan(*, datamodel: str = "Authentication", group_by: str = "user") -> dict:
    return {
        "route_plan_id": "rp_q1c_assist",
        "route_status": "route_ready",
        "primary_skill": "aggregate_and_rank",
        "pattern_id": "test",
        "operation_type": "top_n",
        "domain": "soc",
        "source_class": "okta_authentication_logs",
        "entities": [group_by],
        "time_window": "last_24_hours",
        "parameters": {
            "group_by": {"field": group_by},
            "metric": {"type": "count", "field": "failed_login_count"},
            "limit": 10,
            "time_window": "last_24_hours",
        },
        "evidence_needs": {"datamodel": datamodel, "group_by": [group_by], "metric": {"type": "count"}},
        "missing_slots": [],
        "hard_preconditions": [],
        "model_advisory_metadata": {},
        "deterministic_validation": {},
        "post_enrichment": [],
    }


def test_sidecar_disabled_shadow_off_leaves_matcher_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", False)
    plan = _aggregate_plan()
    baseline = match_route_plan_to_template(plan)
    result = match_route_plan_with_semantic_assist(plan, shadow_enabled=False)

    def _core(dump: dict) -> dict:
        return {key: value for key, value in dump.items() if key not in {"disagreements", "template_match_llm_hints", "llm_assist_enabled"}}

    assert _core(result.model_dump()) == _core(baseline.model_dump())
    assert result.template_match_llm_hints is None


def test_aligned_hints_recorded_without_disagreements(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "mock")
    monkeypatch.setattr(settings, "ai_soc_llm_template_match_provider", "foundation_sec_instruct")
    monkeypatch.setattr(settings, "ai_soc_llm_template_match_model", "Foundation-sec-8B-Instruct")

    payload = json.dumps(
        {
            "llm_semantic_hints": {
                "source_class_hint": "okta_authentication_logs",
                "datamodel_hint": "Authentication",
                "field_aliases": {"failed login user": "user"},
            }
        }
    )
    plan = _aggregate_plan()
    result = match_route_plan_with_semantic_assist(
        plan,
        llm_raw_output_provider=lambda: payload,
    )

    assert result.matched is True
    assert result.disagreements == []
    assert result.llm_assist_enabled is True
    assert result.template_match_llm_hints is not None
    assert result.template_match_llm_hints["llm_semantic_hints"]["datamodel_hint"] == "Authentication"


def test_datamodel_hint_disagreement_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "mock")
    monkeypatch.setattr(settings, "ai_soc_llm_template_match_provider", "foundation_sec_instruct")

    payload = json.dumps({"llm_semantic_hints": {"datamodel_hint": "Network_Traffic"}})
    plan = _aggregate_plan(datamodel="Authentication")
    result = match_route_plan_with_semantic_assist(plan, llm_raw_output_provider=lambda: payload)

    assert result.matched is True
    assert result.matched_template_id == "sample_auth_failed_login_top_users_tstats"
    assert any(item["field"] == "datamodel" for item in result.disagreements)


def test_template_id_stripped_from_llm_output() -> None:
    payload = json.dumps(
        {
            "template_id": "sample_auth_failed_login_top_users_tstats",
            "llm_semantic_hints": {"datamodel_hint": "Authentication"},
        }
    )
    sanitized, notes = sanitize_template_match_llm_payload(payload)

    assert sanitized is not None
    assert "template_id" not in sanitized.get("llm_semantic_hints", {})
    assert any("template_id" in note for note in notes)


def test_spl_fragment_stripped_from_hints() -> None:
    payload = json.dumps(
        {
            "llm_semantic_hints": {
                "datamodel_hint": "search index=secret | stats count",
            }
        }
    )
    sanitized, notes = sanitize_template_match_llm_payload(payload)

    assert sanitized is None or "datamodel_hint" not in (sanitized.get("llm_semantic_hints") or {})
    assert "spl_in_hint_forbidden" in notes


def test_unknown_datamodel_hint_dropped() -> None:
    payload = json.dumps({"llm_semantic_hints": {"datamodel_hint": "MadeUp"}})
    sanitized, notes = sanitize_template_match_llm_payload(payload)

    hints = (sanitized or {}).get("llm_semantic_hints") or {}
    assert "datamodel_hint" not in hints
    assert "unknown_datamodel" in notes


def test_reasoning_model_rejected_for_matching_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "mock")
    monkeypatch.setattr(settings, "ai_soc_llm_template_match_provider", REASONING_PROVIDER_ID)
    monkeypatch.setattr(settings, "ai_soc_llm_template_match_model", "Foundation-sec-8B-Reasoning")

    plan = _aggregate_plan()
    result = match_route_plan_with_semantic_assist(
        plan,
        llm_raw_output_provider=lambda: json.dumps({"llm_semantic_hints": {"datamodel_hint": "Authentication"}}),
    )

    assert result.llm_assist_enabled is True
    assert result.template_match_llm_hints is not None
    assert result.template_match_llm_hints.get("rejected_reason") == "reasoning_model_not_allowed_for_matching"


def test_sidecar_timeout_proceeds_without_hints(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "mock")
    monkeypatch.setattr(settings, "ai_soc_llm_template_match_provider", "foundation_sec_instruct")

    def slow_provider() -> str:
        time.sleep(2.0)
        return json.dumps({"llm_semantic_hints": {"datamodel_hint": "Authentication"}})

    plan = _aggregate_plan()
    result = match_route_plan_with_semantic_assist(plan, llm_raw_output_provider=slow_provider)

    assert result.llm_assist_enabled is True
    assert result.llm_assist_timed_out is True
    assert result.matched is True
    assert result.template_match_llm_hints is not None
    assert result.template_match_llm_hints.get("timed_out") is True
    assert result.template_match_llm_hints.get("llm_semantic_hints") is None


def test_adapter_role_registered() -> None:
    from app.llm.adapter.role_registry import schema_for_role

    schema = schema_for_role(TEMPLATE_MATCH_SEMANTIC_ASSIST_ROLE)
    assert schema.__name__ == "TemplateMatchSemanticAssistPayload"
