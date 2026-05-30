"""Stage 3M-S3: Experience Center demo rows → SplunkResultEnvelope (no MCP I/O)."""

from __future__ import annotations

from typing import Any

from app.connectors.mcp.splunk_result_adapter import execution_preview_from_envelope
from app.connectors.mcp.splunk_result_envelope import DEFAULT_PREVIEW_ROWS, SplunkResultEnvelope
from app.connectors.mcp.splunk_result_fixture import envelope_from_fixture_payload


def demo_envelope_from_rows(
    rows: list[dict[str, Any]],
    *,
    trace_id: str | None = None,
    normalized_spl: str | None = None,
    duration_ms: int = 7,
) -> SplunkResultEnvelope:
    """Normalize COE synthetic Splunk rows through the same fixture adapter as production mock path."""
    return envelope_from_fixture_payload(
        {
            "status": "ok",
            "rows": rows,
            "row_count": len(rows),
            "duration_ms": duration_ms,
        },
        origin="fixture",
        trace_id=trace_id,
        normalized_spl=normalized_spl,
    )


def apply_envelope_to_splunk_evidence(
    item: dict[str, Any],
    envelope: SplunkResultEnvelope,
    *,
    preview_cap: int = DEFAULT_PREVIEW_ROWS,
) -> None:
    """Rewrite splunk_mcp demo evidence fields from envelope (internal normalization only)."""
    item["preview_rows"] = envelope.preview_rows(preview_cap)
    item["fields_returned"] = list(envelope.fields)
    item["result_count"] = envelope.row_count
    warnings = list(item.get("warnings", []))
    for warning in envelope.warnings:
        if warning not in warnings:
            warnings.append(warning)
    schema_token = f"schema_unconfirmed:{envelope.schema_confirmed_reason}"
    if schema_token not in warnings:
        warnings.append(schema_token)
    item["warnings"] = warnings


def execution_fields_from_envelope(
    envelope: SplunkResultEnvelope,
    *,
    preview_cap: int = DEFAULT_PREVIEW_ROWS,
) -> tuple[int, list[dict[str, Any]], dict[str, Any]]:
    """Map envelope to execution.result_count, results_preview, splunk_result_envelope."""
    result_count, preview = execution_preview_from_envelope(envelope, preview_cap=preview_cap)
    return result_count, preview, envelope.to_dict()
