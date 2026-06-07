from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from app.config import settings
from app.llm.adapter import adapt_llm_output
from app.llm.clients import LocalChatClient, LocalChatError, build_synthesis_client_from_settings
from app.safeguards.spl_validator import validate_spl

SPL_ADVISORY_ROLE = "spl_advisory_generator"

CLARIFICATION_LLM_DISABLED = "llm_spl_fallback_disabled"
CLARIFICATION_NO_CLIENT = "llm_spl_fallback_client_unavailable"
CLARIFICATION_INVALID_SCHEMA = "llm_spl_fallback_schema_invalid"
CLARIFICATION_VALIDATION_FAILED = "llm_spl_fallback_validation_failed"
CLARIFICATION_UNSUPPORTED_SOURCE = "llm_spl_fallback_unsupported_source"


@dataclass(frozen=True)
class LlmSplFallbackResult:
    candidate_spl: str
    approved: bool
    validation: dict
    assumptions: list[str] = field(default_factory=list)
    required_fields: list[str] = field(default_factory=list)
    validation_notes: list[str] = field(default_factory=list)
    provider: str = "llm_spl_advisory"
    model: str | None = None
    latency_ms: int | None = None
    clarification_required: bool = False
    clarification_reason: str | None = None
    adapter_errors: list[str] = field(default_factory=list)


def generate_llm_spl_fallback(
    *,
    user_query: str,
    llm_raw_output_provider: Callable[[], str] | None = None,
    client: LocalChatClient | None = None,
) -> LlmSplFallbackResult | None:
    """Generate candidate SPL from governed LLM advisory fallback.

    The LLM is never authoritative: its JSON is adapted through the role schema,
    execution eligibility is ignored/forced false by the adapter contract, and
    the resulting SPL must pass deterministic validation before it can be shown.
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
                # Cap low: SPL JSON is compact, and the synthesis client timeout
                # is 60s at single-digit tokens/sec — a large budget would time
                # out a legitimate response and look like a client failure.
                max_tokens=min(settings.ai_soc_llm_max_output_tokens, 400),
                temperature=0.0,
            )
        except LocalChatError:
            return _clarification(CLARIFICATION_NO_CLIENT)
        raw_output = completion.text
        model = completion.model
        latency_ms = completion.latency_ms

    adapted = adapt_llm_output(role=SPL_ADVISORY_ROLE, raw_output=raw_output or "")
    if not adapted.accepted or not adapted.normalized_payload:
        return _clarification(
            CLARIFICATION_INVALID_SCHEMA,
            adapter_errors=list(adapted.errors),
            model=model,
            latency_ms=latency_ms,
        )

    payload = adapted.normalized_payload
    candidate_spl = str(payload.get("candidate_spl") or "").strip()
    assumptions = [str(item) for item in payload.get("assumptions") or []]
    required_fields = [str(item) for item in payload.get("required_fields") or []]
    validation_notes = [str(item) for item in payload.get("validation_notes") or []]

    source_block = _source_profile_block(candidate_spl)
    if source_block:
        validation = validate_spl(candidate_spl)
        return LlmSplFallbackResult(
            candidate_spl=candidate_spl,
            approved=False,
            validation={**validation, "approved": False, "normalized_spl": None},
            assumptions=assumptions,
            required_fields=required_fields,
            validation_notes=validation_notes,
            model=model,
            latency_ms=latency_ms,
            clarification_required=True,
            clarification_reason=source_block,
        )

    validation = validate_spl(candidate_spl)
    approved = bool(validation.get("approved"))
    return LlmSplFallbackResult(
        candidate_spl=candidate_spl,
        approved=approved,
        validation=validation,
        assumptions=assumptions,
        required_fields=required_fields,
        validation_notes=validation_notes,
        model=model,
        latency_ms=latency_ms,
        clarification_required=not approved,
        clarification_reason=None if approved else CLARIFICATION_VALIDATION_FAILED,
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
        model=model,
        latency_ms=latency_ms,
        clarification_required=True,
        clarification_reason=reason,
        adapter_errors=list(adapter_errors or []),
    )


def _source_profile_block(candidate_spl: str) -> str | None:
    lowered = candidate_spl.lower()
    if not candidate_spl.strip():
        return CLARIFICATION_INVALID_SCHEMA
    if "index=pgcil_soc" not in lowered:
        return CLARIFICATION_UNSUPPORTED_SOURCE
    if "sourcetype=pgcil:auth" in lowered or "sourcetype=aws:cloudtrail" in lowered:
        return None
    return CLARIFICATION_UNSUPPORTED_SOURCE


def _system_prompt() -> str:
    return (
        "You are the AI SOC SPL advisory fallback. Output ONE JSON object and "
        "nothing else: no markdown fences, no text before or after.\n"
        "The candidate_spl MUST:\n"
        "- begin with `search index=pgcil_soc sourcetype=pgcil:auth` (use "
        "`sourcetype=aws:cloudtrail` instead only for cloud-audit questions);\n"
        "- include `earliest=-<N>[mhd]` and `latest=now`;\n"
        "- use only these commands: search, stats, where, table, fields, sort, "
        "dedup, rename, eval, timechart, bin, head;\n"
        "- end with `head 100`;\n"
        "- NOT use: from, tstats, datamodel, subsearches, macros, delete, "
        "collect, outputlookup, sendemail, rest, or any write command.\n"
        "assumptions, required_fields, and validation_notes MUST be JSON arrays "
        "of strings (not a single string). execution_eligible MUST be false.\n"
        "Example output:\n"
        '{"candidate_spl": "search index=pgcil_soc sourcetype=pgcil:auth '
        "earliest=-60m latest=now action=failure | stats count as failed_logins "
        'by src_ip | sort -failed_logins | head 100", "assumptions": ["src_ip '
        'holds the source address"], "required_fields": ["src_ip", "action"], '
        '"validation_notes": ["execution_eligible forced false by AI-SOC"], '
        '"execution_eligible": false}'
    )


def _user_prompt(user_query: str) -> str:
    return (
        "User request:\n"
        f"{user_query}\n\n"
        "Return only the JSON object with keys candidate_spl, assumptions, "
        "required_fields, validation_notes, execution_eligible."
    )
