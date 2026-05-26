from __future__ import annotations

import hashlib
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.llm.adapter.json_extractor import extract_first_json_object
from app.llm.adapter.role_registry import schema_for_role
from app.llm.adapter.schemas import AnalystResponseDraft, QueryUnderstandingCandidate, SplAdvisoryCandidate


class LLMAdapterResult(BaseModel):
    role: str
    parsed_ok: bool
    schema_valid: bool
    accepted: bool
    normalized_payload: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    dropped_fields: list[str] = Field(default_factory=list)
    disagreements: list[str] = Field(default_factory=list)
    raw_output_hash: str | None = None
    raw_output_redacted: str | None = None


def adapt_llm_output(
    *,
    role: str,
    raw_output: str,
    deterministic_context: dict[str, Any] | None = None,
    include_raw_output_redacted: bool = False,
) -> LLMAdapterResult:
    raw_hash = hashlib.sha256(raw_output.encode("utf-8")).hexdigest() if raw_output is not None else None
    raw_redacted = _redact_raw(raw_output) if include_raw_output_redacted else None
    warnings: list[str] = []
    errors: list[str] = []
    dropped_fields: list[str] = []
    disagreements: list[str] = []

    try:
        schema = schema_for_role(role)
    except ValueError as exc:
        return LLMAdapterResult(
            role=role,
            parsed_ok=False,
            schema_valid=False,
            accepted=False,
            warnings=[],
            errors=[str(exc)],
            raw_output_hash=raw_hash,
            raw_output_redacted=raw_redacted,
        )

    extraction = extract_first_json_object(raw_output)
    warnings.extend(extraction.warnings)
    errors.extend(extraction.errors)
    if not extraction.parsed_ok or extraction.payload is None:
        return LLMAdapterResult(
            role=role,
            parsed_ok=False,
            schema_valid=False,
            accepted=False,
            warnings=_dedupe(warnings),
            errors=_dedupe(errors),
            raw_output_hash=raw_hash,
            raw_output_redacted=raw_redacted,
        )

    dropped_fields = sorted(set(extraction.payload) - set(schema.model_fields))
    try:
        model = schema.model_validate(extraction.payload)
    except ValidationError as exc:
        return LLMAdapterResult(
            role=role,
            parsed_ok=True,
            schema_valid=False,
            accepted=False,
            warnings=_dedupe(warnings),
            errors=_validation_errors(exc),
            dropped_fields=dropped_fields,
            raw_output_hash=raw_hash,
            raw_output_redacted=raw_redacted,
        )

    normalized = model.model_dump()
    _apply_authority_overrides(role, model, normalized, deterministic_context or {}, warnings, disagreements)

    return LLMAdapterResult(
        role=role,
        parsed_ok=True,
        schema_valid=True,
        accepted=True,
        normalized_payload=normalized,
        warnings=_dedupe(warnings),
        errors=[],
        dropped_fields=dropped_fields,
        disagreements=_dedupe(disagreements),
        raw_output_hash=raw_hash,
        raw_output_redacted=raw_redacted,
    )


def _apply_authority_overrides(
    role: str,
    model: BaseModel,
    normalized: dict[str, Any],
    deterministic_context: dict[str, Any],
    warnings: list[str],
    disagreements: list[str],
) -> None:
    if isinstance(model, SplAdvisoryCandidate) and normalized.get("execution_eligible") is True:
        normalized["execution_eligible"] = False
        warnings.append("llm_execution_eligibility_ignored")
        disagreements.append("execution_eligible")

    if isinstance(model, QueryUnderstandingCandidate):
        deterministic_clarification = deterministic_context.get("clarification")
        if deterministic_clarification and normalized.get("clarification_needed") is False:
            normalized["clarification_needed"] = True
            normalized["clarification_question"] = deterministic_clarification.get("question") or normalized.get("clarification_question")
            warnings.append("llm_clarification_overridden")
            disagreements.append("clarification_needed")

    if isinstance(model, AnalystResponseDraft):
        deterministic_severity = deterministic_context.get("severity_label")
        if deterministic_severity and normalized.get("severity_label") and normalized.get("severity_label") != deterministic_severity:
            normalized["severity_label"] = deterministic_severity
            warnings.append("llm_severity_ignored")
            disagreements.append("severity_label")

        deterministic_mitre = {
            str(item.get("technique_id")): str(item.get("status"))
            for item in deterministic_context.get("mitre_mappings", [])
            if item.get("technique_id") and item.get("status")
        }
        for item in normalized.get("mitre_mappings") or []:
            technique_id = str(item.get("technique_id") or "")
            deterministic_status = deterministic_mitre.get(technique_id)
            if deterministic_status and item.get("status") != deterministic_status:
                item["status"] = deterministic_status
                warnings.append("llm_mitre_status_ignored")
                disagreements.append(f"mitre_status:{technique_id}")

        deterministic_refs = list(deterministic_context.get("sop_source_refs") or [])
        playbook = normalized.get("retrieved_playbook")
        if deterministic_refs and isinstance(playbook, dict):
            llm_refs = list(playbook.get("source_refs") or [])
            if llm_refs != deterministic_refs:
                playbook["source_refs"] = deterministic_refs
                warnings.append("llm_sop_citation_ignored")
                disagreements.append("sop_source_refs")

        allowed_actions = set(deterministic_context.get("allowed_actions") or [])
        unavailable_actions = set(deterministic_context.get("unavailable_actions") or [])
        blocked = set(normalized.get("blocked_actions") or [])
        accepted_actions = []
        action_warning = False
        for action in normalized.get("recommended_actions") or []:
            action_id = _action_id(action)
            if action_id in blocked or action_id in unavailable_actions or (allowed_actions and action_id not in allowed_actions):
                action_warning = True
                disagreements.append(f"action:{action_id}")
                continue
            accepted_actions.append(action)
        if action_warning:
            normalized["recommended_actions"] = accepted_actions
            warnings.append("llm_action_not_allowed")

    if role == "risk_rationale_reasoner":
        deterministic_severity = deterministic_context.get("severity_label")
        if deterministic_severity and normalized.get("selected_severity") != deterministic_severity:
            normalized["selected_severity"] = deterministic_severity
            warnings.append("llm_severity_ignored")
            disagreements.append("selected_severity")


def _action_id(action: Any) -> str:
    if isinstance(action, dict):
        action = action.get("action") or action.get("id") or action.get("name") or ""
    return str(action).strip()


def _validation_errors(exc: ValidationError) -> list[str]:
    messages = []
    for error in exc.errors():
        location = ".".join(str(item) for item in error.get("loc", ()))
        messages.append(f"{location}: {error.get('msg')}")
    return messages or ["schema_validation_failed"]


def _redact_raw(raw_output: str) -> str:
    redacted = re.sub(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*['\"]?[^'\"\\s,}]+", r"\1=<redacted>", raw_output)
    return redacted[:4000]


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
