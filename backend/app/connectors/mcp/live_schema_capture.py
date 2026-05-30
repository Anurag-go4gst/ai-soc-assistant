"""Stage 3M-S5: Manual-only live Splunk MCP schema capture helpers (no CI / no production gate)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.connectors.mcp.splunk_result_adapter import adapt_mcp_search_payload

LIVE_CAPTURE_FLAG = "STAGE3M_S5_LIVE_MCP_CAPTURE"
DEFAULT_READ_ONLY_SPL = (
    "search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | stats count | head 5"
)
SECRET_PATTERNS = (
    re.compile(r"(?i)(bearer\s+[a-z0-9._-]+)"),
    re.compile(r"(?i)(api[_-]?key[\"']?\s*[:=]\s*[\"']?)[^\"'\s,}]+"),
    re.compile(r"(?i)(password[\"']?\s*[:=]\s*[\"']?)[^\"'\s,}]+"),
    re.compile(r"(?i)(token[\"']?\s*[:=]\s*[\"']?)[^\"'\s,}]+"),
)
SENSITIVE_FIELD_NAMES = frozenset(
    {"token", "api_key", "apikey", "password", "secret", "authorization", "auth"}
)


@dataclass(frozen=True)
class LiveCapturePreflight:
    ok: bool
    reason: str | None = None


@dataclass(frozen=True)
class LiveCaptureResult:
    ok: bool
    reason: str | None = None
    envelope_dict: dict[str, Any] | None = None
    redacted_raw_sample: dict[str, Any] | None = None


def preflight_live_capture(env: dict[str, str]) -> LiveCapturePreflight:
    flag = str(env.get(LIVE_CAPTURE_FLAG, "")).strip().lower()
    if flag not in {"1", "true", "yes"}:
        return LiveCapturePreflight(ok=False, reason="live_capture_flag_missing")

    endpoint = (
        str(env.get("STAGE3M_S5_MCP_ENDPOINT", "")).strip()
        or str(env.get("SPLUNK_MCP_BASE_URL", "")).strip()
    )
    if not endpoint:
        return LiveCapturePreflight(ok=False, reason="mcp_endpoint_missing")

    token = (
        str(env.get("STAGE3M_S5_MCP_TOKEN", "")).strip()
        or str(env.get("SPLUNK_MCP_TOKEN", "")).strip()
    )
    if not token:
        return LiveCapturePreflight(ok=False, reason="mcp_auth_missing")

    tool = str(env.get("STAGE3M_S5_MCP_TOOL", "")).strip() or "run_splunk_query"
    if tool not in {"run_splunk_query", "splunk_run_query"}:
        return LiveCapturePreflight(ok=False, reason="mcp_tool_not_allowlisted")

    return LiveCapturePreflight(ok=True)


def envelope_from_fixture_raw(raw_payload: dict[str, Any]) -> dict[str, Any]:
    """Map a captured or fixture raw payload through the production adapter shape."""
    envelope = adapt_mcp_search_payload(
        raw_payload,
        mcp_mode="splunk_mcp",
        trace_id="stage3m_s5_capture",
        normalized_spl=DEFAULT_READ_ONLY_SPL,
        duration_ms=int(raw_payload.get("duration_ms") or 0),
    )
    return envelope.to_dict()


def redact_capture_document(document: dict[str, Any]) -> dict[str, Any]:
    redacted = _redact_value(document)
    assert isinstance(redacted, dict)
    return redacted


def _redact_value(value: Any, field_name: str | None = None) -> Any:
    if isinstance(value, dict):
        return {key: _redact_value(item, key) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item, field_name) for item in value]
    if isinstance(value, str):
        if field_name and field_name.lower() in SENSITIVE_FIELD_NAMES:
            return "[REDACTED]"
        return _redact_string(value)
    return value


def _redact_string(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def build_capture_document(
    *,
    raw_payload: dict[str, Any],
    endpoint: str,
    tool_name: str,
    coe_reviewed: bool = False,
) -> dict[str, Any]:
    envelope_dict = envelope_from_fixture_raw(raw_payload)
    envelope_dict["schema_confirmed"] = bool(coe_reviewed)
    if not coe_reviewed:
        envelope_dict["schema_confirmed_reason"] = "real_schema_unverified"
    return {
        "stage": "3M-S5",
        "status": "captured_pending_coe_review",
        "schema_confirmed": envelope_dict["schema_confirmed"],
        "schema_confirmed_reason": envelope_dict["schema_confirmed_reason"],
        "mcp_endpoint_redacted": _redact_endpoint(endpoint),
        "tool_name": tool_name,
        "query_policy": {
            "read_only": True,
            "spl": DEFAULT_READ_ONLY_SPL,
            "row_cap": 100,
            "timeout_seconds": 30,
        },
        "redacted_raw_sample": redact_capture_document({"raw": raw_payload})["raw"],
        "splunk_result_envelope": envelope_dict,
        "coe_review_note": (
            "Set schema_confirmed=true only after COE signs this sample shape."
            if not coe_reviewed
            else "COE reviewed sample."
        ),
    }


def write_capture_file(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(redact_capture_document(document), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _redact_endpoint(endpoint: str) -> str:
    text = endpoint.replace("\n", " ")
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text[:240]
