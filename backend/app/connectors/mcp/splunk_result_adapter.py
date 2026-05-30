"""Stage 3M-S2: MCP search-result adapter → SplunkResultEnvelope (no live MCP I/O)."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Protocol

from app.connectors.mcp.splunk_result_envelope import (
    DEFAULT_PREVIEW_ROWS,
    SplunkResultEnvelope,
)
from app.connectors.mcp.splunk_result_fixture import envelope_from_fixture_payload


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
    """Single entry point for execution gate: raw MCP dict → envelope."""
    return get_splunk_result_adapter(mcp_mode).adapt_search_result(
        raw_payload,
        trace_id=trace_id,
        normalized_spl=normalized_spl,
        duration_ms=duration_ms,
    )


def execution_preview_from_envelope(
    envelope: SplunkResultEnvelope,
    *,
    preview_cap: int = DEFAULT_PREVIEW_ROWS,
) -> tuple[int, list[dict[str, Any]]]:
    """Map envelope to execution.result_count and results_preview (API-stable shape)."""
    preview = envelope.preview_rows(preview_cap)
    result_count = min(envelope.row_count, preview_cap)
    return result_count, preview
