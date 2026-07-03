"""LLM SPL advisory fallback (default-off). Exercised with injected raw output
(`llm_raw_output_provider`) so no real HTTP is made."""

from __future__ import annotations

import json

import pytest

from app.chat import pipeline as chat_pipeline
from app.llm.clients.local_chat_client import ChatResult, LocalChatError
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
            "status": "candidate_generated",
            "confidence_score": 0.73,
            "confidence_label": "medium",
            "detection_family": "windows_account_lockout",
            "candidate_spl": candidate_spl,
            "assumptions": assumptions
            or [
                "<auth_index> maps to pgcil_soc for this test fixture only.",
                "src_ip holds the client address.",
            ],
            "required_fields": ["src_ip", "action", "index", "sourcetype"],
            "missing_details": [],
            "clarifying_questions": [],
            "validation_notes": ["Lab candidate only; execution_eligible forced false"],
            "soc_std_rules_applied": ["shift_left_filtering"],
            "risk_notes": ["Not governed; SOC review required"],
            "execution_eligible": True,
            "governed": True,
            "catalog_approved": True,
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
    assert "U1." in prompt or "shift-left" in prompt.lower()
    assert "*it*" not in prompt or "noisy" in prompt.lower() or "Do not use noisy" in prompt
    assert "U2." in prompt or "native _time" in prompt.lower()
    assert "U3." in prompt or "stats inclusion" in prompt.lower()
    assert "streamstats" in prompt.lower()
    assert "values()" in prompt
    assert "shift-left" in prompt.lower() or "base search" in prompt.lower()
    assert "coalesce" in prompt.lower()
    assert "cidrmatch" in prompt.lower()
    assert "strftime" in prompt.lower()
    assert "double backslash" in prompt.lower() or "\\\\" in prompt
    assert "results found" in prompt.lower() or "results were found" in prompt.lower()
    assert "catalog-approved" in prompt.lower() or "catalog approved" in prompt.lower()
    assert "governed" in prompt.lower()
    assert "execution" in prompt.lower()


def test_system_prompt_includes_detection_family_context_and_schema() -> None:
    prompt = _system_prompt()
    assert "Privileged Group Changes / Active Directory" in prompt
    assert "Windows Account Lockout / Event 4740" in prompt
    assert "Sysmon Web Server Spawning Shell" in prompt
    assert "SCADA DNP3/Modbus Write/Modify" in prompt
    assert "ESP IT to OT Boundary" in prompt
    assert "Substation OS/HMI Brute Force" in prompt
    assert "streamstats" in prompt
    assert "confidence_score" in prompt
    assert "clarifying_questions" in prompt


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
    assert result.status == "candidate_generated"
    assert result.confidence_score == pytest.approx(0.73)
    assert result.confidence_label == "medium"


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


class _LengthClient:
    def generate(self, **kwargs) -> ChatResult:  # noqa: ANN003
        return ChatResult(
            text='{"status": "candidate_generated"',
            model="stub",
            latency_ms=1,
            finish_reason="length",
        )


def test_fallback_rejects_length_finish_reason_before_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable(monkeypatch)
    result = generate_llm_spl_fallback(user_query="failed logins last 24 hours", client=_LengthClient())

    assert result is not None
    assert result.approved is False
    assert result.candidate_spl == ""
    assert result.clarification_reason == CLARIFICATION_INVALID_SCHEMA
    assert "llm_finish_reason=length" in result.adapter_errors


def test_fallback_tolerates_json_with_surrounding_prose(monkeypatch: pytest.MonkeyPatch) -> None:
    # Behavior change (tolerant-parser slice): small instruct models wrap JSON in
    # prose / ```json fences. The producer now extracts the first balanced object
    # and processes it through the normal validation gates, instead of rejecting it
    # as schema-invalid. Governance still applies (the extracted SPL is validated).
    _enable(monkeypatch)
    result = generate_llm_spl_fallback(
        user_query="x",
        llm_raw_output_provider=lambda: f"Here is JSON:\n{_raw(_APPROVED_SPL)}",
    )
    assert result is not None
    assert result.clarification_reason != CLARIFICATION_INVALID_SCHEMA
    assert result.approved is True


def test_fallback_needs_clarification_surfaces_questions(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable(monkeypatch)
    raw = json.dumps(
        {
            "status": "needs_clarification",
            "confidence_score": 0.2,
            "confidence_label": "low",
            "detection_family": "scada_firewall_dnp3_modbus",
            "candidate_spl": "",
            "assumptions": ["Firewall source is required."],
            "required_fields": ["src", "dest", "protocol", "function_code"],
            "missing_details": ["engineering workstation allowlist"],
            "clarifying_questions": ["Which CIDRs define engineering workstations?"],
            "validation_notes": ["No SPL generated until required details are supplied."],
            "soc_std_rules_applied": ["clarification_before_execution"],
            "risk_notes": ["User did not supply allowlist."],
            "execution_eligible": False,
            "governed": False,
            "catalog_approved": False,
        }
    )
    result = generate_llm_spl_fallback(user_query="x", llm_raw_output_provider=lambda: raw)
    assert result is not None
    assert result.status == "needs_clarification"
    assert result.clarifying_questions == ["Which CIDRs define engineering workstations?"]
    assert result.approved is False


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


def test_wiring_request_toggle_off_blocks_even_when_server_flag_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", True)
    out = chat_pipeline._candidate_from_llm_fallback(
        trace_id="t", skill="spl_generation", user_query="x", telemetry=_Telemetry(), profile=_Profile()
    )
    assert out is None


def test_lab_stage_server_flag_false_blocks_even_when_request_toggle_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", False)
    called = False

    def _fail(*, user_query: str) -> LlmSplFallbackResult:
        nonlocal called
        called = True
        raise AssertionError("LLM fallback should not run")

    monkeypatch.setattr("app.chat.pipeline.generate_llm_spl_fallback", _fail)
    out = chat_pipeline._llm_spl_candidate_stage(
        skill="spl_generation",
        user_query="x",
        request_enabled=True,
    )
    assert out is None
    assert called is False


def test_wiring_enabled_maps_candidate_ready_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", True)
    monkeypatch.setattr(
        "app.chat.pipeline.generate_llm_spl_fallback",
        lambda *, user_query, **_kw: LlmSplFallbackResult(
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
        trace_id="t", skill="spl_generation", user_query="x", telemetry=_Telemetry(), profile=_Profile(), request_enabled=True
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
        lambda *, user_query, **_kw: LlmSplFallbackResult(
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
        trace_id="t", skill="spl_generation", user_query="failed logins", telemetry=_Telemetry(), profile=_Profile(), request_enabled=True
    )
    assert candidate_payload.get("governed") is False
    assert validation_payload.get("catalog_approved") is False
    assert candidate_payload["execution_enabled"] is False
    assert validation_payload["execution_eligible"] is False


def test_wiring_quality_hard_fail_blocks_spl_exposure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", True)
    monkeypatch.setattr(
        "app.chat.pipeline.generate_llm_spl_fallback",
        lambda *, user_query, **_kw: LlmSplFallbackResult(
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
        trace_id="t", skill="spl_generation", user_query="x", telemetry=_Telemetry(), profile=_Profile(), request_enabled=True
    )
    assert candidate_payload["candidate_spl"] == ""
    assert validation_payload["normalized_spl"] is None
    assert validation_payload["approved"] is False
    assert CLARIFICATION_QUALITY_FAILED in validation_payload["reject_reasons"]


def test_wiring_enabled_propagates_clarification(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", True)
    monkeypatch.setattr(
        "app.chat.pipeline.generate_llm_spl_fallback",
        lambda *, user_query, **_kw: LlmSplFallbackResult(
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
        trace_id="t", skill="spl_generation", user_query="x", telemetry=_Telemetry(), profile=_Profile(), request_enabled=True
    )
    assert validation_payload["approved"] is False
    assert CLARIFICATION_VALIDATION_FAILED in validation_payload["reject_reasons"]
    assert candidate_payload["warnings"] == ["llm_spl_fallback_requires_clarification"]


def test_lab_stage_both_flags_true_maps_separate_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", True)
    monkeypatch.setattr(
        "app.chat.pipeline.generate_llm_spl_fallback",
        lambda *, user_query, **_kw: LlmSplFallbackResult(
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
            status="candidate_generated",
            confidence_score=0.8,
            confidence_label="high",
            detection_family="windows_account_lockout",
            assumptions=["placeholder indexes required"],
            required_fields=["src_ip"],
            quality_standard=STANDARD_ID,
            quality_status="passed",
            hard_fail_count=0,
        ),
    )
    payload = chat_pipeline._llm_spl_candidate_stage(
        skill="spl_generation",
        user_query="x",
        request_enabled=True,
    )
    assert payload is not None
    assert payload["llm_spl_candidate"] == _APPROVED_SPL
    assert payload["llm_spl_candidate_status"] == "candidate_generated"
    assert payload["governed"] is False
    assert payload["catalog_approved"] is False
    assert payload["execution_enabled"] is False
    assert payload["execution_eligible"] is False


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


# --- R5 relevance gate wiring -------------------------------------------------
_NETWORK_SPL = (
    "search index=<network_index> sourcetype=<network_traffic_sourcetype> earliest=-24h latest=now "
    "(dest_port=* OR bytes=*) | eval src_ip_norm=coalesce(src_ip, src) "
    "| stats sum(bytes) as total by src_ip_norm | sort - total | head 100"
)
_DNS_SPL = (
    "search index=<dns_index> sourcetype=<dns_sourcetype> earliest=-24h latest=now query=* "
    "| eval src_host_norm=lower(coalesce(src_host, src_ip)) | eval domain_norm=lower(query) "
    "| stats count as dns_query_count dc(domain_norm) as distinct_domains by src_host_norm "
    "| sort - dns_query_count | head 100"
)


def _result(spl: str) -> "LlmSplFallbackResult":
    return LlmSplFallbackResult(
        candidate_spl=spl,
        approved=True,
        validation={
            "approved": True,
            "normalized_spl": spl,
            "reject_reasons": [],
            "warnings": [],
            "enforced_limits": {},
            "policy_version": "v1",
        },
        quality_standard=STANDARD_ID,
        quality_status="passed",
        hard_fail_count=0,
    )


def test_relevance_gate_blocks_asked_x_got_y(monkeypatch: pytest.MonkeyPatch) -> None:
    # DNS question, network SPL: validated+safe but not on-question -> not exposed.
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", True)
    monkeypatch.setattr(
        "app.chat.pipeline.generate_llm_spl_fallback",
        lambda *, user_query, **_kw: _result(_NETWORK_SPL),
    )
    candidate_payload, validation_payload = chat_pipeline._candidate_from_llm_fallback(
        trace_id="t", skill="attack_discovery",
        user_query="Which hosts generated the most DNS queries?",
        telemetry=_Telemetry(), profile=_Profile(), request_enabled=True,
    )
    assert validation_payload["approved"] is False
    assert candidate_payload["candidate_spl"] == ""
    assert any(r.startswith("relevance_data_source_missing") for r in validation_payload["reject_reasons"])


def test_relevance_gate_regenerates_once_when_retry_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    # First attempt irrelevant (network), retry relevant (dns) -> exposed.
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", True)
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_failover_retry_enabled", True)
    calls = {"n": 0}

    def _two_pass(*, user_query, **_kw):
        calls["n"] += 1
        return _result(_NETWORK_SPL) if calls["n"] == 1 else _result(_DNS_SPL)

    monkeypatch.setattr("app.chat.pipeline.generate_llm_spl_fallback", _two_pass)
    candidate_payload, validation_payload = chat_pipeline._candidate_from_llm_fallback(
        trace_id="t", skill="attack_discovery",
        user_query="Which hosts generated the most DNS queries?",
        telemetry=_Telemetry(), profile=_Profile(), request_enabled=True,
    )
    assert calls["n"] == 2  # regenerated once
    assert validation_payload["approved"] is True
    assert candidate_payload["candidate_spl"] == _DNS_SPL


def test_relevance_gate_retry_off_by_default_one_call(monkeypatch: pytest.MonkeyPatch) -> None:
    # Default off: irrelevant first pass is NOT retried (single LLM call).
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", True)
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_failover_retry_enabled", False)
    calls = {"n": 0}

    def _irrelevant(*, user_query, **_kw):
        calls["n"] += 1
        return _result(_NETWORK_SPL)

    monkeypatch.setattr("app.chat.pipeline.generate_llm_spl_fallback", _irrelevant)
    _candidate_payload, validation_payload = chat_pipeline._candidate_from_llm_fallback(
        trace_id="t", skill="attack_discovery",
        user_query="Which hosts generated the most DNS queries?",
        telemetry=_Telemetry(), profile=_Profile(), request_enabled=True,
    )
    assert calls["n"] == 1  # no retry
    assert validation_payload["approved"] is False  # irrelevant network SPL not exposed


def test_relevance_gate_passes_relevant_first_try(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", True)
    calls = {"n": 0}

    def _once(*, user_query, **_kw):
        calls["n"] += 1
        return _result(_DNS_SPL)

    monkeypatch.setattr("app.chat.pipeline.generate_llm_spl_fallback", _once)
    candidate_payload, validation_payload = chat_pipeline._candidate_from_llm_fallback(
        trace_id="t", skill="attack_discovery",
        user_query="Which hosts generated the most DNS queries?",
        telemetry=_Telemetry(), profile=_Profile(), request_enabled=True,
    )
    assert calls["n"] == 1  # no regeneration needed
    assert validation_payload["approved"] is True


# --- Phase G: lab-tier exposure of placeholder SPL ---------------------------
_PLACEHOLDER_SPL = (
    "search index=<auth_index> sourcetype=<auth_sourcetype> earliest=-60m latest=now "
    "action=failure | stats count as fail_count by src_ip | sort -fail_count | head 100"
)


def test_fallback_placeholder_spl_surfaces_as_lab_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    # The real model emits placeholder indexes; full validation rejects them, but
    # the SPL must surface as a review-only lab candidate (not a clarification).
    _enable(monkeypatch)
    result = generate_llm_spl_fallback(
        user_query="x", llm_raw_output_provider=lambda: _raw(_PLACEHOLDER_SPL)
    )
    assert result is not None
    assert result.lab_tier is True
    assert result.candidate_spl == _PLACEHOLDER_SPL
    assert result.status == "candidate_generated"
    # Exposure OK, execution stays fail-closed.
    assert result.approved is True
    assert result.validation["approved"] is False
    assert result.validation["normalized_spl"] is None
    assert result.validation["exposure_tier"] == "lab_candidate"


def test_pipeline_lab_tier_exposes_spl_but_blocks_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", True)
    monkeypatch.setattr(
        "app.chat.pipeline.generate_llm_spl_fallback",
        lambda *, user_query, **_kw: LlmSplFallbackResult(
            candidate_spl=_PLACEHOLDER_SPL,
            approved=True,
            lab_tier=True,
            validation={
                "approved": False,
                "normalized_spl": None,
                "reject_reasons": ["disallowed_index", "disallowed_sourcetype"],
                "warnings": [],
                "enforced_limits": {},
                "policy_version": "v1",
                "exposure_tier": "lab_candidate",
            },
            quality_standard=STANDARD_ID,
            quality_status="passed",
            hard_fail_count=0,
        ),
    )
    candidate_payload, validation_payload = chat_pipeline._candidate_from_llm_fallback(
        trace_id="t", skill="attack_discovery", user_query="Show failed logins by source IP",
        telemetry=_Telemetry(), profile=_Profile(), request_enabled=True,
    )
    # Analyst sees the SPL...
    assert candidate_payload["candidate_spl"] == _PLACEHOLDER_SPL
    assert candidate_payload["exposure_tier"] == "lab_candidate"
    assert candidate_payload["lab_tier_exposure"] is True
    # ...but execution is fail-closed: MCP gate requires approved + normalized_spl.
    assert validation_payload["approved"] is False
    assert validation_payload["normalized_spl"] is None
    assert validation_payload["execution_eligible"] is False
    assert validation_payload["exposure_tier"] == "lab_candidate"


def test_pipeline_expected_provider_error_degrades_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", True)

    def _provider_failure(**_kwargs):
        raise LocalChatError("url_error:timeout")

    monkeypatch.setattr("app.chat.pipeline.generate_llm_spl_via_plan", _provider_failure)
    assert chat_pipeline._candidate_from_llm_fallback(
        trace_id="t",
        skill="attack_discovery",
        user_query="Show failed logins",
        telemetry=_Telemetry(),
        profile=_Profile(),
        request_enabled=True,
    ) is None


def test_pipeline_programming_error_is_not_masked_as_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_spl_fallback_enabled", True)

    def _signature_bug(**_kwargs):
        raise TypeError("signature drift")

    monkeypatch.setattr("app.chat.pipeline.generate_llm_spl_via_plan", _signature_bug)
    with pytest.raises(TypeError, match="signature drift"):
        chat_pipeline._candidate_from_llm_fallback(
            trace_id="t",
            skill="attack_discovery",
            user_query="Show failed logins",
            telemetry=_Telemetry(),
            profile=_Profile(),
            request_enabled=True,
        )
