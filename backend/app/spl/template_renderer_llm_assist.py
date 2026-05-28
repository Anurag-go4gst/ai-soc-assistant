"""Stage 3K-Q1D LLM-assist sidecar for template parameter extraction (Instruct only)."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any, Callable

from app.config import settings
from app.llm.adapter import adapt_llm_output
from app.llm.sidecar_governance import (
    REASONING_REJECTION_RENDERING,
    adapter_dropped_field_notes,
    build_advisory_disagreement,
    build_sidecar_metadata_payload,
    extract_advisory_confidence,
    resolve_sidecar_role_status,
    run_sidecar_llm_with_timeout,
)
from app.spl.template_registry import SplTemplateDefinition
from app.spl.template_renderer import (
    RenderResult,
    SPL_IN_VALUE_PATTERN,
    _valid_ip,
    render_template,
)

TEMPLATE_RENDER_PARAMETER_ASSIST_ROLE = "template_render_parameter_assist"
TEMPLATE_RENDER_ASSIST_TIMEOUT_SECONDS = 1.5

FORBIDDEN_EXTRACTION_KEYS = frozenset(
    {
        "template_id",
        "datamodel",
        "detection_ref",
        "lookup_name",
        "candidate_spl",
        "spl",
    }
)


def render_template_with_parameter_assist(
    template: SplTemplateDefinition,
    bound_params: dict[str, Any] | None = None,
    *,
    route_window: Any = None,
    user_query: str = "",
    shadow_enabled: bool | None = None,
    llm_raw_output_provider: Callable[[], str] | None = None,
) -> RenderResult:
    """Deterministic render first; optional Instruct parameter extraction when shadow on."""
    route_params = dict(bound_params or {})
    deterministic = render_template(template, route_params, route_window=route_window)

    shadow_on = settings.routing_llm_shadow_enabled if shadow_enabled is None else shadow_enabled
    if not shadow_on:
        return deterministic

    assist_invoked = llm_raw_output_provider is not None
    role_status = resolve_sidecar_role_status(
        TEMPLATE_RENDER_PARAMETER_ASSIST_ROLE,
        reasoning_rejection_reason=REASONING_REJECTION_RENDERING,
        assist_invoked=assist_invoked,
    )

    if role_status.rejected_reason:
        return replace(
            deterministic,
            llm_assist_enabled=True,
            parameter_extraction_llm=build_sidecar_metadata_payload(
                rejected_reason=role_status.rejected_reason,
            ),
        )

    if not assist_invoked:
        if role_status.llm_assist_skipped_reason:
            return replace(
                deterministic,
                llm_assist_enabled=False,
                parameter_extraction_llm=build_sidecar_metadata_payload(
                    skipped_reason=role_status.llm_assist_skipped_reason,
                ),
            )
        return replace(deterministic, llm_assist_enabled=False, parameter_extraction_llm=None)

    extracted, timed_out, notes, advisory_confidence = _fetch_extracted_parameters(
        user_query=user_query,
        llm_raw_output_provider=llm_raw_output_provider,
    )
    merged, merge_notes = _merge_parameters(route_params, extracted, template)
    disagreements = _parameter_disagreements(route_params, extracted)
    notes.extend(merge_notes)

    merged_result = render_template(template, merged, route_window=route_window)
    payload = None
    if extracted is not None or notes or timed_out or advisory_confidence is not None:
        payload = build_sidecar_metadata_payload(
            timed_out=timed_out,
            advisory_confidence=advisory_confidence,
            extra={
                "extracted_parameters": extracted,
                "adapter_notes": notes,
            },
        )

    return replace(
        merged_result,
        disagreements=disagreements,
        parameter_extraction_llm=payload,
        llm_assist_timed_out=timed_out,
        llm_assist_enabled=True,
    )


def sanitize_template_render_llm_payload(
    raw_output: str,
    *,
    template: SplTemplateDefinition | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    notes: list[str] = []
    result = adapt_llm_output(role=TEMPLATE_RENDER_PARAMETER_ASSIST_ROLE, raw_output=raw_output)
    if not result.accepted or not result.normalized_payload:
        if not result.schema_valid:
            notes.append("schema_invalid")
        notes.extend(result.errors)
        return None, notes

    notes.extend(
        adapter_dropped_field_notes(
            result.dropped_fields,
            forbidden_keys=FORBIDDEN_EXTRACTION_KEYS,
        )
    )

    extracted = result.normalized_payload.get("extracted_parameters")
    if not isinstance(extracted, dict):
        notes.append("schema_invalid")
        return None, notes

    sanitized, strip_notes = _sanitize_extracted_parameters(extracted, template=template)
    notes.extend(strip_notes)
    return {"extracted_parameters": sanitized} if sanitized else None, notes


def _fetch_extracted_parameters(
    *,
    user_query: str,
    llm_raw_output_provider: Callable[[], str],
) -> tuple[dict[str, Any] | None, bool, list[str], float | None]:
    call = run_sidecar_llm_with_timeout(
        llm_raw_output_provider,
        timeout_seconds=TEMPLATE_RENDER_ASSIST_TIMEOUT_SECONDS,
    )
    advisory_confidence, confidence_notes = (
        extract_advisory_confidence(
            call.raw_output or "",
            nested_paths=(("extracted_parameters",),),
        )
        if call.raw_output
        else (None, [])
    )
    if call.timed_out:
        return None, True, call.notes + confidence_notes, advisory_confidence

    payload, notes = sanitize_template_render_llm_payload(call.raw_output or "")
    notes.extend(confidence_notes)
    if payload is None:
        return None, False, notes, advisory_confidence
    return payload.get("extracted_parameters"), False, notes, advisory_confidence


def _sanitize_extracted_parameters(
    extracted: dict[str, Any],
    *,
    template: SplTemplateDefinition | None,
) -> tuple[dict[str, Any], list[str]]:
    notes: list[str] = []
    cleaned: dict[str, Any] = {}
    allowed = (
        set(template.optional_parameters) | set(template.required_parameters) | {"host", "user", "src_ip", "dest_ip", "result_limit", "time_window"}
        if template
        else {"host", "user", "src_ip", "dest_ip", "result_limit", "time_window"}
    )

    for key, value in extracted.items():
        if key in FORBIDDEN_EXTRACTION_KEYS:
            notes.append(f"forbidden_field_stripped:{key}")
            continue
        if key == "confidence":
            notes.append("confidence_advisory_only")
            continue
        if key not in allowed:
            notes.append(f"unknown_extraction_field:{key}")
            continue

        if value is None:
            continue

        if key == "time_window" and isinstance(value, dict):
            tw_notes = _sanitize_time_window(value)
            notes.extend(tw_notes)
            if tw_notes:
                continue
            cleaned["time_window"] = value
            continue

        if key == "result_limit":
            try:
                limit = int(value)
            except (TypeError, ValueError):
                notes.append("invalid_result_limit")
                continue
            if limit < 1 or limit > settings.spl_max_result_limit:
                notes.append("result_limit_exceeds_policy")
                continue
            cleaned["result_limit"] = limit
            continue

        if key in {"src_ip", "dest_ip"}:
            text = str(value)
            if SPL_IN_VALUE_PATTERN.search(text) or not _valid_ip(text):
                notes.append("spl_in_extraction_forbidden" if SPL_IN_VALUE_PATTERN.search(text) else "invalid_ip")
                continue
            cleaned[key] = text
            continue

        text = str(value)
        if SPL_IN_VALUE_PATTERN.search(text):
            notes.append("spl_in_extraction_forbidden")
            continue
        cleaned[key] = text

    return cleaned, notes


def _sanitize_time_window(value: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    earliest = value.get("earliest")
    latest = value.get("latest")
    if not isinstance(earliest, str) or not re.fullmatch(r"^earliest=-\d+[mhd]$", earliest):
        notes.append("invalid_time_window_earliest")
        return notes
    if not isinstance(latest, str) or latest != "latest=now":
        notes.append("invalid_time_window_latest")
        return notes
    if SPL_IN_VALUE_PATTERN.search(earliest) or SPL_IN_VALUE_PATTERN.search(latest):
        notes.append("spl_in_extraction_forbidden")
    return notes


def _merge_parameters(
    route_params: dict[str, Any],
    extracted: dict[str, Any] | None,
    template: SplTemplateDefinition,
) -> tuple[dict[str, Any], list[str]]:
    notes: list[str] = []
    if not extracted:
        return dict(route_params), notes

    merged: dict[str, Any] = {key: value for key, value in extracted.items() if value is not None}
    merged.update(route_params)

    time_window = extracted.get("time_window")
    if isinstance(time_window, dict) and "time_window" not in route_params:
        merged["earliest"] = time_window.get("earliest")
        merged["latest"] = time_window.get("latest")

    allowed = _allowed_keys(template)
    return {key: value for key, value in merged.items() if key in allowed or key in {"earliest", "latest"}}, notes


def _allowed_keys(template: SplTemplateDefinition) -> set[str]:
    return set(template.required_parameters) | set(template.optional_parameters) | {"result_limit", "host", "user", "src_ip", "dest_ip"}


def _parameter_disagreements(
    route_params: dict[str, Any],
    extracted: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not extracted:
        return []
    disagreements: list[dict[str, Any]] = []
    for key in ("result_limit", "host", "user", "src_ip", "dest_ip"):
        if key not in extracted or key not in route_params:
            continue
        if extracted[key] != route_params[key]:
            disagreements.append(
                build_advisory_disagreement(
                    field=key,
                    llm_value=extracted[key],
                    deterministic_value=route_params[key],
                    reason_for_deterministic_win="route_plan_parameter_authoritative",
                )
            )
    return disagreements
