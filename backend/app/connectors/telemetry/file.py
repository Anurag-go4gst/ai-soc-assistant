"""Append-only NDJSON telemetry sink for air-gapped deployments.

Used when ``AI_SOC_TELEMETRY_SINK=file`` so observability works without a
Postgres telemetry database. One line per event, one file per UTC day. Same
redaction as the DB sink (no secrets, no raw payloads). Writes are best-effort:
a failure never breaks the calling request.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from app.config import settings
from app.connectors.mcp.base import ConnectorStatus
from app.connectors.telemetry import metrics
from app.connectors.telemetry.base import TraceHandle
from app.connectors.telemetry.redaction import minimize

_LOGGER = logging.getLogger("ai_soc.telemetry")
_WRITE_LOCK = Lock()


class FileTelemetryConnector:
    mode = "file"

    def __init__(self, directory: str | None = None) -> None:
        self.directory = (directory or settings.ai_soc_telemetry_file_dir).strip()

    def health(self) -> ConnectorStatus:
        configured = bool(self.directory)
        available = False
        detail = "file_dir_missing"
        if configured:
            try:
                Path(self.directory).mkdir(parents=True, exist_ok=True)
                available = True
                detail = "file_dir_ready"
            except OSError as exc:
                detail = f"file_dir_error:{type(exc).__name__}"
        return ConnectorStatus(mode=self.mode, configured=configured, available=available, detail=detail)

    # ---- write protocol ----------------------------------------------------

    def start_trace(self, trace_id: str | None = None, **fields: Any) -> TraceHandle:
        trace_id = trace_id or str(uuid4())
        run_id = fields.get("run_id") or trace_id
        metadata = minimize(fields.get("metadata", {}))
        started_at = fields.get("started_at")
        self._append(
            "run_start",
            trace_id,
            run_id=run_id,
            user_id=fields.get("user_id"),
            entrypoint=fields.get("entrypoint"),
            status=fields.get("status", "running"),
            metadata=metadata,
            started_at=_iso(started_at) or _now(),
        )
        return TraceHandle(trace_id=trace_id, run_id=run_id, metadata=metadata if isinstance(metadata, dict) else {})

    def end_trace(self, trace_id: str, status: str = "completed", **fields: Any) -> None:
        self._append(
            "run_end",
            trace_id,
            status=status,
            metadata=minimize(fields.get("metadata", {})),
            ended_at=_now(),
        )

    def merge_run_metadata(self, trace_id: str, metadata: dict[str, Any]) -> None:
        self._append("run_merge", trace_id, metadata=minimize(metadata))

    def record_step(self, trace_id: str, step_name: str, status: str, **fields: Any) -> None:
        self._append("step", trace_id, step_name=step_name, status=status, event=minimize(fields))

    def record_routing_decision(self, trace_id: str, **fields: Any) -> None:
        self._append("routing_decision", trace_id, event=minimize(fields))

    def record_routing_disagreement(self, trace_id: str, **fields: Any) -> None:
        self._append("routing_disagreement", trace_id, event=minimize(fields))

    def record_spl_validation(self, trace_id: str, **fields: Any) -> None:
        self._append("spl_validation", trace_id, event=minimize(fields))

    def record_mcp_execution(self, trace_id: str, **fields: Any) -> None:
        self._append("mcp_execution", trace_id, event=minimize(fields))

    def record_rag_retrieval(self, trace_id: str, **fields: Any) -> None:
        self._append("rag_retrieval", trace_id, event=minimize(fields))

    def record_llm_call(self, trace_id: str, **fields: Any) -> None:
        self._append("llm_call", trace_id, event=minimize(fields))

    def record_harness_result(self, trace_id: str, **fields: Any) -> str:
        test_run_id = str(fields.get("test_run_id") or fields.get("run_id") or uuid4())
        self._append("harness", trace_id, test_run_id=test_run_id, event=minimize(fields))
        return test_run_id

    # ---- internals ---------------------------------------------------------

    def _path_for_today(self) -> Path:
        day = datetime.now(UTC).strftime("%Y-%m-%d")
        return Path(self.directory) / f"ai_soc_telemetry_{day}.ndjson"

    def _append(self, event_type: str, trace_id: str, **payload: Any) -> None:
        if not self.directory:
            metrics.increment("telemetry_writes_skipped_null")
            return
        record = {"type": event_type, "trace_id": trace_id, "created_at": _now(), **payload}
        line = json.dumps(record, separators=(",", ":"), sort_keys=True, default=str)
        try:
            with _WRITE_LOCK:
                path = self._path_for_today()
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
        except OSError as exc:
            metrics.increment("telemetry_write_failures")
            _LOGGER.warning(
                "telemetry_file_write_failed",
                extra={"telemetry_event": "telemetry_file_write_failed", "error_type": type(exc).__name__},
            )


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat()
    if isinstance(value, str) and value:
        return value
    return None
