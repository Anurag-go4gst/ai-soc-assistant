from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from app.config import settings
from app.llm.adapter import adapt_llm_output
from app.llm.clients import LocalChatClient, LocalChatError, build_synthesis_client_from_settings
from app.safeguards.spl_validator import (
    lab_validation_eligible,
    validate_spl,
    validate_spl_lab_candidate,
)
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
    lab_tier: bool = False


def generate_llm_spl_fallback(
    *,
    user_query: str,
    llm_raw_output_provider: Callable[[], str] | None = None,
    client: LocalChatClient | None = None,
    context: dict[str, Any] | None = None,
    relevance_feedback: list[str] | None = None,
    correctness_mode: bool = False,
    utility_authoring: bool = False,
) -> LlmSplFallbackResult | None:
    """Generate candidate SPL from LLM advisory fallback (default-off, never governed).

    The LLM is never authoritative: JSON is adapted through the role schema,
    execution eligibility is forced false by the adapter contract, SPL must pass
    deterministic validation and SOC-STD-SPL-001 quality lint before exposure.
    """
    if not utility_authoring and not settings.ai_soc_llm_spl_fallback_enabled:
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
        system_prompt, user_prompt = spl_advisory_prompts(
            user_query,
            utility_authoring=utility_authoring,
            correctness_mode=correctness_mode,
            context=context,
            relevance_feedback=relevance_feedback,
        )
        try:
            completion = active_client.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                # Raised from 400: the full advisory schema needs ~500 tokens; 400
                # truncated mid-JSON (finish_reason=length) on live probes.
                max_tokens=_spl_max_output_tokens(),
                temperature=0.0,
                # Constrained generation: a json_schema response_format makes
                # llama.cpp grammar-constrain the output to a valid JSON object with
                # our keys — diagnosed as the only mode this server honors (plain /
                # json_object emitted ```json fences + dropped delimiters). This is
                # the reliable fix; the tolerant repair in _strict_json_payload stays
                # as the secondary net for servers that ignore json_schema.
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "spl_advisory", "schema": SPL_ADVISORY_JSON_SCHEMA},
                },
            )
        except LocalChatError as exc:
            # A server that rejects json_schema (HTTP 400) degrades to a plain
            # call + the tolerant parser, rather than failing closed outright.
            if "http_400" in str(exc):
                try:
                    completion = active_client.generate(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        max_tokens=_spl_max_output_tokens(),
                        temperature=0.0,
                    )
                except LocalChatError:
                    return _clarification(CLARIFICATION_NO_CLIENT)
            else:
                return _clarification(CLARIFICATION_NO_CLIENT)
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
    # Lab-tier exposure: quality passed but the execution validator rejected the SPL
    # only because of placeholder index/sourcetype (it cannot know customer source
    # config). Surface it as a review-only lab candidate — same contract as the
    # deterministic draft families — never executable. `approved=True` here means
    # ANALYST EXPOSURE is OK; execution stays fail-closed downstream (the pipeline
    # keeps validation.approved=False and normalized_spl=None for lab-tier).
    if (
        not approved
        and candidate_spl
        and status == "candidate_generated"
        and lab_validation_eligible(list(validation.get("reject_reasons") or []), candidate_spl)
    ):
        lab = validate_spl_lab_candidate(candidate_spl)
        if lab.get("lab_candidate_eligible"):
            return LlmSplFallbackResult(
                candidate_spl=candidate_spl,
                approved=True,
                lab_tier=True,
                validation={**lab, "approved": False, "normalized_spl": None},
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
    if (
        utility_authoring
        and candidate_spl
        and status == "candidate_generated"
        and quality.hard_fail_count == 0
        and _utility_authoring_review_eligible(validation)
    ):
        lab = validate_spl_lab_candidate(candidate_spl)
        return LlmSplFallbackResult(
            candidate_spl=candidate_spl,
            approved=True,
            lab_tier=True,
            validation={**lab, "approved": False, "normalized_spl": None},
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




def _utility_authoring_review_eligible(validation: dict[str, Any]) -> bool:
    """Utility universal drafts may expose through postprocessor despite lab-only validator rejects."""
    rejects = [str(item) for item in (validation.get("reject_reasons") or [])]
    if validation.get("blocked_commands_found"):
        return False
    for reason in rejects:
        if reason.startswith(("blocked_command:", "disallowed_command:")):
            return False
        if reason in {"credential_or_secret_pattern", "empty_spl", "spl_validation_disabled"}:
            return False
    return True

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


def _strip_code_fences(text: str) -> str:
    """Remove a single ```json ... ``` wrapper. Foundation-sec-8B adds fences despite
    the no-fences instruction (measured 2026-06-16), which would fail the strict parser
    and reject otherwise-valid SPL. Only an outer fence is stripped; inner content is
    untouched so strict object-shape validation below still applies."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    body = stripped[3:]
    newline = body.find("\n")
    if newline != -1 and body[:newline].strip().lower() in {"", "json"}:
        body = body[newline + 1 :]
    if body.rstrip().endswith("```"):
        body = body.rstrip()[:-3]
    return body.strip()


def _extract_first_json_object(text: str) -> str | None:
    """Return the first balanced {...} object, ignoring braces inside strings.

    Small instruct models often wrap JSON in prose or emit a trailing token after
    the object; this lifts just the object so the strict parser can validate it.
    """
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _repair_json_text(text: str) -> str:
    """Best-effort, conservative repairs for common small-model JSON defects.

    Only removes trailing commas before } or ] — it never rewrites values, so it
    cannot turn invalid logic into a false positive. Missing-delimiter / truncated
    output stays a parse failure (fail-closed)."""
    return re.sub(r",(\s*[}\]])", r"\1", text)


# SPL generation needs ~490-580 output tokens (full 15-key schema + a complete
# candidate_spl). Decouple it from the shared synthesis budget
# (ai_soc_llm_max_output_tokens, often tuned low for narration, e.g. 400) with a
# hard floor so narration tuning can never truncate SPL mid-JSON again.
_SPL_OUTPUT_TOKENS_FLOOR = 640
_SPL_OUTPUT_TOKENS_CEILING = 768


def _spl_max_output_tokens() -> int:
    return max(_SPL_OUTPUT_TOKENS_FLOOR, min(settings.ai_soc_llm_max_output_tokens, _SPL_OUTPUT_TOKENS_CEILING))


def _strict_json_payload(raw_output: str) -> tuple[dict[str, Any] | None, list[str]]:
    text = _strip_code_fences(raw_output or "")
    if not text:
        return None, ["empty_llm_output"]
    # Tolerant pre-parse net (secondary to response_format=json_object): lift the
    # first balanced object out of any surrounding prose, then drop trailing commas.
    candidates = [text]
    extracted = _extract_first_json_object(text)
    if extracted and extracted != text:
        candidates.append(extracted)
    candidates.append(_repair_json_text(extracted or text))
    last_error = "strict_json_parse_failed:unknown"
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = f"strict_json_parse_failed:{exc.msg}"
            continue
        if not isinstance(payload, dict):
            last_error = "strict_json_object_required"
            continue
        return payload, []
    return None, [last_error]


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


# Datamodels the deterministic validator accepts on the CIM/tstats branch
# (mirror of app.safeguards.spl_validator.APPROVED_DATAMODELS). The correctness
# prompt may emit tstats/from against these only — validate_spl re-checks.
APPROVED_CIM_DATAMODELS = ("Authentication", "Network_Traffic", "Network_Resolution")


def _correctness_engineering_block() -> str:
    """B12 — U01/U02 + a compact correctness hint, NOT the full SOC-STD-SPL-001
    C–I list or the full detection-family catalog. Avoids reproducing draft-family
    verbosity through the model while keeping shift-left + native-time discipline."""
    return (
        f"{universal_engineering_prompt()}\n\n"
        "Correctness rules (keep the query short and exactly on-question):\n"
        "- Answer the EXACT entity, data source, action, and metric the question asks. "
        "Do not add presentation formatting (strftime, eval risk=, wide tables) unless asked.\n"
        "- Normalize key fields with coalesce() before aggregation; format any "
        "earliest/latest timestamps with strftime AFTER stats (never strftime(_time) before stats).\n"
        "- Use placeholders for unknown index/sourcetype (index=<...>, sourcetype=<...>) and list them "
        "in assumptions and required_fields. No false claims of execution/approval/governance.\n"
    )


# JSON schema for constrained generation. Mirrors the keys the adapter/_user_prompt
# expect. `required` covers the governance-critical flags so the model always emits
# them; the adapter still forces execution_eligible=false (no policy reliance on the
# model honoring these — schema only guarantees the keys are present and parseable).
SPL_ADVISORY_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {"type": "string"},
        "confidence_score": {"type": "number"},
        "confidence_label": {"type": "string"},
        "detection_family": {"type": "string"},
        "candidate_spl": {"type": "string"},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "required_fields": {"type": "array", "items": {"type": "string"}},
        "missing_details": {"type": "array", "items": {"type": "string"}},
        "clarifying_questions": {"type": "array", "items": {"type": "string"}},
        "validation_notes": {"type": "array", "items": {"type": "string"}},
        "soc_std_rules_applied": {"type": "array", "items": {"type": "string"}},
        "risk_notes": {"type": "array", "items": {"type": "string"}},
        "execution_eligible": {"type": "boolean"},
        "governed": {"type": "boolean"},
        "catalog_approved": {"type": "boolean"},
    },
    "required": ["status", "candidate_spl", "execution_eligible", "governed", "catalog_approved"],
}


def _utility_authoring_system_append() -> str:
    """Narrow utility-authoring guidance + weekend few-shot (not global authority constants)."""
    return (
        "\n\nUniversal utility SPL authoring (review-only, template-free):\n"
        "- Draft a clean SPL block that matches the user's utility request exactly.\n"
        "- Use index=<your_index> when no trusted index is provided; never invent company indexes.\n"
        "- No inline // comments; no execution or findings claims.\n"
        "- Use %w (0=Sunday, 6=Saturday) for weekend filter logic; %A is display-only.\n"
        "Weekend hour/day extraction few-shot:\n"
        '{"status": "candidate_generated", "confidence_score": 0.72, "confidence_label": "medium", '
        '"detection_family": "universal_timestamp_spl", "candidate_spl": "search index=<your_index> '
        "earliest=-24h latest=now\\n| eval hour_of_day=strftime(_time,\\\"%H\\\")\\n"
        '| eval day_of_week_num=strftime(_time,\\\"%w\\\")\\n'
        '| eval day_of_week=strftime(_time,\\\"%A\\\")\\n'
        '| where day_of_week_num IN (\\\"0\\\",\\\"6\\\")\\n'
        '| table _time hour_of_day day_of_week sourcetype host\\n| head 100", '
        '"assumptions": ["<your_index> is a placeholder index for review-only preview"], '
        '"required_fields": ["_time", "index"], "missing_details": [], '
        '"clarifying_questions": [], "validation_notes": ["Review-only utility draft"], '
        '"soc_std_rules_applied": ["coalesce_normalization"], "risk_notes": ["Not executed"], '
        '"execution_eligible": false, "governed": false, "catalog_approved": false}'
    )


def spl_advisory_prompts(
    user_query: str,
    *,
    utility_authoring: bool = False,
    correctness_mode: bool = False,
    context: dict[str, Any] | None = None,
    relevance_feedback: list[str] | None = None,
) -> tuple[str, str]:
    system_prompt = _system_prompt(correctness_mode=correctness_mode)
    if utility_authoring:
        system_prompt += _utility_authoring_system_append()
    user_prompt = _user_prompt(
        user_query,
        context=context,
        relevance_feedback=relevance_feedback,
    )
    return system_prompt, user_prompt


def _system_prompt(correctness_mode: bool = False) -> str:
    if correctness_mode:
        datamodels = ", ".join(APPROVED_CIM_DATAMODELS)
        return (
            "You are the AI SOC SPL advisory fallback (lab candidate only — never governed, "
            "never catalog-approved, never executable). Return one JSON object "
            "matching the provided schema.\n"
            f"{_correctness_engineering_block()}"
            "Decide whether the request is sufficiently specified. Return clarification questions when the "
            "required log source is unclear, fields required for logic are missing, or the user asks to "
            "execute or confirm results. Otherwise produce a placeholder-based lab candidate.\n"
            "The candidate_spl MUST:\n"
            "- query the data source the question is about (auth, network, DNS, endpoint, or firewall);\n"
            "- begin with `search index=<index> sourcetype=<sourcetype>` OR, when it answers the question "
            f"correctly and faster, `tstats ... from datamodel=<one of: {datamodels}>`;\n"
            "- include a time bound (`earliest=-<N>[mhd]` and `latest=now`, or tstats earliest/latest);\n"
            "- ALWAYS include a `stats` (or timechart/tstats) aggregation grouping by the asked entity "
            "(user, host, src_ip, domain, ...) — the deterministic validator REJECTS any query without "
            "an aggregation, so a filter-only search is not acceptable;\n"
            "- ALWAYS end with `head 100` — the validator REJECTS any query without a result limit;\n"
            "- NOT use: subsearches, macros, delete, collect, outputlookup, sendemail, rest, or any write "
            "command. (tstats/from/datamodel ARE allowed for the approved datamodels above.)\n"
            "confidence_score reflects source-profile completeness and field certainty. assumptions MUST list "
            "index/sourcetype placeholder meanings and field mappings; required_fields MUST list the Splunk "
            "fields the query depends on; execution_eligible, governed, and catalog_approved MUST be false.\n"
            'Example: {"status": "candidate_generated", "confidence_score": 0.7, "confidence_label": "medium", '
            '"detection_family": "dns_query_volume", "candidate_spl": "search index=<dns_index> '
            "sourcetype=<dns_sourcetype> earliest=-24h latest=now query=* | eval src_host_norm=lower(coalesce("
            'src_host, src_ip, "unknown")) | stats count as dns_query_count dc(query) as distinct_domains by '
            'src_host_norm | sort - dns_query_count | head 100", '
            '"assumptions": ["<dns_index>/<dns_sourcetype> are the DNS source"], '
            '"required_fields": ["src_ip", "query", "index", "sourcetype"], "missing_details": [], '
            '"clarifying_questions": [], "validation_notes": ["Lab candidate only"], '
            '"soc_std_rules_applied": ["coalesce_normalization"], "risk_notes": ["Not governed"], '
            '"execution_eligible": false, "governed": false, "catalog_approved": false}'
        )
    return (
        "You are the AI SOC SPL advisory fallback (lab candidate only — never governed, "
        "never catalog-approved, never executable). Return one JSON object "
        "matching the provided schema.\n"
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


def _user_prompt(
    user_query: str,
    *,
    context: dict[str, Any] | None = None,
    relevance_feedback: list[str] | None = None,
) -> str:
    parts = ["User request:", user_query, ""]
    if context:
        ctx_lines = []
        for key in ("primary_skill", "use_case_id", "pattern_type"):
            value = context.get(key)
            if value:
                ctx_lines.append(f"- {key}: {value}")
        sources = context.get("required_sources")
        if sources:
            ctx_lines.append(f"- required_sources: {', '.join(str(s) for s in sources)}")
        families = context.get("candidate_families")
        if families:
            ctx_lines.append(
                "- routing is ambiguous; candidate detection families (pick the one that "
                f"matches the question, or combine correctly): {', '.join(str(f) for f in families)}"
            )
        if ctx_lines:
            parts.append("Routing context (use it to anchor the data source and entity):")
            parts.extend(ctx_lines)
            parts.append("")
        grounding = context.get("t2_grounding")
        if isinstance(grounding, str) and grounding.strip():
            parts.append(
                "Deterministic grounding (advisory — anchor families/MITRE/sources; do not invent indexes):"
            )
            parts.append(grounding.strip())
            parts.append("")
    if relevance_feedback:
        parts.append(
            "Your previous attempt did not answer the question. Fix these specific mismatches:"
        )
        parts.extend(f"- {item}" for item in relevance_feedback)
        parts.append("")
    parts.append(
        "Return only JSON with keys status, confidence_score, confidence_label, detection_family, "
        "candidate_spl, assumptions, required_fields, missing_details, clarifying_questions, "
        "validation_notes, soc_std_rules_applied, risk_notes, execution_eligible, governed, catalog_approved."
    )
    return "\n".join(parts)
