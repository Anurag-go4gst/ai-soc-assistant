from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class JsonExtractionResult:
    parsed_ok: bool
    payload: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def extract_first_json_object(raw_output: str | None) -> JsonExtractionResult:
    if raw_output is None or not raw_output.strip():
        return JsonExtractionResult(parsed_ok=False, errors=["empty_output"])

    text = raw_output.strip()
    warnings: list[str] = []
    fenced = "```" in text
    if fenced:
        warnings.append("json_extracted_from_markdown_fence")

    span = _first_balanced_object(text)
    if span is None:
        return JsonExtractionResult(parsed_ok=False, warnings=warnings, errors=["no_balanced_json_object"])

    start, end = span
    if _has_non_fence_content(text[:start]):
        warnings.append("prose_before_json_ignored")
    if _has_non_fence_content(text[end:]):
        warnings.append("prose_after_json_ignored")
    if _first_balanced_object(text[end:]) is not None:
        warnings.append("multiple_json_objects_first_used")

    try:
        parsed = json.loads(text[start:end])
    except json.JSONDecodeError:
        return JsonExtractionResult(parsed_ok=False, warnings=warnings, errors=["malformed_json"])
    if not isinstance(parsed, dict):
        return JsonExtractionResult(parsed_ok=False, warnings=warnings, errors=["json_value_not_object"])
    return JsonExtractionResult(parsed_ok=True, payload=parsed, warnings=_dedupe(warnings), errors=[])


def _first_balanced_object(text: str) -> tuple[int, int] | None:
    start: int | None = None
    depth = 0
    in_string = False
    escape = False

    for index, char in enumerate(text):
        if start is None:
            if char == "{":
                start = index
                depth = 1
            continue

        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
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
                return start, index + 1
    return None


def _has_non_fence_content(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    stripped = stripped.replace("```json", "").replace("```JSON", "").replace("```", "").strip()
    return bool(stripped)


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
