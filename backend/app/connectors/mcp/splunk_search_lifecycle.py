"""Step 3 — Splunk search job lifecycle (submit → bounded poll → fetch).

Splunk searches exceed normal HTTP timeouts, so the live connector cannot treat
`splunk_run_query` as one synchronous round-trip. This module drives the job
lifecycle internally: the execution gate calls `call_tool` once; the connector
submits a job, polls within bounded limits, and fetches the final rows. Poll
count and wall time are capped and are NOT new investigation calls.

Pure and transport-agnostic: the actual HTTP/MCP transport is injected as a
`SearchTransport`, and `sleep`/`monotonic` are injectable, so the full state
machine is unit-testable without a live server. The returned dict matches the
raw-payload shape `adapt_mcp_search_payload` already consumes (`status`/`rows`).
"""

from __future__ import annotations

import time
from typing import Any, Callable, Protocol

# Terminal + transient job states (plan Step 3 / A.10).
RUNNING_STATES = {"queued", "parsing", "running", "submitted", "in_progress"}
DONE_STATES = {"done", "completed", "succeeded", "finalized"}
FAILED_STATES = {"failed", "error"}
DENIED_STATES = {"denied", "permission_denied", "forbidden", "unauthorized"}

# Typed transport failures. The gate maps these to visible orchestration outcomes.
MCP_ERROR_TYPES = (
    "permission_denied",
    "auth_failed",
    "tls_error",
    "timeout",
    "tool_not_found",
    "malformed_result",
    "unavailable",
    "submit_failed",
)


class McpTransportError(Exception):
    """Typed live-transport failure. Never contains secrets."""

    def __init__(self, error_type: str, message: str = "") -> None:
        kind = error_type if error_type in MCP_ERROR_TYPES else "unavailable"
        super().__init__(message or kind)
        self.error_type = kind


def classify_transport_exception(exc: BaseException) -> tuple[str, str]:
    """Return (payload_status, error_type) for a transport exception."""
    if isinstance(exc, McpTransportError):
        return _status_for_error_type(exc.error_type), exc.error_type
    if isinstance(exc, PermissionError):
        return "denied", "permission_denied"
    if isinstance(exc, TimeoutError):
        return "timeout", "timeout"
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if "ssl" in name or "tls" in name or "certificate" in text:
        return "failed", "tls_error"
    if "timeout" in name:
        return "timeout", "timeout"
    if "json" in name or "decode" in name:
        return "schema_invalid", "malformed_result"
    return "failed", f"submit_failed:{type(exc).__name__}"


def _status_for_error_type(error_type: str) -> str:
    if error_type in {"permission_denied", "auth_failed"}:
        return "denied"
    if error_type == "timeout":
        return "timeout"
    if error_type in {"malformed_result", "schema_invalid"}:
        return "schema_invalid"
    return "failed"


class SearchTransport(Protocol):
    """The three live operations. Implementations may raise on transport error;
    the driver classifies the exception (PermissionError → denied, else failed)."""

    def submit(self, arguments: dict[str, Any]) -> str:
        """Submit a search; return a job id."""

    def poll(self, job_id: str) -> dict[str, Any]:
        """Return job status, including a `state` key."""

    def fetch(self, job_id: str) -> dict[str, Any]:
        """Return final results, including a `rows` list."""


def _payload(status: str, *, rows: list[dict[str, Any]] | None = None, error: str | None = None,
             job: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"status": status, "rows": rows or []}
    if error:
        out["error"] = error
    if job:
        out["job"] = job
    return out


def run_search_lifecycle(
    transport: SearchTransport,
    arguments: dict[str, Any],
    *,
    max_polls: int,
    poll_interval_ms: int,
    job_timeout_ms: int,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Drive submit → bounded poll → fetch and return a normalized raw payload.

    Outcomes (one logical call): ok (rows>0), ok+empty (rows==0), failed,
    timeout, denied, schema_invalid. Fails closed — never fabricates rows.
    """
    try:
        job_id = transport.submit(arguments)
    except Exception as exc:  # noqa: BLE001 — connector must fail closed.
        status, error_type = classify_transport_exception(exc)
        return _payload(status, error=error_type)

    deadline = monotonic() + (job_timeout_ms / 1000.0)
    interval = max(poll_interval_ms, 0) / 1000.0

    for poll_index in range(max(max_polls, 1)):
        if monotonic() >= deadline:
            return _payload("timeout", error="search_job_timed_out",
                            job={"job_id": job_id, "polls": poll_index})
        try:
            status = transport.poll(job_id)
        except Exception as exc:  # noqa: BLE001
            payload_status, error_type = classify_transport_exception(exc)
            return _payload(payload_status, error=error_type, job={"job_id": job_id})

        state = str((status or {}).get("state") or "").strip().lower()
        if state in DONE_STATES:
            return _fetch_final(transport, job_id, poll_index + 1)
        if state in FAILED_STATES:
            return _payload("failed", error=str((status or {}).get("error") or "search_job_failed"),
                            job={"job_id": job_id, "polls": poll_index + 1})
        if state in DENIED_STATES:
            return _payload("denied", error="permission_denied", job={"job_id": job_id})
        if state not in RUNNING_STATES:
            return _payload("schema_invalid", error=f"unknown_job_state:{state or 'missing'}",
                            job={"job_id": job_id})
        if monotonic() + interval >= deadline:
            return _payload("timeout", error="search_job_timed_out",
                            job={"job_id": job_id, "polls": poll_index + 1})
        sleep(interval)

    return _payload("timeout", error="max_polls_exceeded", job={"job_id": job_id, "polls": max_polls})


def _fetch_final(transport: SearchTransport, job_id: str, polls: int) -> dict[str, Any]:
    try:
        result = transport.fetch(job_id)
    except Exception as exc:  # noqa: BLE001
        payload_status, error_type = classify_transport_exception(exc)
        return _payload(payload_status, error=error_type, job={"job_id": job_id})

    rows = result.get("rows") if isinstance(result, dict) else None
    if not isinstance(rows, list):
        return _payload("schema_invalid", error="fetch_missing_rows", job={"job_id": job_id})
    # Empty is honest negative evidence — status stays ok, zero rows.
    return _payload("ok", rows=rows, job={"job_id": job_id, "polls": polls, "state": "completed"})
