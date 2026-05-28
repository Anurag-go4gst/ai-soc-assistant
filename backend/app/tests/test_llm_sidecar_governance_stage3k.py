"""Stage 3K sidecar governance shared helper tests."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from app.config import settings
from app.llm.registry_settings import (
    INSTRUCT_DEFAULT_MODEL,
    INSTRUCT_PROVIDER_ID,
    REASONING_DEFAULT_MODEL,
    REASONING_PROVIDER_ID,
    build_llm_governance_status,
)
from app.llm.sidecar_governance import (
    NOTE_CONFIDENCE_ADVISORY_ONLY,
    REASONING_REJECTION_MATCHING,
    SKIP_NO_PROVIDER_CONFIGURED,
    build_advisory_disagreement,
    extract_advisory_confidence,
    is_reasoning_provider_assignment,
    resolve_sidecar_role_status,
    run_sidecar_llm_with_timeout,
)
from app.spl.template_matcher import match_route_plan_to_template
from app.spl.template_matcher_llm_assist import (
    TEMPLATE_MATCH_SEMANTIC_ASSIST_ROLE,
    match_route_plan_with_semantic_assist,
    sanitize_template_match_llm_payload,
)


def test_is_reasoning_provider_assignment() -> None:
    assert is_reasoning_provider_assignment(REASONING_PROVIDER_ID, INSTRUCT_DEFAULT_MODEL)
    assert is_reasoning_provider_assignment(INSTRUCT_PROVIDER_ID, REASONING_DEFAULT_MODEL)
    assert not is_reasoning_provider_assignment(INSTRUCT_PROVIDER_ID, INSTRUCT_DEFAULT_MODEL)


def test_resolve_rejects_reasoning_from_governance_not_env_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "mock")
    monkeypatch.setattr(settings, "ai_soc_llm_template_match_provider", INSTRUCT_PROVIDER_ID)
    monkeypatch.setattr(settings, "ai_soc_llm_template_match_model", INSTRUCT_DEFAULT_MODEL)

    def _governance_with_reasoning_role() -> dict[str, Any]:
        status = build_llm_governance_status()
        roles = []
        for item in status["role_mappings"]:
            if item.get("role") == TEMPLATE_MATCH_SEMANTIC_ASSIST_ROLE:
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
        role_status = resolve_sidecar_role_status(
            TEMPLATE_MATCH_SEMANTIC_ASSIST_ROLE,
            reasoning_rejection_reason=REASONING_REJECTION_MATCHING,
        )

    assert role_status.rejected_reason == REASONING_REJECTION_MATCHING
    assert role_status.resolved_provider == REASONING_PROVIDER_ID


def test_run_sidecar_llm_with_timeout() -> None:
    import time

    def slow() -> str:
        time.sleep(2.0)
        return "{}"

    result = run_sidecar_llm_with_timeout(slow, timeout_seconds=0.05)
    assert result.timed_out is True
    assert result.raw_output is None
    assert "llm_assist_timed_out" in result.notes


def test_extract_advisory_confidence_nested() -> None:
    raw = json.dumps(
        {
            "confidence": 0.99,
            "llm_semantic_hints": {"datamodel_hint": "Authentication", "confidence": 0.5},
        }
    )
    value, notes = extract_advisory_confidence(raw, nested_paths=(("llm_semantic_hints",),))
    assert value == 0.99
    assert NOTE_CONFIDENCE_ADVISORY_ONLY in notes


def test_build_advisory_disagreement_shape() -> None:
    record = build_advisory_disagreement(
        field="datamodel",
        llm_value="Network_Traffic",
        deterministic_value="Authentication",
        reason_for_deterministic_win="datamodel_hint_advisory_only",
    )
    assert record["field"] == "datamodel"
    assert record["reason_for_deterministic_win"] == "datamodel_hint_advisory_only"


def _aggregate_plan() -> dict:
    return {
        "route_plan_id": "rp_sidecar_gov",
        "route_status": "route_ready",
        "primary_skill": "aggregate_and_rank",
        "pattern_id": "test",
        "operation_type": "top_n",
        "domain": "soc",
        "source_class": "okta_authentication_logs",
        "entities": ["user"],
        "time_window": "last_24_hours",
        "parameters": {
            "group_by": {"field": "user"},
            "metric": {"type": "count"},
            "limit": 10,
            "time_window": "last_24_hours",
        },
        "evidence_needs": {"datamodel": "Authentication", "group_by": ["user"]},
        "missing_slots": [],
        "hard_preconditions": [],
        "model_advisory_metadata": {},
        "deterministic_validation": {},
        "post_enrichment": [],
    }


def test_shadow_no_provider_returns_explicit_skip_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "mock")
    monkeypatch.setattr(settings, "ai_soc_llm_template_match_provider", "")
    monkeypatch.setattr(settings, "ai_soc_llm_template_match_model", "")
    monkeypatch.setattr(settings, "ai_soc_llm_foundation_sec_instruct_base_url", "")
    monkeypatch.setattr(settings, "ai_soc_llm_openai_base_url", "")
    monkeypatch.setattr(settings, "ai_soc_llm_local_base_url", "")
    monkeypatch.setattr(settings, "ai_soc_llm_default_provider", "")

    plan = _aggregate_plan()
    result = match_route_plan_with_semantic_assist(plan, shadow_enabled=True)

    assert result.llm_assist_enabled is False
    assert result.template_match_llm_hints is not None
    assert result.template_match_llm_hints.get("llm_assist_skipped_reason") == SKIP_NO_PROVIDER_CONFIGURED
    baseline = match_route_plan_to_template(plan)
    assert result.matched == baseline.matched


def test_reasoning_rejected_via_governance_when_env_instruct(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "mock")
    monkeypatch.setattr(settings, "ai_soc_llm_template_match_provider", INSTRUCT_PROVIDER_ID)
    monkeypatch.setattr(settings, "ai_soc_llm_template_match_model", INSTRUCT_DEFAULT_MODEL)
    monkeypatch.setattr(settings, "ai_soc_llm_foundation_sec_instruct_base_url", "http://instruct.example")
    monkeypatch.setattr(settings, "ai_soc_llm_foundation_sec_reasoning_base_url", "http://reasoning.example")

    def _governance_with_reasoning_role() -> dict[str, Any]:
        status = build_llm_governance_status()
        roles = []
        for item in status["role_mappings"]:
            if item.get("role") == TEMPLATE_MATCH_SEMANTIC_ASSIST_ROLE:
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

    plan = _aggregate_plan()
    with patch("app.llm.sidecar_governance.build_llm_governance_status", _governance_with_reasoning_role):
        result = match_route_plan_with_semantic_assist(
            plan,
            llm_raw_output_provider=lambda: json.dumps({"llm_semantic_hints": {"datamodel_hint": "Authentication"}}),
        )

    assert result.template_match_llm_hints is not None
    assert result.template_match_llm_hints.get("rejected_reason") == REASONING_REJECTION_MATCHING


def test_confidence_advisory_only_in_sanitize() -> None:
    payload = json.dumps(
        {
            "confidence": 0.95,
            "llm_semantic_hints": {
                "datamodel_hint": "Authentication",
                "confidence": 0.8,
            },
        }
    )
    sanitized, notes = sanitize_template_match_llm_payload(payload)
    hints = (sanitized or {}).get("llm_semantic_hints") or {}
    assert "confidence" not in hints
    assert "confidence_advisory_only" in notes
