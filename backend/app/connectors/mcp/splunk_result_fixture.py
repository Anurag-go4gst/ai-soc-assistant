"""Stage 3M-S1: Fixture/mock-payload → SplunkResultEnvelope (no MCP I/O)."""

from __future__ import annotations

from typing import Any, Literal

from app.connectors.mcp.splunk_result_envelope import (
    DEFAULT_MAX_ROWS,
    VALUE_CAP,
    SplunkResultEnvelope,
    SplunkResultStatus,
    TruncationReason,
    derive_fields,
    sanitize_rows,
    schema_reason_for_origin,
    _safe_text,
)

FixtureOrigin = Literal["fixture", "mock_connector"]


def envelope_from_fixture_payload(
    payload: dict[str, Any],
    *,
    origin: FixtureOrigin = "fixture",
    max_rows: int = DEFAULT_MAX_ROWS,
    trace_id: str | None = None,
    normalized_spl: str | None = None,
) -> SplunkResultEnvelope:
    """Normalize a dict fixture (mock connector or demo shape) into SplunkResultEnvelope."""
    _ = normalized_spl  # reserved for future request_ref enrichment
    raw_status = str(payload.get("status") or "ok").lower()
    duration_ms = _optional_int(payload.get("duration_ms"))
    warnings: list[str] = ["fixture_payload"]

    request_ref = trace_id
    spl_hash = payload.get("spl_hash")
    if spl_hash is not None:
        request_ref = f"{trace_id or ''}:{spl_hash}".strip(":") or str(spl_hash)

    if raw_status in {"error", "failed", "failure"}:
        return _terminal_envelope(
            status="error",
            origin=origin,
            payload=payload,
            duration_ms=duration_ms,
            warnings=warnings,
            request_ref=request_ref,
        )

    if raw_status == "timeout":
        return _terminal_envelope(
            status="timeout",
            origin=origin,
            payload=payload,
            duration_ms=duration_ms,
            warnings=warnings + ["search_timeout"],
            request_ref=request_ref,
            truncation_reason="timeout",
        )

    if raw_status == "blocked":
        return _terminal_envelope(
            status="blocked",
            origin=origin,
            payload=payload,
            duration_ms=duration_ms,
            warnings=warnings,
            request_ref=request_ref,
        )

    raw_rows = payload.get("rows", [])
    sanitized, row_limit_hit, row_limit_reason = sanitize_rows(raw_rows, max_rows=max_rows)
    row_count = len(sanitized)

    total_row_count = _optional_int(payload.get("total_row_count"))
    if total_row_count is None:
        reported = _optional_int(payload.get("row_count"))
        if reported is not None and reported > row_count:
            total_row_count = reported
        elif isinstance(raw_rows, list) and len(raw_rows) > row_count:
            total_row_count = len(raw_rows)

    fixture_truncated = bool(payload.get("truncated"))
    truncated = fixture_truncated or (
        total_row_count is not None and total_row_count > row_count
    ) or row_limit_hit

    truncation_reason = _resolve_truncation_reason(
        payload=payload,
        fixture_truncated=fixture_truncated,
        row_limit_hit=row_limit_hit,
        row_limit_reason=row_limit_reason,
        raw_status=raw_status,
    )

    if truncated and "rows_truncated" not in warnings:
        warnings.append("rows_truncated")

    if row_count == 0 and raw_status in {"ok", "success", ""}:
        return SplunkResultEnvelope(
            status="empty",
            origin=origin,
            schema_confirmed=False,
            schema_confirmed_reason=schema_reason_for_origin(origin),
            row_count=0,
            total_row_count=total_row_count if total_row_count else 0,
            truncated=False,
            truncation_reason=None,
            fields=(),
            rows=(),
            duration_ms=duration_ms,
            error_code=None,
            error_message=None,
            warnings=tuple(warnings + ["zero_rows_normalized_to_empty"]),
            provenance="ai_soc_fixture_adapter_v1",
            request_ref=request_ref,
        )

    return SplunkResultEnvelope(
        status="ok",
        origin=origin,
        schema_confirmed=False,
        schema_confirmed_reason=schema_reason_for_origin(origin),
        row_count=row_count,
        total_row_count=total_row_count,
        truncated=truncated,
        truncation_reason=truncation_reason if truncated else None,
        fields=derive_fields(sanitized),
        rows=sanitized,
        duration_ms=duration_ms,
        error_code=None,
        error_message=None,
        warnings=tuple(warnings),
        provenance="ai_soc_fixture_adapter_v1",
        request_ref=request_ref,
    )


def _terminal_envelope(
    *,
    status: SplunkResultStatus,
    origin: FixtureOrigin,
    payload: dict[str, Any],
    duration_ms: int | None,
    warnings: list[str],
    request_ref: str | None,
    truncation_reason: TruncationReason | None = None,
) -> SplunkResultEnvelope:
    error_code = _safe_text(str(payload.get("error_code") or payload.get("error") or status), 80)
    error_message = _safe_text(str(payload.get("error_message") or payload.get("error") or ""), VALUE_CAP)
    return SplunkResultEnvelope(
        status=status,
        origin=origin,
        schema_confirmed=False,
        schema_confirmed_reason=schema_reason_for_origin(origin),
        row_count=0,
        total_row_count=0,
        truncated=False,
        truncation_reason=truncation_reason,
        fields=(),
        rows=(),
        duration_ms=duration_ms,
        error_code=error_code or status,
        error_message=error_message or None,
        warnings=tuple(warnings),
        provenance="ai_soc_fixture_adapter_v1",
        request_ref=request_ref,
    )


def _resolve_truncation_reason(
    *,
    payload: dict[str, Any],
    fixture_truncated: bool,
    row_limit_hit: bool,
    row_limit_reason: TruncationReason | None,
    raw_status: str,
) -> TruncationReason:
    explicit = payload.get("truncation_reason")
    allowed = {"row_limit", "timeout", "server_limit", "fixture_declared", "unknown"}
    if isinstance(explicit, str) and explicit in allowed:
        return explicit  # type: ignore[return-value]
    if fixture_truncated:
        return "fixture_declared"
    if raw_status == "timeout":
        return "timeout"
    if row_limit_hit and row_limit_reason:
        return row_limit_reason
    if row_limit_hit:
        return "row_limit"
    return "unknown"


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
