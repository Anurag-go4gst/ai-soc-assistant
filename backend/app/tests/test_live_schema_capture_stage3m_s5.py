"""Stage 3M-S5: Live MCP schema capture harness (no network)."""

from __future__ import annotations

import json

from app.connectors.mcp.live_schema_capture import (
    LIVE_CAPTURE_FLAG,
    build_capture_document,
    envelope_from_fixture_raw,
    preflight_live_capture,
    redact_capture_document,
)


def test_missing_live_flag_blocks_capture() -> None:
    result = preflight_live_capture({})
    assert result.ok is False
    assert result.reason == "live_capture_flag_missing"


def test_missing_endpoint_blocks_capture() -> None:
    result = preflight_live_capture({LIVE_CAPTURE_FLAG: "true", "SPLUNK_MCP_TOKEN": "secret"})
    assert result.ok is False
    assert result.reason == "mcp_endpoint_missing"


def test_missing_auth_blocks_capture() -> None:
    result = preflight_live_capture(
        {LIVE_CAPTURE_FLAG: "true", "STAGE3M_S5_MCP_ENDPOINT": "https://splunk-mcp.example/mcp"}
    )
    assert result.ok is False
    assert result.reason == "mcp_auth_missing"


def test_preflight_passes_with_required_env() -> None:
    result = preflight_live_capture(
        {
            LIVE_CAPTURE_FLAG: "true",
            "STAGE3M_S5_MCP_ENDPOINT": "https://splunk-mcp.example/mcp",
            "STAGE3M_S5_MCP_TOKEN": "secret-token",
            "STAGE3M_S5_MCP_TOOL": "run_splunk_query",
        }
    )
    assert result.ok is True


def test_fixture_raw_maps_to_envelope_schema_unconfirmed() -> None:
    raw = {
        "status": "ok",
        "rows": [{"user": "svc_app", "count": 1}],
        "row_count": 1,
        "duration_ms": 12,
    }
    envelope = envelope_from_fixture_raw(raw)
    assert envelope["schema_confirmed"] is False
    assert envelope["schema_confirmed_reason"] == "real_schema_unverified"
    assert envelope["origin"] == "real_mcp"
    assert envelope["row_count"] == 1


def test_capture_document_keeps_schema_unconfirmed_until_coe() -> None:
    doc = build_capture_document(
        raw_payload={"status": "ok", "rows": [], "row_count": 0},
        endpoint="https://splunk-mcp.example/mcp",
        tool_name="run_splunk_query",
        coe_reviewed=False,
    )
    assert doc["schema_confirmed"] is False
    assert "pending_coe_review" in doc["status"]


def test_redaction_strips_secrets() -> None:
    redacted = redact_capture_document(
        {
            "token": "Bearer abcdef123456",
            "nested": {"api_key": "super-secret"},
        }
    )
    blob = json.dumps(redacted)
    assert "abcdef123456" not in blob
    assert "super-secret" not in blob
    assert "[REDACTED]" in blob
