"""Tolerant LLM JSON output pre-processor (plan 1.1).

Shared pipeline: fence/prose tolerance → JSON extraction → schema-aware repair →
optional single retry. Never repairs or synthesizes SPL / raw query strings.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from app.llm.adapter.json_extractor import extract_first_json_object

BRIDGE_PROPOSAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "steps": {"type": "array"},
        "rationale": {"type": "string"},
    },
    "required": ["steps"],
}

INVESTIGATION_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "objectives": {"type": "array"},
        "hypotheses": {"type": "array"},
        "evidence_needed": {"type": "array"},
        "data_categories": {"type": "array"},
        "rag_sufficient": {"type": "boolean"},
        "env_kb_needed": {"type": "boolean"},
        "discovery_needed": {"type": "boolean"},
        "read_only_tools": {"type": "array"},
        "safe_spl_templates": {"type": "array"},
        "spl_review_requested": {"type": "boolean"},
        "clarification_needed": {"type": "boolean"},
        "clarification_questions": {"type": "array"},
        "refinement_recommended": {"type": "boolean"},
        "rationale": {"type": "string"},
    },
    "required": ["hypotheses", "evidence_needed"],
}

INTENT_ADVISORY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "paraphrase_detected": {"type": "boolean"},
        "spl_authoring_request": {"type": "boolean"},
        "llm_called": {"type": "boolean"},
        "requires_source_profile": {"type": "boolean"},
    },
}

_SPL_FORBIDDEN_KEYS = frozenset(
    {
        "spl",
        "search_query",
        "query",
        "raw_spl",
        "search",
        "candidate_spl",
        "normalized_spl",
    }
)
_TRUE_TOKENS = {"true", "yes", "y", "1", "t"}
_FALSE_TOKENS = {"false", "no", "n", "0", "f", "", "n/a", "na", "none", "null"}
_TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")


@dataclass(frozen=True)
class PreprocessResult:
    payload: dict[str, Any] | None
    verdict: str
    repairs: list[str] = field(default_factory=list)
    extraction_warnings: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)

    @property
    def llm_output_utilization(self) -> str:
        """Scorecard-compatible utilization label."""
        return utilization_verdict(self)


def utilization_verdict(result: PreprocessResult) -> str:
    if result.verdict in {"used", "repaired_used", "retried_used"}:
        return "used"
    if result.verdict.startswith("dropped:"):
        return result.verdict
    return "dropped:unknown"


def preprocess_llm_output(
    raw: str,
    schema: dict[str, Any],
    *,
    allow_retry: bool = False,
    retry_fn: Callable[[list[str]], str | None] | None = None,
    echo_of: str | None = None,
) -> PreprocessResult:
    """Parse and validate model JSON output with tolerant repair."""
    result = _preprocess_once(raw, schema, echo_of=echo_of)
    if result.payload is not None:
        return result
    if allow_retry and retry_fn is not None and result.validation_errors:
        retry_raw = retry_fn(result.validation_errors)
        if isinstance(retry_raw, str) and retry_raw.strip():
            retried = _preprocess_once(retry_raw, schema, echo_of=echo_of)
            if retried.payload is not None:
                repairs = [*result.repairs, *retried.repairs, "retry_attempted"]
                return PreprocessResult(
                    payload=retried.payload,
                    verdict="retried_used",
                    repairs=repairs,
                    extraction_warnings=[*result.extraction_warnings, *retried.extraction_warnings],
                    validation_errors=[],
                )
            return PreprocessResult(
                payload=None,
                verdict="dropped:retry_failed",
                repairs=repairs,
                extraction_warnings=[*result.extraction_warnings, *retried.extraction_warnings],
                validation_errors=retried.validation_errors,
            )
    return result


def _preprocess_once(raw: str, schema: dict[str, Any], *, echo_of: str | None) -> PreprocessResult:
    repairs: list[str] = []
    text = (raw or "").strip()
    if not text:
        return PreprocessResult(payload=None, verdict="dropped:empty_output", validation_errors=["empty_output"])

    if echo_of and _is_echo_of_input(text, echo_of):
        return PreprocessResult(
            payload=None,
            verdict="dropped:echo_of_input",
            validation_errors=["echo_of_input"],
        )

    extraction, parse_repairs = _extract_with_repair(text)
    repairs.extend(parse_repairs)
    if not extraction.parsed_ok or not isinstance(extraction.payload, dict):
        reason = extraction.errors[0] if extraction.errors else "malformed_json"
        verdict = "dropped:truncated" if reason == "no_balanced_json_object" else f"dropped:{reason}"
        return PreprocessResult(
            payload=None,
            verdict=verdict,
            extraction_warnings=list(extraction.warnings),
            validation_errors=list(extraction.errors) or [reason],
        )

    payload = dict(extraction.payload)
    repaired_payload, repair_notes = _repair_payload(payload, schema)
    repairs.extend(repair_notes)

    validation_errors = _validate_against_schema(repaired_payload, schema)
    if validation_errors:
        return PreprocessResult(
            payload=None,
            verdict=f"dropped:schema_invalid",
            repairs=repairs,
            extraction_warnings=list(extraction.warnings),
            validation_errors=validation_errors,
        )

    verdict = "repaired_used" if repairs else "used"
    return PreprocessResult(
        payload=repaired_payload,
        verdict=verdict,
        repairs=repairs,
        extraction_warnings=list(extraction.warnings),
        validation_errors=[],
    )


def _extract_with_repair(text: str) -> tuple[Any, list[str]]:
    repairs: list[str] = []
    for candidate in (text, _repair_json_text(text)):
        result = extract_first_json_object(candidate)
        if result.parsed_ok and isinstance(result.payload, dict):
            if candidate != text:
                repairs.append("trailing_comma_repaired")
            return result, repairs
    return extract_first_json_object(text), repairs


def _is_echo_of_input(raw: str, echo_of: str) -> bool:
    query = echo_of.strip().lower()
    if not query:
        return False
    stripped = raw.strip().lower()
    if stripped == query:
        return True
    if stripped.startswith(query) and "{" not in stripped:
        return True
    return False


def _repair_json_text(text: str) -> str:
    return _TRAILING_COMMA_RE.sub(r"\1", text)


def _repair_payload(payload: dict[str, Any], schema: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    repairs: list[str] = []
    out = dict(payload)
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}

    for key, prop in properties.items():
        if key not in out or key in _SPL_FORBIDDEN_KEYS:
            continue
        if not isinstance(prop, dict):
            continue
        value = out[key]
        enum_values = prop.get("enum")
        if isinstance(enum_values, list) and isinstance(value, str):
            lowered = value.strip().lower()
            for option in enum_values:
                if str(option).lower() == lowered:
                    if value != option:
                        out[key] = option
                        repairs.append(f"enum_case_normalized:{key}")
                    break

        expected_type = prop.get("type")
        if expected_type == "boolean" and not isinstance(value, bool):
            coerced = _coerce_bool(value)
            if coerced is not None:
                out[key] = coerced
                repairs.append(f"coerced_bool:{key}")
        elif expected_type == "integer" and not isinstance(value, int):
            try:
                out[key] = int(value)
                repairs.append(f"coerced_int:{key}")
            except (TypeError, ValueError):
                pass
        elif expected_type == "number" and not isinstance(value, (int, float)):
            try:
                out[key] = float(value)
                repairs.append(f"coerced_number:{key}")
            except (TypeError, ValueError):
                pass
        elif expected_type == "array" and not isinstance(value, list):
            if value is None:
                out[key] = []
                repairs.append(f"coerced_array:{key}")

    return out, repairs


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        token = value.strip().lower()
        if token in _TRUE_TOKENS:
            return True
        if token in _FALSE_TOKENS:
            return False
    return None


def _validate_against_schema(payload: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = schema.get("required") if isinstance(schema.get("required"), list) else []
    for key in required:
        if key not in payload or payload.get(key) is None:
            errors.append(f"missing_required:{key}")

    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    for key, prop in properties.items():
        if key not in payload or key in _SPL_FORBIDDEN_KEYS:
            continue
        if not isinstance(prop, dict):
            continue
        value = payload[key]
        enum_values = prop.get("enum")
        if isinstance(enum_values, list) and value is not None and value not in enum_values:
            errors.append(f"enum_mismatch:{key}")

        expected_type = prop.get("type")
        if expected_type == "string" and value is not None and not isinstance(value, str):
            errors.append(f"type_mismatch:{key}")
        elif expected_type == "boolean" and value is not None and not isinstance(value, bool):
            errors.append(f"type_mismatch:{key}")
        elif expected_type == "integer" and value is not None and not isinstance(value, int):
            errors.append(f"type_mismatch:{key}")
        elif expected_type == "array" and value is not None and not isinstance(value, list):
            errors.append(f"type_mismatch:{key}")

        if key in _SPL_FORBIDDEN_KEYS and value:
            errors.append(f"forbidden_spl_field:{key}")

    return errors


def preprocess_with_trailing_comma_repair(raw: str) -> dict[str, Any] | None:
    """Legacy helper: extract + trailing-comma repair only (no schema)."""
    extraction = extract_first_json_object(raw)
    if extraction.parsed_ok and isinstance(extraction.payload, dict):
        return extraction.payload
    span_text = _repair_json_text(raw or "")
    try:
        parsed = json.loads(span_text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
