"""Governed LLM SPL advisory fallback. Exercised with injected raw output
(`llm_raw_output_provider`) so no real HTTP is made. Covers the approve path and
each clarification branch, and asserts the candidate is never executable."""

from __future__ import annotations

import json

import pytest

from app.spl.llm_fallback import (
    CLARIFICATION_INVALID_SCHEMA,
    CLARIFICATION_LLM_DISABLED,
    CLARIFICATION_UNSUPPORTED_SOURCE,
    CLARIFICATION_VALIDATION_FAILED,
    generate_llm_spl_fallback,
)

_APPROVED_SPL = (
    "search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now "
    "action=failure | stats count as fail_count by src_ip | sort -fail_count | head 100"
)


def _raw(candidate_spl: str) -> str:
    return json.dumps(
        {
            "candidate_spl": candidate_spl,
            "assumptions": ["Restricted to allowed auth source."],
            "required_fields": ["src_ip", "action"],
            "validation_notes": ["execution_eligible forced false"],
            "execution_eligible": True,  # adapter must force this to false
        }
    )


def _enable(monkeypatch: pytest.MonkeyPatch) -> None:
    for attr, value in (
        ("ai_soc_llm_spl_fallback_enabled", True),
        ("ai_soc_llm_enabled", True),
        ("ai_soc_llm_mode", "local"),
    ):
        monkeypatch.setattr(f"app.spl.llm_fallback.settings.{attr}", value)


def test_fallback_disabled_returns_clarification(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.spl.llm_fallback.settings.ai_soc_llm_spl_fallback_enabled", False)
    result = generate_llm_spl_fallback(user_query="failed logins by source ip", llm_raw_output_provider=lambda: _raw(_APPROVED_SPL))
    assert result is not None
    assert result.clarification_required is True
    assert result.clarification_reason == CLARIFICATION_LLM_DISABLED
    assert result.approved is False


def test_fallback_approved_is_validated_and_non_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable(monkeypatch)
    result = generate_llm_spl_fallback(user_query="failed logins by source ip", llm_raw_output_provider=lambda: _raw(_APPROVED_SPL))
    assert result is not None
    assert result.approved is True
    assert result.clarification_required is False
    assert "src_ip" in result.candidate_spl
    # Governance invariant: never executable.
    assert result.validation.get("execution_eligible") in (None, False)


def test_fallback_schema_invalid_clarifies(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable(monkeypatch)
    result = generate_llm_spl_fallback(user_query="x", llm_raw_output_provider=lambda: "not json at all")
    assert result is not None
    assert result.approved is False
    assert result.clarification_required is True
    assert result.clarification_reason == CLARIFICATION_INVALID_SCHEMA


def test_fallback_unsupported_source_clarifies(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable(monkeypatch)
    bad = "search index=other_index sourcetype=foo | stats count by src_ip | head 100"
    result = generate_llm_spl_fallback(user_query="x", llm_raw_output_provider=lambda: _raw(bad))
    assert result is not None
    assert result.approved is False
    assert result.clarification_reason == CLARIFICATION_UNSUPPORTED_SOURCE
    assert result.validation.get("approved") is False


def test_fallback_blocked_command_fails_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable(monkeypatch)
    # Allowed source so it passes the source pre-check, but a blocked command
    # must be rejected by the deterministic validator.
    bad = "search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now | delete"
    result = generate_llm_spl_fallback(user_query="x", llm_raw_output_provider=lambda: _raw(bad))
    assert result is not None
    assert result.approved is False
    assert result.clarification_reason == CLARIFICATION_VALIDATION_FAILED


# --- pipeline wiring (`_candidate_from_llm_fallback`) ---

from app.chat import pipeline as chat_pipeline
from app.spl.llm_fallback import LlmSplFallbackResult


class _Telemetry:
    def record_step(self, *a, **k) -> None: ...
    def record_spl_validation(self, *a, **k) -> None: ...


class _Profile:
    def model_dump(self) -> dict:
        return {}


def test_wiring_disabled_returns_none_for_legacy_non_control_plane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", False)
    out = chat_pipeline._candidate_from_llm_fallback(
        trace_id="t", skill="spl_generation", user_query="x", telemetry=_Telemetry(), profile=_Profile()
    )
    assert out is None


def test_wiring_enabled_maps_approved_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", True)
    spl = "search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now action=failure | stats count by src_ip | head 100"
    monkeypatch.setattr(
        "app.chat.pipeline.generate_llm_spl_fallback",
        lambda *, user_query: LlmSplFallbackResult(
            candidate_spl=spl, approved=True,
            validation={"approved": True, "normalized_spl": spl, "reject_reasons": [], "warnings": [], "enforced_limits": {}, "policy_version": "v1"},
        ),
    )
    candidate_payload, validation_payload = chat_pipeline._candidate_from_llm_fallback(
        trace_id="t", skill="spl_generation", user_query="x", telemetry=_Telemetry(), profile=_Profile()
    )
    assert candidate_payload["generation_mode"] == "llm_spl_advisory_fallback"
    assert validation_payload["approved"] is True
    assert validation_payload["selected_candidate_spl_provider"] == "llm_spl_advisory_fallback"
    # Governance invariant: provider never reports an executable candidate.
    assert validation_payload["fallback_required"] is True


def test_wiring_enabled_propagates_clarification(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", True)
    monkeypatch.setattr(
        "app.chat.pipeline.generate_llm_spl_fallback",
        lambda *, user_query: LlmSplFallbackResult(
            candidate_spl="", approved=False,
            validation={"approved": False, "normalized_spl": None, "reject_reasons": ["empty_spl"], "warnings": [], "enforced_limits": {}, "policy_version": "v1"},
            clarification_required=True, clarification_reason=CLARIFICATION_VALIDATION_FAILED,
        ),
    )
    candidate_payload, validation_payload = chat_pipeline._candidate_from_llm_fallback(
        trace_id="t", skill="spl_generation", user_query="x", telemetry=_Telemetry(), profile=_Profile()
    )
    assert validation_payload["approved"] is False
    assert CLARIFICATION_VALIDATION_FAILED in validation_payload["reject_reasons"]
    assert candidate_payload["warnings"] == ["llm_spl_fallback_requires_clarification"]
