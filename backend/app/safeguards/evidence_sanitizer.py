"""Recursive secret redaction for evidence and LLM prompt surfaces (Stage A1)."""

from __future__ import annotations

from typing import Any

from app.connectors.telemetry.redaction import is_secret_key, mask_secret_substrings

REDACTED = "[redacted]"


def redact_secret_values(value: str) -> str:
    return mask_secret_substrings(value)


def sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_secret_values(value)
    if isinstance(value, dict):
        return sanitize_mapping(value)
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    return value


def sanitize_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in mapping.items():
        if is_secret_key(str(key)):
            cleaned[str(key)] = REDACTED
            continue
        cleaned[str(key)] = sanitize_value(value)
    return cleaned


def secret_types_in(text: str) -> list[str]:
    found: list[str] = []
    lowered = text.lower()
    for label, marker in (
        ("bearer", "bearer "),
        ("jwt", "eyj"),
        ("pem", "-----begin"),
        ("api_key", "sk-"),
    ):
        if marker in lowered and label not in found:
            found.append(label)
    return found
