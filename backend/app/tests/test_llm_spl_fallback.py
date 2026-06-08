"""LLM SPL advisory fallback (default-off). Exercised with injected raw output
(`llm_raw_output_provider`) so no real HTTP is made."""

from __future__ import annotations

import json

import pytest

from app.chat import pipeline as chat_pipeline
from app.spl.draft_quality import STANDARD_ID
from app.spl.llm_fallback import (
    CLARIFICATION_INVALID_SCHEMA,
    CLARIFICATION_LLM_DISABLED,
    CLARIFICATION_QUALITY_FAILED,
    CLARIFICATION_VALIDATION_FAILED,
    LlmSplFallbackResult,
    _system_prompt,
    generate_llm_spl_fallback,
)

_APPROVED_SPL = (
    "search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now "
    "action=failure | eval src_ip=coalesce(src_ip, src, source, \"\") "
    "| stats count as fail_count by src_ip | sort -fail_count | head 100"
)

_QUALITY_FAIL_SPL = (
    "search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now "
    '| where ParentImage="*\\w3wp.exe" '
    "| stats count by host | head 100"
)


def _raw(candidate_spl: str, *, assumptions: list[str] | None = None) -> str:
    return json.dumps(
        {
            "candidate_spl": candidate_spl,
            "assumptions": assumptions
            or [
                "<auth_index> maps to pgcil_soc for this test fixture only.",
                "src_ip holds the client address.",
            ],
            "required_fields": ["src_ip", "action", "index", "sourcetype"],
            "validation_notes": ["Lab candidate only; execution_eligible forced false"],
            "execution_eligible": True,
        }
    )


def _enable(monkeypatch: pytest.MonkeyPatch) -> None:
    for attr, value in (
        ("ai_soc_llm_spl_fallback_enabled", True),
        ("ai_soc_llm_enabled", True),
        ("ai_soc_llm_mode", "local"),
    ):
        monkeypatch.setattr(f"app.spl.llm_fallback.settings.{attr}", value)


def test_system_prompt_includes_soc_std_spl_001_rules() -> None:
    prompt = _system_prompt()
    assert STANDARD_ID in prompt
    assert "shift-left" in prompt.lower() or "base search" in prompt.lower()
    assert "coalesce" in prompt.lower()
    assert "cidrmatch" in prompt.lower()
    assert "strftime" in prompt.lower()
    assert "double backslash" in prompt.lower() or "\\\\" in prompt
    assert "results found" in prompt.lower() or "results were found" in prompt.lower()
    assert "catalog-approved" in prompt.lower() or "catalog approved" in prompt.lower()
    assert "governed" in prompt.lower()
    assert "execution" in prompt.lower()


def test_system_prompt_does_not_hardcode_pgcil_environment() -> None:
    prompt = _system_prompt()
    assert "pgcil_soc" not in prompt
    assert "pgcil:auth" not in prompt
    assert "index=<" in prompt
    assert "sourcetype=<" in prompt


def test_fallback_disabled_returns_clarification(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.spl.llm_fallback.settings.ai_soc_llm_spl_fallback_enabled", False)
    result = generate_llm_spl_fallback(
        user_query="failed logins by source ip",
        llm_raw_output_provider=lambda: _raw(_APPROVED_SPL),
    )
    assert result is not None
    assert result.clarification_required is True
    assert result.clarification_reason == CLARIFICATION_LLM_DISABLED
    assert result.approved is False


def test_fallback_approved_is_validated_quality_linted_and_non_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(monkeypatch)
    result = generate_llm_spl_fallback(
        user_query="failed logins by source ip",
        llm_raw_output_provider=lambda: _raw(_APPROVED_SPL),
    )
    assert result is not None
    assert result.approved is True
    assert result.clarification_required is False
    assert "src_ip" in result.candidate_spl
    assert result.quality_standard == STANDARD_ID
    assert result.hard_fail_count == 0
    assert result.validation.get("execution_eligible") in (None, False)


def test_fallback_quality_hard_fail_blocks_candidate_and_normalized_spl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(monkeypatch)
    result = generate_llm_spl_fallback(
        user_query="sysmon web shell",
        llm_raw_output_provider=lambda: _raw(_QUALITY_FAIL_SPL),
    )
    assert result is not None
    assert result.approved is False
    assert result.candidate_spl == ""
    assert result.validation.get("normalized_spl") is None
    assert result.clarification_reason == CLARIFICATION_QUALITY_FAILED
    assert result.hard_fail_count >= 1
    assert result.quality_findings


def test_fallback_prohibited_claim_in_assumptions_is_quality_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(monkeypatch)
    result = generate_llm_spl_fallback(
        user_query="failed logins",
        llm_raw_output_provider=lambda: _raw(
            _APPROVED_SPL,
            assumptions=["results were found in Splunk", "src_ip holds client address"],
        ),
    )
    assert result is not None
    assert result.approved is False
    assert result.candidate_spl == ""
    assert result.clarification_reason == CLARIFICATION_QUALITY_FAILED


def test_fallback_schema_invalid_clarifies(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable(monkeypatch)
    result = generate_llm_spl_fallback(user_query="x", llm_raw_output_provider=lambda: "not json at all")
    assert result is not None
    assert result.approved is False
    assert result.clarification_required is True
    assert result.clarification_reason == CLARIFICATION_INVALID_SCHEMA


def test_fallback_missing_assumptions_or_required_fields_clarifies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(monkeypatch)
    bad = json.dumps(
        {
            "candidate_spl": _APPROVED_SPL,
            "assumptions": [],
            "required_fields": [],
            "validation_notes": [],
            "execution_eligible": False,
        }
    )
    result = generate_llm_spl_fallback(user_query="x", llm_raw_output_provider=lambda: bad)
    assert result is not None
    assert result.clarification_reason == CLARIFICATION_INVALID_SCHEMA


def test_fallback_blocked_command_fails_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable(monkeypatch)
    bad = (
        "search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now "
        "| eval src_ip=coalesce(src_ip, src, source, \"\") | delete"
    )
    result = generate_llm_spl_fallback(user_query="x", llm_raw_output_provider=lambda: _raw(bad))
    assert result is not None
    assert result.approved is False
    assert result.candidate_spl == ""
    assert result.clarification_reason == CLARIFICATION_VALIDATION_FAILED


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


def test_wiring_enabled_maps_candidate_ready_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", True)
    monkeypatch.setattr(
        "app.chat.pipeline.generate_llm_spl_fallback",
        lambda *, user_query: LlmSplFallbackResult(
            candidate_spl=_APPROVED_SPL,
            approved=True,
            validation={
                "approved": True,
                "normalized_spl": _APPROVED_SPL,
                "reject_reasons": [],
                "warnings": [],
                "enforced_limits": {},
                "policy_version": "v1",
            },
            quality_standard=STANDARD_ID,
            quality_status="passed",
            hard_fail_count=0,
        ),
    )
    candidate_payload, validation_payload = chat_pipeline._candidate_from_llm_fallback(
        trace_id="t", skill="spl_generation", user_query="x", telemetry=_Telemetry(), profile=_Profile()
    )
    assert candidate_payload["generation_mode"] == "llm_spl_advisory_fallback"
    assert validation_payload["approved"] is True
    assert validation_payload["normalized_spl"] == _APPROVED_SPL
    assert validation_payload["llm_fallback_status"] == "candidate_ready"
    assert validation_payload["fallback_required"] is True
    assert validation_payload["governed"] is False
    assert validation_payload["catalog_approved"] is False
    assert validation_payload["execution_enabled"] is False
    assert validation_payload["execution_eligible"] is False
    assert validation_payload["review_required"] is True


def test_wiring_enabled_approved_never_marks_governed_catalog_or_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", True)
    monkeypatch.setattr(
        "app.chat.pipeline.generate_llm_spl_fallback",
        lambda *, user_query: LlmSplFallbackResult(
            candidate_spl=_APPROVED_SPL,
            approved=True,
            validation={
                "approved": True,
                "normalized_spl": _APPROVED_SPL,
                "reject_reasons": [],
                "warnings": [],
                "enforced_limits": {},
                "policy_version": "v1",
            },
            quality_standard=STANDARD_ID,
            quality_status="passed",
            hard_fail_count=0,
        ),
    )
    candidate_payload, validation_payload = chat_pipeline._candidate_from_llm_fallback(
        trace_id="t", skill="spl_generation", user_query="failed logins", telemetry=_Telemetry(), profile=_Profile()
    )
    assert candidate_payload.get("governed") is False
    assert validation_payload.get("catalog_approved") is False
    assert candidate_payload["execution_enabled"] is False
    assert validation_payload["execution_eligible"] is False


def test_wiring_quality_hard_fail_blocks_spl_exposure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", True)
    monkeypatch.setattr(
        "app.chat.pipeline.generate_llm_spl_fallback",
        lambda *, user_query: LlmSplFallbackResult(
            candidate_spl="",
            approved=False,
            validation={
                "approved": False,
                "normalized_spl": None,
                "reject_reasons": [CLARIFICATION_QUALITY_FAILED],
                "warnings": [],
                "enforced_limits": {},
                "policy_version": "v1",
            },
            clarification_required=True,
            clarification_reason=CLARIFICATION_QUALITY_FAILED,
            quality_standard=STANDARD_ID,
            quality_status="failed",
            quality_findings=[{"rule_id": "SOC-STD-SPL-001-Q02", "severity": "hard_fail", "message": "x"}],
            hard_fail_count=1,
        ),
    )
    candidate_payload, validation_payload = chat_pipeline._candidate_from_llm_fallback(
        trace_id="t", skill="spl_generation", user_query="x", telemetry=_Telemetry(), profile=_Profile()
    )
    assert candidate_payload["candidate_spl"] == ""
    assert validation_payload["normalized_spl"] is None
    assert validation_payload["approved"] is False
    assert CLARIFICATION_QUALITY_FAILED in validation_payload["reject_reasons"]


def test_wiring_enabled_propagates_clarification(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", True)
    monkeypatch.setattr(
        "app.chat.pipeline.generate_llm_spl_fallback",
        lambda *, user_query: LlmSplFallbackResult(
            candidate_spl="",
            approved=False,
            validation={
                "approved": False,
                "normalized_spl": None,
                "reject_reasons": ["empty_spl"],
                "warnings": [],
                "enforced_limits": {},
                "policy_version": "v1",
            },
            clarification_required=True,
            clarification_reason=CLARIFICATION_VALIDATION_FAILED,
        ),
    )
    candidate_payload, validation_payload = chat_pipeline._candidate_from_llm_fallback(
        trace_id="t", skill="spl_generation", user_query="x", telemetry=_Telemetry(), profile=_Profile()
    )
    assert validation_payload["approved"] is False
    assert CLARIFICATION_VALIDATION_FAILED in validation_payload["reject_reasons"]
    assert candidate_payload["warnings"] == ["llm_spl_fallback_requires_clarification"]


def test_chat_message_for_llm_fallback_uses_lab_candidate_wording() -> None:
    message = chat_pipeline._chat_message(
        {
            "approved": True,
            "normalized_spl": _APPROVED_SPL,
            "llm_fallback_used": True,
            "selected_candidate_spl_provider": "llm_spl_advisory_fallback",
        }
    )
    assert "LLM lab SPL candidate" in message
    assert "not governed" in message
    assert "Governed SPL draft ready" not in message


def test_chat_message_for_template_spl_keeps_governed_wording() -> None:
    message = chat_pipeline._chat_message(
        {
            "approved": True,
            "normalized_spl": _APPROVED_SPL,
            "selected_candidate_spl_provider": "deterministic_template_render",
        }
    )
    assert "Governed SPL draft ready" in message
