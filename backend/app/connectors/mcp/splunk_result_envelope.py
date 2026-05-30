"""Stage 3M-S1: Internal Splunk MCP search result envelope (not /chat API schema)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

# Internal envelope safety limits — not claimed Splunk platform limits until COE validates real MCP schema.
DEFAULT_MAX_ROWS = 100
DEFAULT_PREVIEW_ROWS = 5
FIELD_CAP = 40
VALUE_CAP = 240

SplunkResultStatus = Literal["ok", "empty", "error", "timeout", "blocked"]
SplunkResultOrigin = Literal["fixture", "mock_connector", "real_mcp"]
SchemaConfirmedReason = Literal["fixture_adapter", "mock_payload", "real_schema_unverified"]
TruncationReason = Literal["row_limit", "timeout", "server_limit", "fixture_declared", "unknown"]

SENSITIVE_PATTERNS = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|credential|authorization)",
    re.IGNORECASE,
)

REDACTED_VALUE = "[REDACTED]"


@dataclass(frozen=True)
class SplunkResultEnvelope:
    status: SplunkResultStatus
    origin: SplunkResultOrigin
    schema_confirmed: bool
    schema_confirmed_reason: SchemaConfirmedReason
    row_count: int
    total_row_count: int | None
    truncated: bool
    truncation_reason: TruncationReason | None
    fields: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    duration_ms: int | None
    error_code: str | None
    error_message: str | None
    warnings: tuple[str, ...]
    provenance: str
    request_ref: str | None = None

    def preview_rows(self, limit: int = DEFAULT_PREVIEW_ROWS) -> list[dict[str, Any]]:
        cap = max(0, min(limit, len(self.rows)))
        return [dict(row) for row in self.rows[:cap]]

    def to_dict(self) -> dict[str, Any]:
        """Stable serialization for tests and future trace attachment."""
        return {
            "duration_ms": self.duration_ms,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "fields": list(self.fields),
            "origin": self.origin,
            "provenance": self.provenance,
            "request_ref": self.request_ref,
            "row_count": self.row_count,
            "rows": [dict(row) for row in self.rows],
            "schema_confirmed": self.schema_confirmed,
            "schema_confirmed_reason": self.schema_confirmed_reason,
            "status": self.status,
            "total_row_count": self.total_row_count,
            "truncated": self.truncated,
            "truncation_reason": self.truncation_reason,
            "warnings": list(self.warnings),
        }


def sanitize_rows(
    rows: Any,
    *,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> tuple[tuple[dict[str, Any], ...], bool, TruncationReason | None]:
    """Return sanitized rows, whether row_limit truncation was applied, and reason if so."""
    if not isinstance(rows, list):
        return (), False, None
    safe: list[dict[str, Any]] = []
    row_limit_hit = False
    for row in rows:
        if len(safe) >= max_rows:
            row_limit_hit = True
            break
        if not isinstance(row, dict):
            continue
        safe.append({_safe_key(str(key)): _safe_cell(key, value) for key, value in row.items()})
    reason: TruncationReason | None = "row_limit" if row_limit_hit else None
    return tuple(safe), row_limit_hit, reason


def derive_fields(rows: tuple[dict[str, Any], ...]) -> tuple[str, ...]:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    return tuple(fields[:FIELD_CAP])


def _safe_key(key: str) -> str:
    return key.replace("\n", " ")[:80]


def _safe_cell(key: str, value: Any) -> Any:
    if _is_sensitive_key(key):
        return REDACTED_VALUE
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    text = str(value).replace("\n", " ")
    if SENSITIVE_PATTERNS.search(text):
        return REDACTED_VALUE
    return text[:VALUE_CAP]


def _is_sensitive_key(key: str) -> bool:
    return bool(SENSITIVE_PATTERNS.search(key))


def _safe_text(value: str, max_len: int) -> str:
    return SENSITIVE_PATTERNS.sub(REDACTED_VALUE, value).replace("\n", " ")[:max_len]


def schema_reason_for_origin(origin: SplunkResultOrigin) -> SchemaConfirmedReason:
    if origin == "fixture":
        return "fixture_adapter"
    if origin == "mock_connector":
        return "mock_payload"
    return "real_schema_unverified"
