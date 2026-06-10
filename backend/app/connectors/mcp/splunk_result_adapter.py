"""Stage 3M-S2: MCP search-result adapter → SplunkResultEnvelope (no live MCP I/O)."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Protocol

from app.connectors.mcp.splunk_result_envelope import (
    DEFAULT_PREVIEW_ROWS,
    SplunkResultEnvelope,
)
from app.connectors.mcp.splunk_result_fixture import envelope_from_fixture_payload
from app.safeguards.data_minimizer import minimize_context
from app.safeguards.mcp_result_safeguard import scan_mcp_preview_rows

_MINIMIZED_WARNING = "mcp_result_fields_minimized"


def sanitize_result_envelope(envelope: SplunkResultEnvelope) -> SplunkResultEnvelope:
    """Apply data minimization and injection scanning to envelope rows (T4.2).

    Runs at the adapter boundary so every downstream consumer of an envelope
    (execution gate, source evidence, demo fixtures) only ever sees minimized
    rows and an injection verdict in `warnings`. Rows are not rewritten on
    injection — the warning plus the source-evidence sensitivity flag drive
    the blocked-by-policy path; minimization only drops secret-bearing keys.
    """
    if not envelope.rows:
        return envelope

    original_rows = [dict(row) for row in envelope.rows]
    minimized_rows = [minimize_context(row) for row in original_rows]
    dropped_keys = {
        key
        for original, minimized in zip(original_rows, minimized_rows)
        for key in set(original) - set(minimized)
    }

    warnings = list(envelope.warnings)
    if dropped_keys and _MINIMIZED_WARNING not in warnings:
        warnings.append(_MINIMIZED_WARNING)
    _, _, scan_warnings = scan_mcp_preview_rows(minimized_rows)
    warnings.extend(item for item in scan_warnings if item not in warnings)

    if not dropped_keys and not scan_warnings:
        return envelope
    return replace(
        envelope,
        rows=tuple(minimized_rows),
        fields=tuple(field for field in envelope.fields if field not in dropped_keys),
        warnings=tuple(warnings),
    )


class SplunkMcpResultAdapter(Protocol):
    """Normalize raw MCP connector payloads into SplunkResultEnvelope."""

    def adapt_search_result(
        self,
        raw_payload: dict[str, Any],
        *,
        trace_id: str | None = None,
        normalized_spl: str | None = None,
        duration_ms: int | None = None,
    ) -> SplunkResultEnvelope:
        ...


class MockConnectorResultAdapter:
    """Mock/registry mock-mode connector payloads (schema unconfirmed)."""

    def adapt_search_result(
        self,
        raw_payload: dict[str, Any],
        *,
        trace_id: str | None = None,
        normalized_spl: str | None = None,
        duration_ms: int | None = None,
    ) -> SplunkResultEnvelope:
        payload = dict(raw_payload)
        if duration_ms is not None and payload.get("duration_ms") is None:
            payload["duration_ms"] = duration_ms
        return envelope_from_fixture_payload(
            payload,
            origin="mock_connector",
            trace_id=trace_id,
            normalized_spl=normalized_spl,
        )


class UnconfirmedRealMcpResultAdapter:
    """Hypothesis normalizer for future real MCP JSON — schema never confirmed in S2."""

    def adapt_search_result(
        self,
        raw_payload: dict[str, Any],
        *,
        trace_id: str | None = None,
        normalized_spl: str | None = None,
        duration_ms: int | None = None,
    ) -> SplunkResultEnvelope:
        payload = dict(raw_payload)
        if duration_ms is not None and payload.get("duration_ms") is None:
            payload["duration_ms"] = duration_ms
        base = envelope_from_fixture_payload(
            payload,
            origin="mock_connector",
            trace_id=trace_id,
            normalized_spl=normalized_spl,
        )
        extra_warnings = list(base.warnings)
        if "real_schema_unverified" not in extra_warnings:
            extra_warnings.append("real_schema_unverified")
        return replace(
            base,
            origin="real_mcp",
            schema_confirmed=False,
            schema_confirmed_reason="real_schema_unverified",
            provenance="ai_soc_unconfirmed_real_mcp_adapter_v1",
            warnings=tuple(extra_warnings),
        )


def get_splunk_result_adapter(mcp_mode: str) -> SplunkMcpResultAdapter:
    mode = (mcp_mode or "mock").strip().lower()
    if mode == "splunk_mcp":
        return UnconfirmedRealMcpResultAdapter()
    return MockConnectorResultAdapter()


def adapt_mcp_search_payload(
    raw_payload: dict[str, Any],
    *,
    mcp_mode: str,
    trace_id: str | None = None,
    normalized_spl: str | None = None,
    duration_ms: int | None = None,
) -> SplunkResultEnvelope:
    """Single entry point for execution gate: raw MCP dict → sanitized envelope."""
    envelope = get_splunk_result_adapter(mcp_mode).adapt_search_result(
        raw_payload,
        trace_id=trace_id,
        normalized_spl=normalized_spl,
        duration_ms=duration_ms,
    )
    return sanitize_result_envelope(envelope)


def execution_preview_from_envelope(
    envelope: SplunkResultEnvelope,
    *,
    preview_cap: int = DEFAULT_PREVIEW_ROWS,
) -> tuple[int, list[dict[str, Any]]]:
    """Map envelope to execution.result_count and results_preview (API-stable shape)."""
    preview = envelope.preview_rows(preview_cap)
    result_count = min(envelope.row_count, preview_cap)
    return result_count, preview
