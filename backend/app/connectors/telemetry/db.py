from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import asyncpg

from app.config import settings
from app.connectors.mcp.base import ConnectorStatus
from app.connectors.telemetry import metrics as _telemetry_metrics_module
from app.connectors.telemetry.base import TraceHandle
from app.connectors.telemetry.redaction import (
    MAX_SERIALIZED_PAYLOAD_BYTES,
    minimize,
    truncate,
)

# Direct submodule reference. We do not access ``metrics`` as a package
# attribute because ``app.connectors.telemetry.__init__`` may still be
# executing when this module is first imported.
metrics = _telemetry_metrics_module

_MIGRATION_PATH = Path(__file__).resolve().parents[2] / "db" / "migrations" / "0001_ai_soc_telemetry.sql"
_LOGGER = logging.getLogger("ai_soc.telemetry")


class DbTelemetryConnector:
    mode = "db"
    _global_disabled_after_failure = False

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or settings.database_url
        self._schema_ready = False
        self._disabled_after_failure = False
        self._write_disabled_for_placeholder = "change-me@postgres" in self.database_url

    def health(self) -> ConnectorStatus:
        configured = bool(self.database_url.strip())
        return ConnectorStatus(
            mode=self.mode,
            configured=configured,
            available=configured,
            detail="postgres_configured" if configured else "database_url_missing",
        )

    def start_trace(self, trace_id: str | None = None, **fields: Any) -> TraceHandle:
        trace_id = trace_id or str(uuid4())
        run_id = fields.get("run_id") or trace_id
        metadata = _minimize(fields.get("metadata", {}))
        self._run(
            """
            INSERT INTO ai_trace_runs (trace_id, run_id, user_id, entrypoint, status, metadata)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            ON CONFLICT (trace_id) DO UPDATE SET
                status = EXCLUDED.status,
                metadata = ai_trace_runs.metadata || EXCLUDED.metadata
            """,
            trace_id,
            run_id,
            fields.get("user_id"),
            fields.get("entrypoint"),
            fields.get("status", "running"),
            _json(metadata),
        )
        return TraceHandle(trace_id=trace_id, run_id=run_id, metadata=metadata)

    def record_step(self, trace_id: str, step_name: str, status: str, **fields: Any) -> None:
        self._insert_json("ai_trace_steps", trace_id, step_name=step_name, status=status, **fields)

    def record_routing_decision(self, trace_id: str, **fields: Any) -> None:
        self._insert_json("routing_decisions", trace_id, **fields)

    def record_routing_disagreement(self, trace_id: str, **fields: Any) -> None:
        self._insert_json("routing_disagreements", trace_id, **fields)

    def record_spl_validation(self, trace_id: str, **fields: Any) -> None:
        self._insert_json("spl_validation_results", trace_id, **fields)

    def record_mcp_execution(self, trace_id: str, **fields: Any) -> None:
        self._insert_json("mcp_execution_logs", trace_id, **fields)

    def record_rag_retrieval(self, trace_id: str, **fields: Any) -> None:
        self._insert_json("rag_retrieval_logs", trace_id, **fields)

    def record_llm_call(self, trace_id: str, **fields: Any) -> None:
        self._insert_json("llm_call_logs", trace_id, **fields)

    def record_harness_result(self, trace_id: str, **fields: Any) -> str:
        test_run_id = str(fields.get("test_run_id") or fields.get("run_id") or uuid4())
        self._run(
            """
            INSERT INTO harness_test_runs (test_run_id, trace_id, status, metadata)
            VALUES ($1, $2, $3, $4::jsonb)
            ON CONFLICT (test_run_id) DO NOTHING
            """,
            test_run_id,
            trace_id,
            fields.get("status", "completed"),
            _json(_minimize(fields.get("run_metadata", {}))),
        )
        self._run(
            """
            INSERT INTO harness_test_case_results (
                test_run_id, trace_id, case_id, user_query, expected_skill, actual_skill,
                generated_spl_ref, spl_validation_result, mcp_execution_status,
                expected_findings, actual_findings_summary, layer_results, final_pass
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10::jsonb, $11, $12::jsonb, $13)
            """,
            test_run_id,
            trace_id,
            fields.get("case_id"),
            _truncate(fields.get("user_query")),
            fields.get("expected_skill"),
            fields.get("actual_skill"),
            _truncate(fields.get("generated_spl_ref") or fields.get("spl")),
            _json(_minimize(fields.get("spl_validation_result", {}))),
            fields.get("mcp_execution_status"),
            _json(_minimize(fields.get("expected_findings", {}))),
            _truncate(fields.get("actual_findings_summary")),
            _json(_minimize(fields.get("layer_results", {}))),
            bool(fields.get("final_pass", False)),
        )
        return test_run_id

    def end_trace(self, trace_id: str, status: str = "completed", **fields: Any) -> None:
        self._run(
            """
            UPDATE ai_trace_runs
            SET status = $2, ended_at = $3, metadata = metadata || $4::jsonb
            WHERE trace_id = $1
            """,
            trace_id,
            status,
            datetime.now(UTC),
            _json(_minimize(fields.get("metadata", {}))),
        )

    def _insert_json(self, table: str, trace_id: str, **fields: Any) -> None:
        self._run(
            f"INSERT INTO {table} (trace_id, event) VALUES ($1, $2::jsonb)",
            trace_id,
            _json(_minimize(fields)),
        )

    def _run(self, sql: str, *args: Any) -> None:
        """Execute a single telemetry write.

        A telemetry write failure must never crash the calling request flow.
        On any exception we increment the in-process failure counter, emit a
        structured warning log (without payload contents), and return — i.e.
        we fall through to no-op behavior for this call.
        """
        if self._write_disabled_for_placeholder or self._disabled_after_failure or DbTelemetryConnector._global_disabled_after_failure:
            return

        async def _inner() -> None:
            await self._ensure_schema()
            conn = await asyncpg.connect(self.database_url, timeout=1.0)
            try:
                await conn.execute(sql, *args)
            finally:
                await conn.close()

        try:
            asyncio.run(_inner())
        except Exception as exc:  # noqa: BLE001 — telemetry must be best-effort
            self._disabled_after_failure = True
            DbTelemetryConnector._global_disabled_after_failure = True
            metrics.increment("telemetry_write_failures")
            _LOGGER.warning(
                "telemetry_write_failed",
                extra={
                    "telemetry_event": "telemetry_write_failed",
                    "sql_kind": _sql_kind(sql),
                    "error_type": type(exc).__name__,
                },
            )

    async def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        conn = await asyncpg.connect(self.database_url, timeout=1.0)
        try:
            await conn.execute(_MIGRATION_PATH.read_text(encoding="utf-8"))
            self._schema_ready = True
        finally:
            await conn.close()


def _sql_kind(sql: str) -> str:
    head = sql.strip().split(None, 1)
    return head[0].upper() if head else "UNKNOWN"


def _json(value: Any) -> str:
    serialized = json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)
    if len(serialized.encode("utf-8")) > MAX_SERIALIZED_PAYLOAD_BYTES:
        return json.dumps(
            {"__truncated__": True, "preview": serialized[:512] + "..."},
            separators=(",", ":"),
        )
    return serialized


# Backwards-compatible internal aliases (other modules import these names).
_minimize = minimize
_truncate = truncate
