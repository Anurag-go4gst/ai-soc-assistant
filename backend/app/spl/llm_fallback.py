from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.config import settings
from app.llm.adapter import adapt_llm_output
from app.llm.clients import LocalChatClient, LocalChatError, build_synthesis_client_from_settings
from app.safeguards.spl_validator import validate_spl
from app.spl.draft_quality import STANDARD_ID, evaluate_draft_quality

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
    assumptions: list[str] = field(default_factory=list)
    required_fields: list[str] = field(default_factory=list)
    validation_notes: list[str] = field(default_factory=list)
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

    if not candidate_spl:
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

    quality = evaluate_draft_quality(
        candidate_spl,
        extra_text=" ".join([*assumptions, *validation_notes]),
    )
    quality_payload = quality.to_dict()
    quality_findings = list(quality_payload.get("findings") or [])

    validation = validate_spl(candidate_spl)
    if quality.hard_fail_count > 0:
        return LlmSplFallbackResult(
            candidate_spl="",
            approved=False,
            validation={**validation, "approved": False, "normalized_spl": None},
            assumptions=assumptions,
            required_fields=required_fields,
            validation_notes=validation_notes,
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
            assumptions=assumptions,
            required_fields=required_fields,
            validation_notes=validation_notes,
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
        assumptions=assumptions,
        required_fields=required_fields,
        validation_notes=validation_notes,
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
        model=model,
        latency_ms=latency_ms,
        clarification_required=True,
        clarification_reason=reason,
        adapter_errors=list(adapter_errors or []),
    )


def _soc_std_spl_001_prompt_rules() -> str:
    return (
        "SOC-STD-SPL-001 quality rules (candidate_spl must comply):\n"
        "- Shift-left filtering: index=, sourcetype=, and static EventCode/action/protocol "
        "filters belong in the base search command.\n"
        "- Keep _time numeric until aggregation; strftime() only after stats/bin/timechart.\n"
        "- Use coalesce() early for multi-vendor field aliases in eval stages.\n"
        "- Escape Windows paths in like() with double backslashes (e.g. %\\\\cmd.exe).\n"
        "- Use cidrmatch() for CIDR allow/deny logic, not IN() on IP fields.\n"
        "- No newline characters inside quoted SPL strings.\n"
        "- Never claim results found, execution, approval, governed status, or "
        "catalog-approved status in candidate_spl, assumptions, or validation_notes.\n"
    )


def _system_prompt() -> str:
    return (
        "You are the AI SOC SPL advisory fallback (lab candidate only — never governed, "
        "never catalog-approved, never executable). Output ONE JSON object and nothing else: "
        "no markdown fences, no text before or after.\n"
        f"{_soc_std_spl_001_prompt_rules()}"
        "The candidate_spl MUST:\n"
        "- begin with `search index=<index> sourcetype=<sourcetype>` using angle-bracket "
        "placeholders (do not hardcode environment-specific index or sourcetype values);\n"
        "- include `earliest=-<N>[mhd]` and `latest=now`;\n"
        "- use only: search, stats, where, table, fields, sort, dedup, rename, eval, "
        "timechart, bin, head;\n"
        "- end with `head 100`;\n"
        "- NOT use: from, tstats, datamodel, subsearches, macros, delete, collect, "
        "outputlookup, sendemail, rest, or any write command.\n"
        "assumptions MUST list index/sourcetype placeholder meanings and field mappings. "
        "required_fields MUST list Splunk fields the query depends on. "
        "assumptions, required_fields, and validation_notes MUST be JSON arrays of strings. "
        "execution_eligible MUST be false.\n"
        "Example output:\n"
        '{"candidate_spl": "search index=<auth_index> sourcetype=<auth_sourcetype> '
        "earliest=-60m latest=now action=failure | eval src_ip=coalesce(src_ip, src, source, "
        '"") | stats count as failed_logins by src_ip | sort -failed_logins | head 100", '
        '"assumptions": ["<auth_index> is the authentication log index", '
        '"<auth_sourcetype> is the auth sourcetype", "src_ip holds the client address"], '
        '"required_fields": ["src_ip", "action", "index", "sourcetype"], '
        '"validation_notes": ["Lab candidate only; execution_eligible forced false"], '
        '"execution_eligible": false}'
    )


def _user_prompt(user_query: str) -> str:
    return (
        "User request:\n"
        f"{user_query}\n\n"
        "Return only the JSON object with keys candidate_spl, assumptions, "
        "required_fields, validation_notes, execution_eligible."
    )
