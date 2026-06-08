from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from app.config import settings
from app.llm.adapter import adapt_llm_output
from app.llm.clients import LocalChatClient, LocalChatError, build_synthesis_client_from_settings
from app.safeguards.spl_validator import validate_spl
from app.spl.draft_quality import STANDARD_ID, evaluate_draft_quality
from app.spl.family_engineering import full_engineering_prompt, universal_engineering_prompt

SPL_ADVISORY_ROLE = "spl_advisory_generator"

CLARIFICATION_LLM_DISABLED = "llm_spl_fallback_disabled"
CLARIFICATION_NO_CLIENT = "llm_spl_fallback_client_unavailable"
CLARIFICATION_INVALID_SCHEMA = "llm_spl_fallback_schema_invalid"
CLARIFICATION_VALIDATION_FAILED = "llm_spl_fallback_validation_failed"
CLARIFICATION_QUALITY_FAILED = "llm_spl_fallback_quality_failed"
CLARIFICATION_UNSUPPORTED_SOURCE = "llm_spl_fallback_unsupported_source"


@dataclass(frozen=True)
class LlmSplFallbackResult:
    candidate_spl: str
    approved: bool
    validation: dict
    status: str = "blocked"
    confidence_score: float = 0.0
    confidence_label: str = "low"
    detection_family: str = ""
    assumptions: list[str] = field(default_factory=list)
    required_fields: list[str] = field(default_factory=list)
    missing_details: list[str] = field(default_factory=list)
    clarifying_questions: list[str] = field(default_factory=list)
    validation_notes: list[str] = field(default_factory=list)
    soc_std_rules_applied: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)
    provider: str = "llm_spl_advisory"
    model: str | None = None
    latency_ms: int | None = None
    clarification_required: bool = False
    clarification_reason: str | None = None
    adapter_errors: list[str] = field(default_factory=list)
    quality_standard: str | None = None
    quality_status: str | None = None
    quality_findings: list[dict[str, Any]] = field(default_factory=list)
    hard_fail_count: int = 0


def generate_llm_spl_fallback(
    *,
    user_query: str,
    llm_raw_output_provider: Callable[[], str] | None = None,
    client: LocalChatClient | None = None,
) -> LlmSplFallbackResult | None:
    """Generate candidate SPL from LLM advisory fallback (default-off, never governed).

    The LLM is never authoritative: JSON is adapted through the role schema,
    execution eligibility is forced false by the adapter contract, SPL must pass
    deterministic validation and SOC-STD-SPL-001 quality lint before exposure.
    """
    if not settings.ai_soc_llm_spl_fallback_enabled:
        return _clarification(CLARIFICATION_LLM_DISABLED)
    if settings.ai_soc_llm_mode.strip().lower() == "disabled" or not settings.ai_soc_llm_enabled:
        return _clarification(CLARIFICATION_LLM_DISABLED)

    raw_output: str | None = None
    model: str | None = None
    latency_ms: int | None = None
    if llm_raw_output_provider is not None:
        raw_output = llm_raw_output_provider()
    else:
        active_client = client or build_synthesis_client_from_settings()
        if active_client is None:
            return _clarification(CLARIFICATION_NO_CLIENT)
        try:
            completion = active_client.generate(
                system_prompt=_system_prompt(),
                user_prompt=_user_prompt(user_query),
                max_tokens=min(settings.ai_soc_llm_max_output_tokens, 400),
                temperature=0.0,
            )
        except LocalChatError:
            return _clarification(CLARIFICATION_NO_CLIENT)
        raw_output = completion.text
        model = completion.model
        latency_ms = completion.latency_ms

    strict_payload, strict_errors = _strict_json_payload(raw_output or "")
    if strict_payload is None:
        return _clarification(
            CLARIFICATION_INVALID_SCHEMA,
            adapter_errors=strict_errors,
            model=model,
            latency_ms=latency_ms,
        )

    adapted = adapt_llm_output(role=SPL_ADVISORY_ROLE, raw_output=json.dumps(strict_payload))
    if not adapted.accepted or not adapted.normalized_payload:
        return _clarification(
            CLARIFICATION_INVALID_SCHEMA,
            adapter_errors=list(adapted.errors),
            model=model,
            latency_ms=latency_ms,
        )

    payload = adapted.normalized_payload
    status = str(payload.get("status") or "candidate_generated")
    if status not in {"candidate_generated", "needs_clarification", "blocked"}:
        return _clarification(
            CLARIFICATION_INVALID_SCHEMA,
            adapter_errors=[f"invalid status: {status}"],
            model=model,
            latency_ms=latency_ms,
        )
    confidence_score = _confidence_score(payload.get("confidence_score"))
    confidence_label = str(payload.get("confidence_label") or "low").lower()
    if confidence_label not in {"low", "medium", "high"}:
        confidence_label = "low"
    detection_family = str(payload.get("detection_family") or "")
    candidate_spl = str(payload.get("candidate_spl") or "").strip()
    assumptions = [str(item) for item in payload.get("assumptions") or []]
    required_fields = [str(item) for item in payload.get("required_fields") or []]
    missing_details = [str(item) for item in payload.get("missing_details") or []]
    clarifying_questions = [str(item) for item in payload.get("clarifying_questions") or []]
    validation_notes = [str(item) for item in payload.get("validation_notes") or []]
    soc_std_rules_applied = [str(item) for item in payload.get("soc_std_rules_applied") or []]
    risk_notes = [str(item) for item in payload.get("risk_notes") or []]

    if status == "blocked":
        return LlmSplFallbackResult(
            candidate_spl="",
            approved=False,
            validation={**validate_spl(""), "approved": False, "normalized_spl": None},
            status="blocked",
            confidence_score=confidence_score,
            confidence_label=confidence_label,
            detection_family=detection_family,
            assumptions=assumptions,
            required_fields=required_fields,
            missing_details=missing_details,
            clarifying_questions=clarifying_questions,
            validation_notes=validation_notes,
            soc_std_rules_applied=soc_std_rules_applied,
            risk_notes=risk_notes,
            model=model,
            latency_ms=latency_ms,
            clarification_required=True,
            clarification_reason=CLARIFICATION_INVALID_SCHEMA,
        )

    if not candidate_spl and status != "needs_clarification":
        return _clarification(
            CLARIFICATION_INVALID_SCHEMA,
            model=model,
            latency_ms=latency_ms,
        )

    if not assumptions or not required_fields:
        return _clarification(
            CLARIFICATION_INVALID_SCHEMA,
            model=model,
            latency_ms=latency_ms,
            adapter_errors=["assumptions and required_fields must be non-empty arrays"],
        )

    if status == "needs_clarification" and not candidate_spl:
        return LlmSplFallbackResult(
            candidate_spl="",
            approved=False,
            validation={**validate_spl(""), "approved": False, "normalized_spl": None},
            status="needs_clarification",
            confidence_score=confidence_score,
            confidence_label=confidence_label,
            detection_family=detection_family,
            assumptions=assumptions,
            required_fields=required_fields,
            missing_details=missing_details,
            clarifying_questions=clarifying_questions,
            validation_notes=validation_notes,
            soc_std_rules_applied=soc_std_rules_applied,
            risk_notes=risk_notes,
            model=model,
            latency_ms=latency_ms,
            clarification_required=True,
            clarification_reason="llm_spl_fallback_needs_clarification",
        )

    quality = evaluate_draft_quality(
        candidate_spl,
        extra_text=" ".join([*assumptions, *validation_notes, *risk_notes]),
        detection_family=detection_family or None,
    )
    quality_payload = quality.to_dict()
    quality_findings = list(quality_payload.get("findings") or [])

    validation = validate_spl(candidate_spl)
    if quality.hard_fail_count > 0:
        return LlmSplFallbackResult(
            candidate_spl="",
            approved=False,
            validation={**validation, "approved": False, "normalized_spl": None},
            status="blocked",
            confidence_score=confidence_score,
            confidence_label=confidence_label,
            detection_family=detection_family,
            assumptions=assumptions,
            required_fields=required_fields,
            missing_details=missing_details,
            clarifying_questions=clarifying_questions,
            validation_notes=validation_notes,
            soc_std_rules_applied=soc_std_rules_applied,
            risk_notes=risk_notes,
            model=model,
            latency_ms=latency_ms,
            clarification_required=True,
            clarification_reason=CLARIFICATION_QUALITY_FAILED,
            quality_standard=STANDARD_ID,
            quality_status=quality_payload["quality_status"],
            quality_findings=quality_findings,
            hard_fail_count=quality.hard_fail_count,
        )

    approved = bool(validation.get("approved"))
    if not approved:
        return LlmSplFallbackResult(
            candidate_spl="",
            approved=False,
            validation={**validation, "approved": False, "normalized_spl": None},
            status="needs_clarification" if status == "needs_clarification" else "blocked",
            confidence_score=confidence_score,
            confidence_label=confidence_label,
            detection_family=detection_family,
            assumptions=assumptions,
            required_fields=required_fields,
            missing_details=missing_details,
            clarifying_questions=clarifying_questions,
            validation_notes=validation_notes,
            soc_std_rules_applied=soc_std_rules_applied,
            risk_notes=risk_notes,
            model=model,
            latency_ms=latency_ms,
            clarification_required=True,
            clarification_reason=CLARIFICATION_VALIDATION_FAILED,
            quality_standard=STANDARD_ID,
            quality_status=quality_payload["quality_status"],
            quality_findings=quality_findings,
            hard_fail_count=quality.hard_fail_count,
        )

    return LlmSplFallbackResult(
        candidate_spl=candidate_spl,
        approved=True,
        validation=validation,
        status="candidate_generated",
        confidence_score=confidence_score,
        confidence_label=confidence_label,
        detection_family=detection_family,
        assumptions=assumptions,
        required_fields=required_fields,
        missing_details=missing_details,
        clarifying_questions=clarifying_questions,
        validation_notes=validation_notes,
        soc_std_rules_applied=soc_std_rules_applied,
        risk_notes=risk_notes,
        model=model,
        latency_ms=latency_ms,
        clarification_required=False,
        clarification_reason=None,
        quality_standard=STANDARD_ID,
        quality_status=quality_payload["quality_status"],
        quality_findings=quality_findings,
        hard_fail_count=quality.hard_fail_count,
    )


def _clarification(
    reason: str,
    *,
    adapter_errors: list[str] | None = None,
    model: str | None = None,
    latency_ms: int | None = None,
) -> LlmSplFallbackResult:
    validation = validate_spl("")
    return LlmSplFallbackResult(
        candidate_spl="",
        approved=False,
        validation={**validation, "approved": False, "normalized_spl": None},
        status="needs_clarification",
        confidence_score=0.0,
        confidence_label="low",
        model=model,
        latency_ms=latency_ms,
        clarification_required=True,
        clarification_reason=reason,
        adapter_errors=list(adapter_errors or []),
    )


def _strict_json_payload(raw_output: str) -> tuple[dict[str, Any] | None, list[str]]:
    text = (raw_output or "").strip()
    if not text:
        return None, ["empty_llm_output"]
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, [f"strict_json_parse_failed:{exc.msg}"]
    if not isinstance(payload, dict):
        return None, ["strict_json_object_required"]
    if json.dumps(payload, sort_keys=True, separators=(",", ":")) != json.dumps(
        json.loads(text), sort_keys=True, separators=(",", ":")
    ):
        return None, ["strict_json_object_required"]
    return payload, []


def _confidence_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, score))


def _soc_std_spl_001_prompt_rules() -> str:
    return (
        f"{universal_engineering_prompt()}\n\n"
        "SOC-STD-SPL-001 additional quality rules (candidate_spl must comply):\n"
        "C. Normalize fields early with coalesce(), for example user_norm=lower(coalesce(user, username, "
        "src_user, Account_Name, TargetUserName, \"unknown\")); src_ip_norm=coalesce(src_ip, src, source, "
        "source_ip, Source_Network_Address, \"unknown\"); dest_ip_norm=coalesce(dest_ip, dest, destination, "
        "dest_ip, \"unknown\"); command_line_norm=coalesce(CommandLine, command_line, process_command_line, "
        "cmdline, \"\"); image_norm=lower(coalesce(Image, process_path, process_name, New_Process_Name, \"\")); "
        "parent_image_norm=lower(coalesce(ParentImage, parent_process_path, parent_process_name, \"\")); "
        "domain_norm=lower(coalesce(query, query_name, domain, dns_query, url_domain, \"\")).\n"
        "D. Escape Windows paths with double backslashes in SPL strings: \"%\\\\cmd.exe\", "
        "\"%\\\\powershell.exe\", \"%\\\\w3wp.exe\". Do not use broken single-backslash patterns like "
        "\"*\\w3wp.exe\".\n"
        "E. Use cidrmatch() for CIDR ranges, e.g. cidrmatch(\"10.0.0.0/8\", src_ip_norm); do not use "
        "IN (\"10.0.0.0/8\") for subnet matching.\n"
        "F. Avoid broken quoted strings: no newline inside quoted strings, no multiline regex inside "
        "quotes; prefer like(lower(field), \"%value%\") for simple matching.\n"
        "G. Format analyst timestamps at the end: if using earliest(_time) or latest(_time), add "
        "first_seen_readable=strftime(first_seen, \"%Y-%m-%d %H:%M:%S\") and "
        "last_seen_readable=strftime(last_seen, \"%Y-%m-%d %H:%M:%S\").\n"
        "H. No false claims: do not say results were found, SPL was executed, SPL is approved, SPL is "
        "governed, compromise is confirmed, or invent customer-specific index/sourcetype/field names as fact.\n"
        "I. Use placeholders when unknown, such as index=<windows_index>, "
        "sourcetype=<windows_security_sourcetype>, index=<sysmon_index>, sourcetype=<sysmon_sourcetype>, "
        "index=<firewall_index>, sourcetype=<firewall_sourcetype>. List placeholders in assumptions and "
        "required_fields.\n"
    )


def _detection_family_prompt() -> str:
    return full_engineering_prompt()


def _system_prompt() -> str:
    return (
        "You are the AI SOC SPL advisory fallback (lab candidate only — never governed, "
        "never catalog-approved, never executable). Output ONE JSON object and nothing else: "
        "no markdown fences, no text before or after.\n"
        f"{_soc_std_spl_001_prompt_rules()}"
        f"{_detection_family_prompt()}"
        "Decide whether the request is sufficiently specified. Return clarification questions when "
        "index/sourcetype cannot be safely placeholdered, the required log source is unclear, fields "
        "required for logic are missing, threshold/time window is unclear, asset zone definitions are "
        "missing, engineering workstation allowlist is missing, protocol/function-code mapping is missing, "
        "or the user asks to execute or confirm results. You may still produce a placeholder-based lab "
        "candidate if the question is clear enough for preview.\n"
        "The candidate_spl MUST:\n"
        "- begin with `search index=<index> sourcetype=<sourcetype>` using angle-bracket "
        "placeholders (do not hardcode environment-specific index or sourcetype values);\n"
        "- include `earliest=-<N>[mhd]` and `latest=now`;\n"
        "- use only: search, stats, where, table, fields, sort, dedup, rename, eval, "
        "timechart, bin, head, streamstats;\n"
        "- end with `head 100`;\n"
        "- NOT use: from, tstats, datamodel, subsearches, macros, delete, collect, "
        "outputlookup, sendemail, rest, or any write command.\n"
        "confidence_score must reflect source-profile completeness and field certainty. High confidence "
        "only when a known family maps clearly and key fields are present or safely placeholdered; medium "
        "when family is clear but source profile/field mapping is incomplete; low when family is uncertain "
        "or clarification is required. assumptions MUST list index/sourcetype placeholder meanings and "
        "field mappings. required_fields MUST list Splunk fields the query depends on. execution_eligible, "
        "governed, and catalog_approved MUST be false.\n"
        "Example output:\n"
        '{"status": "candidate_generated", "confidence_score": 0.72, "confidence_label": "medium", '
        '"detection_family": "windows_account_lockout", "candidate_spl": "search index=<auth_index> sourcetype=<auth_sourcetype> '
        "earliest=-60m latest=now action=failure | eval src_ip=coalesce(src_ip, src, source, "
        '"") | stats count as failed_logins by src_ip | sort -failed_logins | head 100", '
        '"assumptions": ["<auth_index> is the authentication log index", '
        '"<auth_sourcetype> is the auth sourcetype", "src_ip holds the client address"], '
        '"required_fields": ["src_ip", "action", "index", "sourcetype"], "missing_details": [], '
        '"clarifying_questions": [], '
        '"validation_notes": ["Lab candidate only; execution_eligible forced false"], '
        '"soc_std_rules_applied": ["shift_left_filtering", "coalesce_normalization"], '
        '"risk_notes": ["Not governed; SOC review required"], "execution_eligible": false, '
        '"governed": false, "catalog_approved": false}'
    )


def _user_prompt(user_query: str) -> str:
    return (
        "User request:\n"
        f"{user_query}\n\n"
        "Return only JSON with keys status, confidence_score, confidence_label, detection_family, "
        "candidate_spl, assumptions, required_fields, missing_details, clarifying_questions, "
        "validation_notes, soc_std_rules_applied, risk_notes, execution_eligible, governed, catalog_approved."
    )
