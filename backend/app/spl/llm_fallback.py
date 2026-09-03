from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from app.chat.llm_interaction_trace import capture_llm_interaction
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


def _capture_spl_advisory_interaction(
    *,
    user_query: str,
    utility_authoring: bool,
    correctness_mode: bool,
    context: dict[str, Any] | None,
    relevance_feedback: list[str] | None,
    raw_output: str | None,
    parsed_payload: Any = None,
    model: str | None,
    latency_ms: int | None,
    finish_reason: str | None,
    usage: dict[str, Any] | None = None,
    provider_label: str | None = None,
    transport_status: str,
    parse_status: str,
    schema_status: str | None = None,
    quality_status: str | None = None,
    reject_reasons: list[str] | None = None,
) -> None:
    """Observability only — never changes advisory SPL selection."""
    try:
        system_prompt, user_prompt = spl_advisory_prompts(
            user_query,
            utility_authoring=utility_authoring,
            correctness_mode=correctness_mode,
            context=context,
            relevance_feedback=relevance_feedback,
        )
        capture_llm_interaction(
            role=SPL_ADVISORY_ROLE,
            stage="spl_authoring",
            provider_label=provider_label,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_schema=_advisory_response_format(context),
            temperature=0.0,
            max_tokens=_spl_max_output_tokens(),
            raw_text=raw_output,
            parsed_payload=parsed_payload,
            finish_reason=finish_reason,
            usage=usage,
            transport_status=transport_status,
            parse_status=parse_status,
            schema_status=schema_status,
            quality_status=quality_status,
            reject_reasons=reject_reasons or [],
            accepted=False,
            contributed_to_final_output=False,
            fallback_selected=True,
            fallback_reason=(reject_reasons or [None])[0],
            latency_ms=latency_ms,
        )
    except Exception:  # noqa: BLE001 - trace capture must never break SPL authoring
        return


AUTHORING_FAILURE_STAGES = (
    "provider",
    "json_parse",
    "schema_validation",
    "content_validation",
    "semantic_validation",
    "draft_quality",
    "unknown",
)
_SANITIZED_ADAPTER_FIELD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,80}$")


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
    # Phase 4B — redacted detection plan the LLM chose before compile (plan-plus-
    # compiler path only). Advisory, not authority; persisted by the workflow node
    # so downstream source-resolve/MITRE/narration prefer it over re-parsing.
    detection_plan: dict[str, Any] | None = None
    authoring_failure_stage: str | None = None
    authoring_failure_code: str | None = None
    authoring_failure_field: str | None = None
    finish_reason: str | None = None
    rejected_candidate_spl: str | None = None


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
    if llm_raw_output_provider is None:
        if not utility_authoring and not settings.ai_soc_llm_spl_fallback_enabled:
            return _clarification(
                CLARIFICATION_LLM_DISABLED,
                authoring_failure_stage="provider",
                authoring_failure_code=CLARIFICATION_LLM_DISABLED,
            )
        if settings.ai_soc_llm_mode.strip().lower() == "disabled" or not settings.ai_soc_llm_enabled:
            return _clarification(
                CLARIFICATION_LLM_DISABLED,
                authoring_failure_stage="provider",
                authoring_failure_code=CLARIFICATION_LLM_DISABLED,
            )

    raw_output: str | None = None
    model: str | None = None
    latency_ms: int | None = None
    finish_reason: str | None = None
    usage: dict[str, Any] = {}
    provider_label: str | None = None
    if llm_raw_output_provider is not None:
        raw_output = llm_raw_output_provider()
    else:
        active_client = client or build_synthesis_client_from_settings()
        if active_client is None:
            return _clarification(
                CLARIFICATION_NO_CLIENT,
                authoring_failure_stage="provider",
                authoring_failure_code=CLARIFICATION_NO_CLIENT,
            )
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
                # Pattern adaptation uses a compact {status, candidate_spl} schema
                # so the grammar does not spend the remaining budget on envelope keys.
                max_tokens=_spl_max_output_tokens(),
                temperature=0.0,
                # Constrained generation: a json_schema response_format makes
                # llama.cpp grammar-constrain the output to a valid JSON object with
                # our keys — diagnosed as the only mode this server honors (plain /
                # json_object emitted ```json fences + dropped delimiters). This is
                # the reliable fix; the tolerant repair in _strict_json_payload stays
                # as the secondary net for servers that ignore json_schema.
                response_format=_advisory_response_format(context),
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
                    return _clarification(
                        CLARIFICATION_NO_CLIENT,
                        authoring_failure_stage="provider",
                        authoring_failure_code="provider_http_error",
                    )
            else:
                return _clarification(
                    CLARIFICATION_NO_CLIENT,
                    authoring_failure_stage="provider",
                    authoring_failure_code="provider_http_error",
                )
        except LocalChatError:
            return _clarification(
                CLARIFICATION_NO_CLIENT,
                authoring_failure_stage="provider",
                authoring_failure_code="provider_http_error",
            )
        raw_output = completion.text
        model = completion.model
        latency_ms = completion.latency_ms
        finish_reason = completion.finish_reason
        usage = dict(completion.usage or {}) if getattr(completion, "usage", None) else {}
        provider_label = getattr(completion, "answered_label", None)

    strict_payload, strict_errors = _strict_json_payload(raw_output or "")
    _capture_spl_advisory_interaction(
        user_query=user_query,
        utility_authoring=utility_authoring,
        correctness_mode=correctness_mode,
        context=context,
        relevance_feedback=relevance_feedback,
        raw_output=raw_output,
        parsed_payload=strict_payload,
        model=model,
        latency_ms=latency_ms,
        finish_reason=finish_reason,
        usage=usage,
        provider_label=provider_label,
        transport_status="completed" if raw_output else "failed",
        parse_status="parsed" if strict_payload is not None else "failed",
        schema_status="valid" if strict_payload is not None else "failed",
        reject_reasons=(
            ["llm_finish_reason=length"]
            if finish_reason == "length" and not _complete_candidate_payload(strict_payload)
            else list(strict_errors or [])
        ),
    )
    if finish_reason == "length" and not _complete_candidate_payload(strict_payload):
        return _clarification(
            CLARIFICATION_INVALID_SCHEMA,
            adapter_errors=["llm_finish_reason=length"],
            model=model,
            latency_ms=latency_ms,
            authoring_failure_stage="provider",
            authoring_failure_code="finish_reason_length",
            finish_reason="length",
        )
    if strict_payload is None:
        parse_code = "empty_llm_output" if "empty_llm_output" in (strict_errors or []) else "json_parse_failed"
        return _clarification(
            CLARIFICATION_INVALID_SCHEMA,
            adapter_errors=strict_errors,
            model=model,
            latency_ms=latency_ms,
            authoring_failure_stage="json_parse",
            authoring_failure_code=parse_code,
            finish_reason=finish_reason,
        )

    if _pattern_adaptation_requested(context):
        strict_payload = _hydrate_pattern_adaptation_payload(strict_payload, context=context)
    adapted = adapt_llm_output(role=SPL_ADVISORY_ROLE, raw_output=json.dumps(strict_payload))
    if not adapted.accepted or not adapted.normalized_payload:
        field, code = _sanitized_adapter_failure(list(adapted.errors))
        stage = "schema_validation" if not adapted.schema_valid or not adapted.parsed_ok else "content_validation"
        return _clarification(
            CLARIFICATION_INVALID_SCHEMA,
            adapter_errors=_bounded_adapter_errors(list(adapted.errors)),
            model=model,
            latency_ms=latency_ms,
            authoring_failure_stage=stage,
            authoring_failure_code=code,
            authoring_failure_field=field,
            finish_reason=finish_reason,
        )

    payload = adapted.normalized_payload
    status = str(payload.get("status") or "candidate_generated")
    if status not in {"candidate_generated", "needs_clarification", "blocked"}:
        return _clarification(
            CLARIFICATION_INVALID_SCHEMA,
            adapter_errors=["invalid_status"],
            model=model,
            latency_ms=latency_ms,
            authoring_failure_stage="content_validation",
            authoring_failure_code="invalid_status",
            authoring_failure_field="status",
            finish_reason=finish_reason,
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
            authoring_failure_stage="content_validation",
            authoring_failure_code="status_blocked",
            authoring_failure_field="status",
            finish_reason=finish_reason,
        )

    if not candidate_spl and status != "needs_clarification":
        return _clarification(
            CLARIFICATION_INVALID_SCHEMA,
            model=model,
            latency_ms=latency_ms,
            adapter_errors=["empty_candidate_spl"],
            authoring_failure_stage="content_validation",
            authoring_failure_code="empty_candidate_spl",
            authoring_failure_field="candidate_spl",
            finish_reason=finish_reason,
        )

    if not assumptions or not required_fields:
        field = "assumptions" if not assumptions else "required_fields"
        return _clarification(
            CLARIFICATION_INVALID_SCHEMA,
            model=model,
            latency_ms=latency_ms,
            adapter_errors=["missing_required_non_empty_arrays"],
            authoring_failure_stage="content_validation",
            authoring_failure_code="missing_required",
            authoring_failure_field=field,
            finish_reason=finish_reason,
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
            authoring_failure_stage="content_validation",
            authoring_failure_code="needs_clarification",
            finish_reason=finish_reason,
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
            authoring_failure_stage="draft_quality",
            authoring_failure_code=CLARIFICATION_QUALITY_FAILED,
            finish_reason=finish_reason,
            rejected_candidate_spl=candidate_spl,
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
                finish_reason=finish_reason,
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
            finish_reason=finish_reason,
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
            authoring_failure_stage="content_validation",
            authoring_failure_code=CLARIFICATION_VALIDATION_FAILED,
            finish_reason=finish_reason,
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
        finish_reason=finish_reason,
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
    authoring_failure_stage: str | None = None,
    authoring_failure_code: str | None = None,
    authoring_failure_field: str | None = None,
    finish_reason: str | None = None,
) -> LlmSplFallbackResult:
    validation = validate_spl("")
    stage = authoring_failure_stage or _infer_authoring_stage(reason, adapter_errors or [])
    code = authoring_failure_code or reason
    if stage not in AUTHORING_FAILURE_STAGES:
        stage = "unknown"
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
        adapter_errors=_bounded_adapter_errors(list(adapter_errors or [])),
        authoring_failure_stage=stage,
        authoring_failure_code=code,
        authoring_failure_field=_bounded_field_name(authoring_failure_field),
        finish_reason=finish_reason,
    )


def _bounded_field_name(value: str | None) -> str | None:
    token = str(value or "").strip()
    if not token or not _SANITIZED_ADAPTER_FIELD_RE.match(token):
        return None
    return token[:80]


def _bounded_adapter_errors(errors: list[str]) -> list[str]:
    bounded: list[str] = []
    for raw in errors:
        text = str(raw or "").strip()
        if not text:
            continue
        if text.startswith("strict_json_parse_failed"):
            bounded.append("strict_json_parse_failed")
            continue
        if text in {"empty_llm_output", "strict_json_object_required", "empty_candidate_spl", "missing_required_non_empty_arrays", "invalid_status", "llm_finish_reason=length"}:
            bounded.append(text)
            continue
        location = text.split(":", 1)[0].strip()
        if _SANITIZED_ADAPTER_FIELD_RE.match(location):
            bounded.append(f"schema_field:{location}"[:80])
            continue
        bounded.append("adapter_validation_failed")
        if len(bounded) >= 8:
            break
    return bounded[:8]


def _sanitized_adapter_failure(errors: list[str]) -> tuple[str | None, str]:
    bounded = _bounded_adapter_errors(errors)
    if not bounded:
        return None, "adapter_schema_invalid"
    first = bounded[0]
    if first.startswith("schema_field:"):
        return first.split(":", 1)[1], "missing_required"
    if first == "empty_llm_output":
        return None, "empty_llm_output"
    return None, first[:80]


def _infer_authoring_stage(reason: str, adapter_errors: list[str]) -> str:
    joined = " ".join(adapter_errors)
    if reason in {CLARIFICATION_LLM_DISABLED, CLARIFICATION_NO_CLIENT}:
        return "provider"
    if "strict_json_parse_failed" in joined or "empty_llm_output" in joined:
        return "json_parse"
    if reason == CLARIFICATION_QUALITY_FAILED:
        return "draft_quality"
    if reason == CLARIFICATION_VALIDATION_FAILED:
        return "content_validation"
    if "schema_field:" in joined or (adapter_errors and reason == CLARIFICATION_INVALID_SCHEMA):
        return "schema_validation"
    if reason == CLARIFICATION_INVALID_SCHEMA:
        return "content_validation"
    return "unknown"


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


def _spl_efficiency_guidance_block() -> str:
    """Layer 1b — SPL efficiency guidance for the free-text advisory path (OPTIONAL_PHASE_S S5).

    Advisory to the model only; correctness and governed RQC time scope always win."""
    return (
        "Efficiency guidance (never sacrifice correctness for speed):\n"
        "- Use the governed RQC / request time scope exactly — never independently narrow or widen it.\n"
        "- Put index, sourcetype, and selective static filters in the base search before the first pipe.\n"
        "- Prefer positive field=value filters over broad NOT / != when the desired values are known.\n"
        "- Avoid large same-field OR chains; use field IN (a,b,c) when values are on the same field.\n"
        "- Use TERM() only for genuine minor-breaker tokens (contains . or _) not already wrapped.\n"
        "- Do not use leading wildcards in search terms.\n"
        "- Filter before expensive eval/stats; project unused columns early with | fields when safe.\n"
        "- Keep sort/stats/streamstats as late as correctness allows (except sort 0 + _time before streamstats).\n"
    )


# Probe-only toggle: live before/after probes may disable this block without editing prompts.py.
_SPL_EFFICIENCY_PROMPT_ENABLED = True


def set_spl_efficiency_prompt_enabled(enabled: bool) -> None:
    """Allow /llm-live-probe to compare with vs without Layer 1b guidance."""
    global _SPL_EFFICIENCY_PROMPT_ENABLED
    _SPL_EFFICIENCY_PROMPT_ENABLED = bool(enabled)


def _maybe_spl_efficiency_block() -> str:
    if not _SPL_EFFICIENCY_PROMPT_ENABLED:
        return ""
    return f"\n{_spl_efficiency_guidance_block()}\n"


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
        f"{_maybe_spl_efficiency_block()}"
    )


# JSON schema for constrained generation. Mirrors the keys the adapter/_user_prompt
# expect. `required` covers the governance-critical flags so the model always emits
# them; the adapter still forces execution_eligible=false (no policy reliance on the
# model honoring these — schema only guarantees the keys are present and parseable).
SPL_ADVISORY_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["candidate_generated", "needs_clarification", "blocked"],
        },
        "confidence_score": {"type": "number"},
        "confidence_label": {"type": "string"},
        "detection_family": {"type": "string"},
        "candidate_spl": {"type": "string"},
        "index": {"type": "string"},
        "sourcetype": {"type": "string"},
        "earliest": {"type": "string"},
        "latest": {"type": "string"},
        "time_window_hours": {"type": "integer"},
        "result_cap": {"type": ["integer", "null"]},
        "unresolved_slots": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "required_fields": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "missing_details": {"type": "array", "items": {"type": "string"}},
        "clarifying_questions": {"type": "array", "items": {"type": "string"}},
        "validation_notes": {"type": "array", "items": {"type": "string"}},
        "soc_std_rules_applied": {"type": "array", "items": {"type": "string"}},
        "risk_notes": {"type": "array", "items": {"type": "string"}},
        "execution_eligible": {"type": "boolean"},
        "governed": {"type": "boolean"},
        "catalog_approved": {"type": "boolean"},
    },
    # `required` is the model's COMPLETION BURDEN, not the safety contract.
    # execution_eligible / governed / catalog_approved stay declared as optional
    # properties for wire compatibility, but are deliberately NOT required: the
    # adapter forces execution_eligible=false regardless of what the model emits,
    # so making the model spend completion tokens asserting them bought nothing and
    # lengthened every response on a path that was already truncating.
    "required": [
        "status",
        "candidate_spl",
        "index",
        "sourcetype",
        "unresolved_slots",
        "assumptions",
        "required_fields",
    ],
}


# Pattern-adaptation wire contract. The full advisory schema's required envelope
# (index/sourcetype/assumptions/required_fields/unresolved_slots) is what made
# live P1 hit finish_reason=length after a long candidate_spl. This schema is
# only used when a vetted pattern is selected; the adapter still forces
# execution_eligible=false.
PATTERN_ADAPTATION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {
            "type": "string",
            "enum": ["candidate_generated", "needs_clarification", "blocked"],
        },
        "candidate_spl": {"type": "string"},
    },
    "required": ["status", "candidate_spl"],
}


AUTHORING_SOURCE_LLM_PATTERN_PRIMARY = "LLM_PATTERN_PRIMARY"
AUTHORING_SOURCE_LLM_PATTERN_NORMALIZED = "LLM_PATTERN_NORMALIZED"
AUTHORING_SOURCE_LLM_PATTERN_REPAIR = "LLM_PATTERN_REPAIR"
AUTHORING_SOURCE_LEGACY_COMPILER_RESCUE = "LEGACY_COMPILER_RESCUE"
AUTHORING_SOURCE_ABSTAIN = "ABSTAIN"


def select_vetted_authoring_pattern(spec: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return the enabled governed pattern for this analysis_shape, or None.

    Selection reuses ``build_spl_intent_spec``'s analysis_shape. Only shapes with
    ``pattern_enabled=True`` are treated as vetted topology; other shots remain
    few-shots and are not claimed as governed patterns.
    """
    shape = str((spec or {}).get("analysis_shape") or "").strip().lower()
    shot = _AUTHORING_FEW_SHOTS.get(shape)
    if not isinstance(shot, dict) or not shot.get("pattern_enabled"):
        return None
    return shot


def _pattern_adaptation_requested(context: dict[str, Any] | None) -> bool:
    spec = (context or {}).get("semantic_analyst_intent") if isinstance(context, dict) else None
    return select_vetted_authoring_pattern(spec if isinstance(spec, dict) else None) is not None


def _advisory_response_format(context: dict[str, Any] | None) -> dict[str, Any]:
    if _pattern_adaptation_requested(context):
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "spl_pattern_adaptation",
                "schema": PATTERN_ADAPTATION_JSON_SCHEMA,
            },
        }
    return {
        "type": "json_schema",
        "json_schema": {"name": "spl_advisory", "schema": SPL_ADVISORY_JSON_SCHEMA},
    }


def _complete_candidate_payload(payload: dict[str, Any] | None) -> bool:
    return isinstance(payload, dict) and bool(str(payload.get("candidate_spl") or "").strip())


def _hydrate_pattern_adaptation_payload(
    payload: dict[str, Any],
    *,
    context: dict[str, Any] | None,
) -> dict[str, Any]:
    """Fill the existing advisory envelope after a compact {status, candidate_spl} wire object.

    Does not invent detection topology. Adapter/content checks still require non-empty
    assumptions and required_fields; those come from the governed contract when present.
    """
    hydrated = dict(payload)
    spec = (context or {}).get("semantic_analyst_intent") if isinstance(context, dict) else {}
    spec = spec if isinstance(spec, dict) else {}
    if not hydrated.get("assumptions"):
        hydrated["assumptions"] = ["pattern-adapted review-only draft"]
    if not hydrated.get("required_fields"):
        outputs = [str(item).strip() for item in (spec.get("required_outputs") or []) if str(item).strip()]
        hydrated["required_fields"] = outputs or ["_time"]
    hydrated.setdefault("unresolved_slots", [])
    hydrated.setdefault("index", "")
    hydrated.setdefault("sourcetype", "")
    hydrated.setdefault("execution_eligible", False)
    hydrated.setdefault("governed", False)
    hydrated.setdefault("catalog_approved", False)
    return hydrated


def _pattern_adaptation_block(spec: dict[str, Any]) -> str:
    shot = select_vetted_authoring_pattern(spec)
    if not shot:
        return ""
    allowed = ", ".join(str(item) for item in (shot.get("allowed_adaptation_fields") or ()))
    prohibited = ", ".join(str(item) for item in (shot.get("prohibited_structural_changes") or ()))
    pattern_id = str(shot.get("pattern_id") or "")
    if pattern_id == "sequence":
        order = (
            "Order: retrieve EVENT_A OR EVENT_B (never implicit AND) -> sort by time -> "
            "prove EVENT_A burst inside WINDOW_A -> snapshot count/first/last -> "
            "streamstats last() carry -> later EVENT_B after last EVENT_A within FOLLOW_WINDOW -> "
            "requested stats/outputs."
        )
    elif pattern_id == "parent_child":
        order = (
            "Order: retrieve process events -> normalize parent/child/command-line roles -> "
            "require CHILD predicate on the child role AND PARENT predicate on the parent role "
            "on the SAME event -> stats by host and user while preserving parent/child/"
            "command line plus earliest/latest and count."
        )
    else:
        order = (
            "Order: combined retrieval span -> period=observation|baseline -> "
            "streamstats values(baseline_object) as baseline_objects by <subject> -> "
            "keep observation -> exact mvmap(baseline_objects, if(baseline_objects==<object>,1,0)) "
            "then seen_before=coalesce(max(exact_matches),0) where seen_before=0 "
            "(never mvfilter(A==B), never mvfind) -> "
            "requested stats/outputs."
        )
    return (
        f"\nSelected governed pattern: {shot.get('pattern_id')}. "
        "PRESERVE PATTERN TOPOLOGY; adapt only contract fields/filters/mappings/outputs.\n"
        f"{order}\n"
        f"Allowed: {allowed}. Prohibited: {prohibited}.\n"
    )


# ---------------------------------------------------------------------------
# Utility-authoring few-shots (prompt assets, shape-keyed).
#
# These extend the single pre-existing inline weekend example rather than
# starting a second store. Metadata (pattern_id, invariants, allowed
# adaptations) lives on these same dicts. ``few_shot_catalog_v1`` in
# ``app.llm.policy.examples`` is the hashed P8 identity catalog and is not
# extended here — adding FIRST_SEEN there would change production
# ``spl_advisory_generator`` ACTIVE prefix hashes.
# Selection reuses the deterministic ``analysis_shape`` from
# ``build_spl_intent_spec`` — the same key the shape rules already use — so
# exactly ONE example is rendered per call.
#
# Bodies are held as real dicts and rendered with ``json.dumps`` at prompt
# build time. That is deliberate: hand-written escapes drift, and the measured
# P3 failure was precisely an UNESCAPED double quote inside candidate_spl
# (``coalesce(..., "unknown")``), which under json_schema constrained decoding
# stalled the sampler into a 900+ character whitespace loop until max_tokens.
# Rendering through json.dumps means every example the model sees demonstrates
# correct \\" escaping.
# ---------------------------------------------------------------------------

_AUTHORING_FEW_SHOTS: dict[str, dict[str, Any]] = {
    # FS1 — basic filter + actor pattern. Also the fallback for unkeyed shapes.
    "raw": {
        "example_id": "fs.spl.authoring.basic_filter_actor",
        "request": "Show successful logons for accounts matching svc-* in the last 24 hours; return user, host, and source IP.",
        "note": (
            "Static field filters belong in the base search. Actor wildcards use "
            "field=value* in the search command; LIKE is an eval/where function and "
            "takes % wildcards, never *."
        ),
        "payload": {
            "status": "candidate_generated",
            "candidate_spl": (
                'search index=<index> sourcetype=<sourcetype> earliest=-24h latest=now '
                'EventCode=4624 user=svc-*\n'
                '| eval user_norm=lower(coalesce(user, "unknown"))\n'
                '| stats count as event_count by user_norm, host, src_ip'
            ),
            "index": "<index>",
            "sourcetype": "<sourcetype>",
            "result_cap": None,
            "unresolved_slots": ["index", "sourcetype"],
            "assumptions": ["<index>/<sourcetype> are review-only placeholders"],
            "required_fields": ["user", "host", "src_ip"],
        },
    },
    # FS2 — first-seen: compiler-vetted topology, generic subject/object (not P1 literals).
    "first_seen": {
        "example_id": "fs.spl.authoring.first_seen_preceding_baseline",
        "pattern_id": "first_seen",
        "pattern_enabled": True,
        "analysis_shape": "first_seen",
        "semantic_invariants": (
            "single_retrieval_horizon_covers_observation_plus_baseline",
            "period_observation_vs_baseline_on_time",
            "accumulate_baseline_objects_by_subject_via_streamstats",
            "keep_observation_events_only_after_accumulation",
            "exact_historical_absence_via_mvmap_eq_not_mvfilter_or_mvfind",
            "requested_aggregation_after_new_object_filter",
        ),
        "allowed_adaptation_fields": (
            "index",
            "sourcetype",
            "static_search_filters",
            "actor_prefix_like",
            "subject_field",
            "object_field",
            "observation_window",
            "baseline_window",
            "combined_horizon",
            "temporal_grain",
            "output_aliases",
            "requested_stats",
        ),
        "prohibited_structural_changes": (
            "collapse_observation_and_baseline",
            "change_streamstats_subject",
            "regex_membership_mvfind",
            "mvfilter_cross_field",
            "join_append_subsearch",
            "invent_algorithm",
            "arbitrary_head",
        ),
        "source_mapping_behaviour": "use_governed_bindings_when_supplied_else_placeholders",
        "required_validation_checks": (
            "retrieval_window",
            "baseline_observation_split",
            "same_subject_comparison",
            "exact_object_absence",
            "actor_prefix",
            "field_lineage",
            "_time_for_binning",
            "requested_outputs",
            "review_only",
        ),
        "request": (
            "Find destination ports contacted by a host in the last 1 day that the same host "
            "had not contacted during the preceding 7 days; return host, port, first seen."
        ),
        "note": (
            "Preserve this topology: one combined retrieval span, mark observation vs baseline, "
            "streamstats values(baseline_object) by the SAME subject, keep observation events, "
            "exact mvmap(baseline_objects, if(baseline_objects==object,1,0)) then "
            "seen_before=coalesce(max(exact_matches),0) where seen_before=0 "
            "(never mvfilter(A==B), never mvfind), then requested outputs. "
            "Copy structure only — every field, window, and filter must come from the contract."
        ),
        "payload": {
            "status": "candidate_generated",
            "candidate_spl": (
                'search index=<index> sourcetype=<sourcetype> earliest=-8d latest=now '
                '| eval subject_norm=lower(coalesce(host, "unknown")), '
                'object_norm=lower(coalesce(dest_port, "unknown")) '
                '| eval period=if(_time>=relative_time(now(),"-1d"),"observation","baseline") '
                '| eval baseline_object=if(period="baseline", object_norm, null()) '
                '| sort 0 + _time '
                '| streamstats values(baseline_object) as baseline_objects by subject_norm '
                '| where period="observation" '
                '| eval exact_matches=mvmap(baseline_objects, if(baseline_objects==object_norm,1,0)) '
                '| eval seen_before=coalesce(max(exact_matches),0) '
                '| where seen_before=0 '
                '| stats values(object_norm) as dest_port earliest(_time) as first_seen by subject_norm'
            ),
            "index": "<index>",
            "sourcetype": "<sourcetype>",
            "result_cap": None,
            "unresolved_slots": ["index", "sourcetype"],
            "assumptions": ["Observation 1d and baseline 7d share one -8d retrieval span"],
            "required_fields": ["host", "dest_port", "_time"],
        },
    },
    # FS3 — sequence: EVENT_A burst inside WINDOW_A, then later EVENT_B. Union, never AND.
    "sequence": {
        "example_id": "fs.spl.authoring.event_sequence",
        "pattern_id": "sequence",
        "pattern_enabled": True,
        "analysis_shape": "sequence",
        "semantic_invariants": (
            "retrieve_event_a_or_event_b_union",
            "order_by_subject_correlate_time",
            "prove_event_a_burst_inside_window_a",
            "snapshot_event_a_count_first_last",
            "carry_qualified_burst_forward",
            "event_b_after_last_event_a_within_follow_window",
            "correlate_subject_and_source_ip_only",
            "event_b_object_is_output_not_correlation_key",
        ),
        "allowed_adaptation_fields": (
            "index",
            "sourcetype",
            "event_a_predicate",
            "event_b_predicate",
            "subject_field",
            "correlate_ip_field",
            "window_a",
            "follow_window",
            "event_a_threshold",
            "output_aliases",
            "requested_stats",
        ),
        "prohibited_structural_changes": (
            "implicit_and_event_retrieval",
            "count_event_a_in_window_ending_at_event_b",
            "host_as_correlation_key",
            "reorder_event_a_after_event_b",
            "join_append_subsearch",
            "invent_algorithm",
            "arbitrary_head",
        ),
        "source_mapping_behaviour": "use_governed_bindings_when_supplied_else_placeholders",
        "required_validation_checks": (
            "event_union",
            "burst_window",
            "threshold_exclusive",
            "same_user_same_source",
            "success_after_burst",
            "follow_gap",
            "outputs",
            "review_only",
        ),
        "request": (
            "Find accounts with more than 5 event_a occurrences in 10 minutes followed by "
            "event_b within the next 30 minutes; return user, source IP, dest host, "
            "event_a count, first event_a time, event_b time."
        ),
        "note": (
            "Preserve this topology: retrieve EVENT_A OR EVENT_B (never juxtaposed AND), "
            "order by time, prove the EVENT_A burst inside WINDOW_A, snapshot count/first/last, "
            "carry that burst with streamstats last(), then match a later EVENT_B after last "
            "EVENT_A within FOLLOW_WINDOW. Correlate only subject + source IP. Destination host "
            "is an EVENT_B output. Copy structure only — predicates, windows, and threshold "
            "come from the contract."
        ),
        "payload": {
            "status": "candidate_generated",
            "candidate_spl": (
                'search index=<index> sourcetype=<sourcetype> earliest=-24h latest=now '
                '(event_a OR event_b)\n'
                '| eval subject_norm=lower(coalesce(user, "unknown")), '
                'correlate_ip=coalesce(src_ip, "unknown"), '
                'object_host=lower(coalesce(host, "unknown"))\n'
                '| eval event_type=case(event_a, "event_a", event_b, "event_b")\n'
                '| sort 0 + _time\n'
                '| streamstats time_window=10m count(eval(event_type="event_a")) as event_a_count '
                'min(eval(if(event_type="event_a", _time, null()))) as event_a_first '
                'max(eval(if(event_type="event_a", _time, null()))) as event_a_last '
                'by subject_norm, correlate_ip\n'
                '| streamstats last(eval(if(event_type="event_a" AND event_a_count>5, event_a_count, null()))) as burst_count '
                'last(eval(if(event_type="event_a" AND event_a_count>5, event_a_first, null()))) as burst_first '
                'last(eval(if(event_type="event_a" AND event_a_count>5, event_a_last, null()))) as burst_last '
                'by subject_norm, correlate_ip\n'
                '| where event_type="event_b" AND burst_count>5 AND _time>burst_last AND (_time-burst_last)<=1800\n'
                '| stats max(burst_count) as event_a_count min(burst_first) as first_event_a '
                'latest(_time) as event_b_time latest(object_host) as dest_host '
                'by subject_norm, correlate_ip\n'
                '| eval first_event_a=strftime(first_event_a,"%Y-%m-%d %H:%M:%S"), '
                'event_b_time=strftime(event_b_time,"%Y-%m-%d %H:%M:%S")\n'
                '| table subject_norm, correlate_ip, dest_host, event_a_count, first_event_a, event_b_time'
            ),
            "index": "<index>",
            "sourcetype": "<sourcetype>",
            "result_cap": None,
            "unresolved_slots": ["index", "sourcetype"],
            "assumptions": ["EVENT_A/EVENT_B predicates are adapted from the contract"],
            "required_fields": ["user", "src_ip", "host", "_time"],
        },
    },
    # FS4 — parent/child: same-event CHILD launched by PARENT, then stats.
    "parent_child": {
        "example_id": "fs.spl.authoring.parent_child",
        "pattern_id": "parent_child",
        "pattern_enabled": True,
        "analysis_shape": "parent_child",
        "semantic_invariants": (
            "retrieve_process_events",
            "normalize_parent_and_child_roles",
            "require_child_predicate_on_child_role",
            "require_parent_predicate_on_parent_role",
            "same_event_parent_and_child",
            "aggregate_by_host_and_user",
            "preserve_parent_child_command_line_through_stats",
            "earliest_and_latest_event_time",
        ),
        "allowed_adaptation_fields": (
            "index",
            "sourcetype",
            "child_predicate",
            "parent_predicate",
            "observation_window",
            "host_field",
            "user_field",
            "output_aliases",
            "requested_stats",
        ),
        "prohibited_structural_changes": (
            "invert_parent_child",
            "prove_child_only_in_command_line",
            "join_append_subsearch",
            "drop_outputs_in_stats",
            "eval_like_in_base_search",
            "invent_algorithm",
            "arbitrary_head",
        ),
        "source_mapping_behaviour": "use_governed_bindings_when_supplied_else_placeholders",
        "required_validation_checks": (
            "child_role",
            "parent_role",
            "same_event_relationship",
            "outputs",
            "review_only",
        ),
        "request": (
            "Find child.exe launched by parent_a.exe or parent_b.exe in the last 12 hours; "
            "group by host and user and return parent, child, command line, first seen, "
            "last seen, and event count."
        ),
        "note": (
            "Preserve this topology: retrieve process events, normalize parent/child/"
            "command-line roles, require the CHILD predicate on the child role AND the "
            "PARENT predicate on the parent role on the SAME event, then stats by host and "
            "user while preserving those outputs plus earliest/latest and count. Copy "
            "structure only — process names and windows come from the contract."
        ),
        "payload": {
            "status": "candidate_generated",
            "candidate_spl": (
                'search index=<index> sourcetype=<sourcetype> earliest=-12h latest=now\n'
                '| eval subject_host=lower(coalesce(host, "unknown")), '
                'subject_user=lower(coalesce(user, "unknown")), '
                'parent_process=coalesce(ParentImage, Parent_Process_Name, "unknown"), '
                'child_process=coalesce(Image, New_Process_Name, "unknown"), '
                'command_line=coalesce(CommandLine, "unknown")\n'
                '| where like(child_process, "%child.exe%") AND '
                '(like(parent_process, "%parent_a.exe%") OR like(parent_process, "%parent_b.exe%"))\n'
                '| stats count as event_count earliest(_time) as first_seen latest(_time) as last_seen '
                'values(parent_process) as parent_process values(child_process) as child_process '
                'values(command_line) as command_line by subject_host, subject_user\n'
                '| eval first_seen=strftime(first_seen,"%Y-%m-%d %H:%M:%S"), '
                'last_seen=strftime(last_seen,"%Y-%m-%d %H:%M:%S")\n'
                '| table subject_host, subject_user, parent_process, child_process, command_line, '
                'first_seen, last_seen, event_count'
            ),
            "index": "<index>",
            "sourcetype": "<sourcetype>",
            "result_cap": None,
            "unresolved_slots": ["index", "sourcetype"],
            "assumptions": ["parent_process/child_process carry the same-event process relationship"],
            "required_fields": ["host", "user", "parent_process", "child_process"],
        },
    },
    # FS5 — genuinely underspecified: ask, do not guess.
    "__clarification__": {
        "example_id": "fs.spl.authoring.clarification",
        "request": "Find the bad traffic on the usual box.",
        "note": (
            "When neither the detection condition nor the source can be resolved from the "
            "request, return needs_clarification with an EMPTY candidate_spl. Never invent "
            "a plausible-looking query to fill the gap."
        ),
        "payload": {
            "status": "needs_clarification",
            "candidate_spl": "",
            "index": "",
            "sourcetype": "",
            "result_cap": None,
            "unresolved_slots": ["index", "sourcetype"],
            "assumptions": ["No detection condition could be resolved from the request"],
            "required_fields": ["_time"],
            "clarifying_questions": [
                "Which host or asset should be searched?",
                "What behaviour counts as bad traffic here?",
            ],
        },
    },
}

#: Shapes that have no dedicated asset fall back to FS1.
_AUTHORING_FEW_SHOT_FALLBACK = "raw"


def _authoring_few_shot_block(spec: dict[str, Any]) -> str:
    """Render exactly ONE shape-relevant authoring example, or '' when unmapped."""
    shape = str((spec or {}).get("analysis_shape") or "").strip().lower()
    shot = _AUTHORING_FEW_SHOTS.get(shape) or _AUTHORING_FEW_SHOTS.get(
        _AUTHORING_FEW_SHOT_FALLBACK
    )
    if not shot:
        return ""
    payload = shot["payload"]
    if shot.get("pattern_enabled"):
        payload = {
            "status": str(payload.get("status") or "candidate_generated"),
            "candidate_spl": str(payload.get("candidate_spl") or ""),
        }
        body = json.dumps(payload, separators=(",", ":"))
    else:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    # The rule precedes the JSON deliberately: a rule placed after the example
    # reads as a footnote and the example gets copied instead of applied.
    return (
        f"\nWorked example for this SHAPE of request ({shot['example_id']}). "
        "Copy its STRUCTURE only — every index, field, value and window below must come "
        "from the actual request above, never from this example.\n"
        f"Rule for this shape: {shot['note']}\n"
        f"Example request: {shot['request']}\n"
        f"Example response: {body}\n"
    )


def _utility_authoring_system_append(*, context: dict[str, Any] | None = None) -> str:
    """Narrow utility-authoring guidance + weekend few-shot (not global authority constants)."""
    spec = (context or {}).get("semantic_analyst_intent") if isinstance(context, dict) else {}
    spec = spec if isinstance(spec, dict) else {}
    shape = str(spec.get("analysis_shape") or "")
    shape_rules = _shape_authoring_rules(spec)
    prefix = (
        "\n\nUniversal utility SPL authoring (review-only, template-free):\n"
        "- Draft a clean SPL block that matches the user's utility request exactly.\n"
        "- Preserve ALL semantic requirements from the analyst intent block (filters, grouping, ranking, time window).\n"
        "- Use index=<your_index> when no trusted index is provided; never invent company indexes.\n"
        f"{shape_rules}"
        "- Match earliest/latest to the requested search horizon; never overwrite an explicit window with 24h.\n"
        "- No inline // comments; no execution or findings claims.\n"
        "- Use %w (0=Sunday, 6=Saturday) for weekend filter logic; %A is display-only.\n"
    )
    prefix += _pattern_adaptation_block(spec)
    # candidate_spl is transported as a JSON string. The measured P3 failure was an
    # candidate_spl is transported as a JSON string. The measured P3 failure was an
    # unescaped inner double quote (coalesce(..., "unknown")): under json_schema
    # constrained decoding the sampler could not legally emit it and stalled into a
    # 900+ character whitespace run until max_tokens. State the rule explicitly and
    # let the rendered example demonstrate it.
    # Order matters: the worked example first, then the two hard transport rules
    # LAST so they are the most recent thing the model reads before generating.
    # Both were derived from measured stalls, not style preference.
    prefix += _authoring_few_shot_block(spec)
    prefix += (
        "\nTwo hard rules, applied after everything above:\n"
        '1. candidate_spl is a JSON string value. Escape every double quote inside it '
        'as \\" and every newline as \\n. A raw " inside candidate_spl is invalid and '
        "cannot be recovered.\n"
        "2. Keep every coalesce() to at most TWO source fields plus the quoted default, "
        'e.g. user_norm=lower(coalesce(user, Account_Name, \\"unknown\\")). The contract\'s '
        "normalization_aliases are still required — an unbounded alias list is not, and is "
        "the most common cause of an unfinished query.\n"
    )
    if shape in {"trend", "rolling", "sequence", "first_seen", "parent_child"}:
        return prefix
    return (
        prefix
        + "Weekend hour/day extraction few-shot:\n"
        '{"status": "candidate_generated", "confidence_score": 0.72, "confidence_label": "medium", '
        '"detection_family": "universal_timestamp_spl", "candidate_spl": "search index=<your_index> '
        "earliest=-24h latest=now\\n| eval hour_of_day=strftime(_time,\\\"%H\\\")\\n"
        '| eval day_of_week_num=strftime(_time,\\\"%w\\\")\\n'
        '| eval day_of_week=strftime(_time,\\\"%A\\\")\\n'
        '| where day_of_week_num IN (\\\"0\\\",\\\"6\\\")\\n'
        '| table _time hour_of_day day_of_week sourcetype host\\n| head 100", '
        '"index": "<your_index>", "sourcetype": "", "earliest": "-24h", "latest": "now", '
        '"time_window_hours": 24, "result_cap": 100, "unresolved_slots": ["sourcetype"], '
        '"assumptions": ["<your_index> is a placeholder index for review-only preview"], '
        '"required_fields": ["_time", "index"], "missing_details": [], '
        '"clarifying_questions": [], "validation_notes": ["Review-only utility draft"], '
        '"soc_std_rules_applied": ["coalesce_normalization"], "risk_notes": ["Not executed"], '
        '"execution_eligible": false, "governed": false, "catalog_approved": false}'
    )


def _shape_authoring_rules(spec: dict[str, Any]) -> str:
    shape = str(spec.get("analysis_shape") or "")
    prohibitions = {str(item) for item in (spec.get("prohibitions") or [])}
    lines = [
        "- Follow the immutable semantic contract. Do not reinterpret the analyst request.\n",
        "- Do not inject MITRE, remediation, routing, MCP execution, or unrelated alert templates.\n",
    ]
    grouped_by = [str(x) for x in (spec.get("grouped_by") or []) if str(x).strip()]
    required_outputs = [str(x) for x in (spec.get("required_outputs") or []) if str(x).strip()]
    wants_aggregate = bool(grouped_by) or any(
        token in " ".join(required_outputs).lower()
        for token in ("count", "first seen", "last seen", "first_seen", "last_seen")
    )
    if (shape == "raw" or "mandatory_aggregation" in prohibitions) and not wants_aggregate:
        lines.append("- Do not force stats/tstats aggregation; raw events were requested.\n")
    elif shape == "raw" and wants_aggregate:
        # A 'raw' shape that names group-by keys or first/last-seen/count outputs is an
        # aggregate request; telling the model not to aggregate contradicts the contract.
        lines.append(
            "- The request names grouping keys or aggregate outputs: use stats with those "
            "keys and return the requested aggregates.\n"
        )
    elif shape == "trend":
        lines.append("- Use timechart (or bin+_time+stats) with the declared temporal_grain. Do not emit a ranked top-N alert query.\n")
    elif shape == "rolling":
        lines.append("- Preserve the rolling analytical window with streamstats time_window= and the distinct relationship. Sort 0 _time before streamstats.\n")
    elif shape == "sequence":
        lines.append(
            "- Preserve ordered EVENT_A then EVENT_B. First prove the EVENT_A burst inside "
            "WINDOW_A and snapshot count/first/last, then carry that burst forward and match "
            "EVENT_B after last EVENT_A within FOLLOW_WINDOW. Correlate only by the contract "
            "subject and source IP. Destination host is an EVENT_B output, not a correlation key. "
            "Retrieve EVENT_A OR EVENT_B; never implicit AND.\n"
        )
    elif shape == "first_seen":
        lines.append(
            "- Preserve a separate observation window and a preceding baseline window. "
            "Compare per the same subject (account or host). Flag objects absent from that subject's baseline. "
            "Do not collapse both windows into one undivided search, and do not drop actor patterns.\n"
        )
    elif shape == "parent_child":
        lines.append(
            "- Preserve same-event parent-to-child process semantics. The child predicate belongs "
            "on the child-process role and the parent predicate belongs on the parent-process role. "
            "Do not invert them, and do not treat command-line text as proof of the child process. "
            "After filtering, stats by host and user while preserving parent, child, command line, "
            "earliest, latest, and count.\n"
        )
    elif shape == "ranking":
        lines.append("- When the analyst asks for top/ranked results, include stats aggregation, sort descending, then head only if a result_limit was requested.\n")
    else:
        lines.append("- When the analyst asks for top/ranked results, include stats aggregation, sort descending, then head.\n")
    if "arbitrary_head_100" in prohibitions or shape in {
        "trend",
        "rolling",
        "sequence",
        "first_seen",
        "parent_child",
    }:
        lines.append("- Do NOT add `head 100` arbitrarily; do not truncate time-series/rolling/sequence output.\n")
    else:
        lines.append("- When the analyst asks for ALL logs/events without a limit, do NOT add `head 100` arbitrarily.\n")
    if "unexpected_threshold_invention" in prohibitions:
        lines.append("- Do not invent count/severity thresholds that are not in the contract.\n")
    return "".join(lines)


def spl_advisory_prompts(
    user_query: str,
    *,
    utility_authoring: bool = False,
    correctness_mode: bool = False,
    context: dict[str, Any] | None = None,
    relevance_feedback: list[str] | None = None,
) -> tuple[str, str]:
    system_prompt = _system_prompt(correctness_mode=correctness_mode, context=context)
    if utility_authoring:
        system_prompt += _utility_authoring_system_append(context=context)
    user_prompt = _user_prompt(
        user_query,
        context=context,
        relevance_feedback=relevance_feedback,
    )
    return system_prompt, user_prompt


def _example_candidate_json(*, shape: str, skip_forced_head: bool) -> str:
    if skip_forced_head and shape == "trend":
        return (
            '{"status": "candidate_generated", "confidence_score": 0.72, "confidence_label": "medium", '
            '"detection_family": "failed_login_trend", "candidate_spl": "search index=<auth_index> sourcetype=<auth_sourcetype> '
            "earliest=-24h latest=now EventCode=4625\\n| timechart span=1h count as fail_count\", "
            '"index": "<auth_index>", "sourcetype": "<auth_sourcetype>", "earliest": "-24h", '
            '"latest": "now", "time_window_hours": 24, "result_cap": null, "unresolved_slots": [], '
            '"assumptions": ["<auth_index> is the authentication log index", '
            '"<auth_sourcetype> is the auth sourcetype"], '
            '"required_fields": ["EventCode", "index", "sourcetype"], "missing_details": [], '
            '"clarifying_questions": [], '
            '"validation_notes": ["Lab candidate only; execution_eligible forced false"], '
            '"soc_std_rules_applied": ["shift_left_filtering"], '
            '"risk_notes": ["Not governed; SOC review required"], "execution_eligible": false, '
            '"governed": false, "catalog_approved": false}'
        )
    if skip_forced_head and shape == "rolling":
        return (
            '{"status": "candidate_generated", "confidence_score": 0.72, "confidence_label": "medium", '
            '"detection_family": "rolling_distinct_accounts", "candidate_spl": "search index=<auth_index> sourcetype=<auth_sourcetype> '
            "earliest=-24h latest=now\\n| sort 0 _time\\n| streamstats time_window=10m dc(user) as distinct_count by src_ip\", "
            '"index": "<auth_index>", "sourcetype": "<auth_sourcetype>", "earliest": "-24h", '
            '"latest": "now", "time_window_hours": 24, "result_cap": null, "unresolved_slots": [], '
            '"assumptions": ["<auth_index> is the authentication log index"], '
            '"required_fields": ["src_ip", "user", "index", "sourcetype"], "missing_details": [], '
            '"clarifying_questions": [], '
            '"validation_notes": ["Lab candidate only; execution_eligible forced false"], '
            '"soc_std_rules_applied": ["shift_left_filtering"], '
            '"risk_notes": ["Not governed; SOC review required"], "execution_eligible": false, '
            '"governed": false, "catalog_approved": false}'
        )
    if skip_forced_head:
        return (
            '{"status": "candidate_generated", "confidence_score": 0.72, "confidence_label": "medium", '
            '"detection_family": "raw_events", "candidate_spl": "search index=<index> sourcetype=<sourcetype> '
            "earliest=-30d latest=now\\n| table _time src_ip dest_ip action\", "
            '"index": "<index>", "sourcetype": "<sourcetype>", "earliest": "-30d", '
            '"latest": "now", "time_window_hours": 720, "result_cap": null, "unresolved_slots": [], '
            '"assumptions": ["<index>/<sourcetype> are placeholders"], '
            '"required_fields": ["_time", "index", "sourcetype"], "missing_details": [], '
            '"clarifying_questions": [], '
            '"validation_notes": ["Lab candidate only; execution_eligible forced false"], '
            '"soc_std_rules_applied": ["shift_left_filtering"], '
            '"risk_notes": ["Not governed; SOC review required"], "execution_eligible": false, '
            '"governed": false, "catalog_approved": false}'
        )
    return (
        '{"status": "candidate_generated", "confidence_score": 0.72, "confidence_label": "medium", '
        '"detection_family": "windows_account_lockout", "candidate_spl": "search index=<auth_index> sourcetype=<auth_sourcetype> '
        "earliest=-60m latest=now action=failure | eval src_ip=coalesce(src_ip, src, source, "
        '"") | stats count as failed_logins by src_ip | sort -failed_logins | head 100", '
        '"index": "<auth_index>", "sourcetype": "<auth_sourcetype>", "earliest": "-60m", '
        '"latest": "now", "time_window_hours": 1, "result_cap": 100, "unresolved_slots": [], '
        '"assumptions": ["<auth_index> is the authentication log index", '
        '"<auth_sourcetype> is the auth sourcetype", "src_ip holds the client address"], '
        '"required_fields": ["src_ip", "action", "index", "sourcetype"], "missing_details": [], '
        '"clarifying_questions": [], '
        '"validation_notes": ["Lab candidate only; execution_eligible forced false"], '
        '"soc_std_rules_applied": ["shift_left_filtering", "coalesce_normalization"], '
        '"risk_notes": ["Not governed; SOC review required"], "execution_eligible": false, '
        '"governed": false, "catalog_approved": false}'
    )


def _system_prompt(correctness_mode: bool = False, context: dict[str, Any] | None = None) -> str:
    spec = (context or {}).get("semantic_analyst_intent") if isinstance(context, dict) else {}
    spec = spec if isinstance(spec, dict) else {}
    shape = str(spec.get("analysis_shape") or "")
    prohibitions = {str(item) for item in (spec.get("prohibitions") or [])}
    skip_forced_head = shape in {"trend", "rolling", "sequence", "first_seen", "parent_child"} or (
        "arbitrary_head_100" in prohibitions or "arbitrary_truncation" in prohibitions
    )
    skip_forced_stats = shape in {"raw", "sequence"} or "mandatory_aggregation" in prohibitions
    skip_family_catalog = bool(shape)
    if correctness_mode:
        datamodels = ", ".join(APPROVED_CIM_DATAMODELS)
        return (
            "You are the AI SOC SPL advisory fallback (lab candidate only — never governed, "
            "never catalog-approved, never executable). Return only valid JSON matching the provided schema. "
            "No markdown, no explanation outside JSON, no hidden reasoning, no scratchpad, no planning text, "
            "and no <think> tags.\n"
            f"{_correctness_engineering_block()}"
            "Decide whether the request is sufficiently specified. Return clarification questions when the "
            "required log source is unclear, fields required for logic are missing, or the user asks to "
            "execute or confirm results. Otherwise produce a placeholder-based lab candidate.\n"
            "The candidate_spl MUST:\n"
            "- query the data source the question is about (auth, network, DNS, endpoint, or firewall);\n"
            "- begin with `search index=<index> sourcetype=<sourcetype>` OR, when it answers the question "
            f"correctly and faster, `tstats ... from datamodel=<one of: {datamodels}>`;\n"
            "- include a time bound (`earliest=-<N>[mhd]` and `latest=now`, or tstats earliest/latest);\n"
            + (
                "- include aggregation only when the semantic contract analysis_shape requires it "
                "(trend/ranking/aggregation); raw and sequence requests must not be forced into stats;\n"
                if skip_forced_stats
                else
                "- ALWAYS include a `stats` (or timechart/tstats) aggregation grouping by the asked entity "
                "(user, host, src_ip, domain, ...) — the deterministic validator REJECTS any query without "
                "an aggregation, so a filter-only search is not acceptable;\n"
            )
            + (
                "- do NOT end with `head 100` unless the contract requested a result_limit; "
                "do not truncate trend/rolling/sequence/raw output;\n"
                if skip_forced_head
                else
                "- ALWAYS end with `head 100` — the validator REJECTS any query without a result limit;\n"
            )
            +
            "- NOT use: subsearches, macros, delete, collect, outputlookup, sendemail, rest, or any write "
            "command. (tstats/from/datamodel ARE allowed for the approved datamodels above.)\n"
            "confidence_score reflects source-profile completeness and field certainty. assumptions MUST list "
            "index/sourcetype placeholder meanings and field mappings; required_fields MUST list the Splunk "
            "fields the query depends on; index/sourcetype MUST mirror the candidate source placeholders or "
            "empty strings when unresolved; earliest/latest or time_window_hours MUST reflect the requested "
            "time bound; result_cap MUST be 100 unless the analyst requested a smaller cap; unresolved_slots "
            "MUST list unknown source/time fields and must not be guessed; execution_eligible, governed, and "
            "catalog_approved MUST be false.\n"
            'Example: {"status": "candidate_generated", "confidence_score": 0.7, "confidence_label": "medium", '
            '"detection_family": "dns_query_volume", "candidate_spl": "search index=<dns_index> '
            "sourcetype=<dns_sourcetype> earliest=-24h latest=now query=* | eval src_host_norm=lower(coalesce("
            'src_host, src_ip, "unknown")) | stats count as dns_query_count dc(query) as distinct_domains by '
            'src_host_norm | sort - dns_query_count | head 100", '
            '"index": "<dns_index>", "sourcetype": "<dns_sourcetype>", "earliest": "-24h", '
            '"latest": "now", "time_window_hours": 24, "result_cap": 100, "unresolved_slots": [], '
            '"assumptions": ["<dns_index>/<dns_sourcetype> are the DNS source"], '
            '"required_fields": ["src_ip", "query", "index", "sourcetype"], "missing_details": [], '
            '"clarifying_questions": [], "validation_notes": ["Lab candidate only"], '
            '"soc_std_rules_applied": ["coalesce_normalization"], "risk_notes": ["Not governed"], '
            '"execution_eligible": false, "governed": false, "catalog_approved": false}'
        )
    family_block = "" if skip_family_catalog else _detection_family_prompt()
    head_rule = (
        "- do NOT end with `head 100` unless the semantic contract requested a result_limit;\n"
        if skip_forced_head
        else
        "- end with `head 100`;\n"
    )
    return (
        "You are the AI SOC SPL advisory fallback (lab candidate only — never governed, "
        "never catalog-approved, never executable). Return only valid JSON matching the provided schema. "
        "No markdown, no explanation outside JSON, no hidden reasoning, no scratchpad, no planning text, "
        "and no <think> tags.\n"
        f"{_soc_std_spl_001_prompt_rules()}"
        f"{family_block}"
        f"{_maybe_spl_efficiency_block()}"
        "Decide whether the request is sufficiently specified. Return clarification questions when "
        "index/sourcetype cannot be safely placeholdered, the required log source is unclear, fields "
        "required for logic are missing, threshold/time window is unclear, asset zone definitions are "
        "missing, engineering workstation allowlist is missing, protocol/function-code mapping is missing, "
        "or the user asks to execute or confirm results. You may still produce a placeholder-based lab "
        "candidate if the question is clear enough for preview.\n"
        "The candidate_spl MUST:\n"
        "- begin with `search index=<index> sourcetype=<sourcetype>` using angle-bracket "
        "placeholders (do not hardcode environment-specific index or sourcetype values);\n"
        "- include `earliest=-<N>[mhd]` and `latest=now` when the contract supplies a search horizon;\n"
        "- use only: search, stats, where, table, fields, sort, dedup, rename, eval, "
        "timechart, bin, head, streamstats;\n"
        f"{head_rule}"
        "- NOT use: from, tstats, datamodel, subsearches, macros, delete, collect, "
        "outputlookup, sendemail, rest, or any write command.\n"
        "confidence_score must reflect source-profile completeness and field certainty. High confidence "
        "only when a known family maps clearly and key fields are present or safely placeholdered; medium "
        "when family is clear but source profile/field mapping is incomplete; low when family is uncertain "
        "or clarification is required. assumptions MUST list index/sourcetype placeholder meanings and "
        "field mappings. required_fields MUST list Splunk fields the query depends on. index/sourcetype "
        "MUST mirror the candidate source placeholders or empty strings when unresolved; earliest/latest "
        "or time_window_hours MUST reflect the requested time bound; "
        + (
            "result_cap MUST follow the contract (omit truncation when prohibited); "
            if skip_forced_head
            else
            "result_cap MUST be 100 unless the analyst requested a smaller cap; "
        )
        + "unresolved_slots MUST list unknown source/time fields and must "
        "not be guessed. execution_eligible, governed, and catalog_approved MUST be false.\n"
        + (
            ""
            if shape in _AUTHORING_FEW_SHOTS
            else ("Example output:\n" + _example_candidate_json(shape=shape, skip_forced_head=skip_forced_head))
        )
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
        bindings = context.get("deterministic_source_bindings")
        if isinstance(bindings, dict) and bindings:
            parts.append(
                "Deterministic source bindings (MUST NOT be overridden — use these exact values when present):"
            )
            for key, value in bindings.items():
                parts.append(f"- {key}: {value}")
            parts.append("")
        if context.get("review_only_posture"):
            parts.append(
                "Review-only SPL authoring: execution_eligible, governed, and catalog_approved MUST remain false."
            )
            parts.append("Do not invent unsupported index/sourcetype bindings; flag uncertain field mappings in assumptions.")
            parts.append("")
        semantic_text = context.get("semantic_analyst_intent_text")
        if isinstance(semantic_text, str) and semantic_text.strip():
            parts.append(semantic_text.strip())
            parts.append("")
        if context.get("do_not_reinterpret_request"):
            parts.append("Repair/generation scope: correct the candidate. Do NOT reinterpret the user request.")
            parts.append("")
        previous = context.get("previous_rejected_candidate")
        if isinstance(previous, str) and previous.strip():
            parts.append("Previous rejected candidate_spl:")
            parts.append(previous.strip())
            parts.append("")
        losses = context.get("deterministic_losses")
        if isinstance(losses, list) and losses:
            parts.append("Deterministic syntax/fidelity losses to correct (bounded):")
            parts.extend(f"- {item}" for item in losses[:16])
            parts.append("")
        if context.get("repair_scope"):
            parts.append(f"Bounded correction scope: {context['repair_scope']}")
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
    if _pattern_adaptation_requested(context if isinstance(context, dict) else None):
        parts.append(
            'Return only JSON with keys status and candidate_spl, for example '
            '{"status":"candidate_generated","candidate_spl":"search ..."}. '
            "No other keys. Escape double quotes inside candidate_spl. No markdown or reasoning text."
        )
    else:
        parts.append(
            "Return only JSON with keys status, confidence_score, confidence_label, detection_family, "
            "candidate_spl, index, sourcetype, earliest, latest, time_window_hours, result_cap, unresolved_slots, "
            "assumptions, required_fields, missing_details, clarifying_questions, validation_notes, "
            "soc_std_rules_applied, risk_notes, execution_eligible, governed, catalog_approved. No markdown or reasoning text."
        )
    return "\n".join(parts)
