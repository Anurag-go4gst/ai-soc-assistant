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
        # ``started_at`` is supplied by callers (e.g. live ``/chat``) that captured
        # the true turn-start before the pipeline ran, so run duration reflects the
        # whole turn rather than only the post-hoc telemetry write.
        started_at = fields.get("started_at") or datetime.now(UTC)
        self._run(
            """
            INSERT INTO ai_trace_runs (trace_id, run_id, user_id, entrypoint, status, metadata, started_at)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
            ON CONFLICT (trace_id) DO UPDATE SET
                status = EXCLUDED.status,
                started_at = LEAST(ai_trace_runs.started_at, EXCLUDED.started_at),
                metadata = ai_trace_runs.metadata || EXCLUDED.metadata
            """,
            trace_id,
            run_id,
            fields.get("user_id"),
            fields.get("entrypoint"),
            fields.get("status", "running"),
            _json(metadata),
            started_at,
        )
        return TraceHandle(trace_id=trace_id, run_id=run_id, metadata=metadata)

    def merge_run_metadata(self, trace_id: str, metadata: dict[str, Any]) -> None:
        """Merge additional run metadata without touching status/ended_at.

        Used to attach late-bound fields (``turn_id``, ``user_id``) discovered
        after the pipeline returned but before the response is sent.
        """
        user_id = metadata.get("user_id")
        self._run(
            """
            UPDATE ai_trace_runs
            SET metadata = metadata || $2::jsonb,
                user_id = COALESCE($3, user_id)
            WHERE trace_id = $1
            """,
            trace_id,
            _json(_minimize(metadata)),
            user_id if isinstance(user_id, str) else None,
        )

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

    def reap_stale_running_runs(self, *, older_than_seconds: int = 900) -> None:
        """Mark long-orphaned ``running`` runs as ``abandoned`` (best-effort).

        A turn that crashes or whose backend restarts mid-pipeline never reaches
        ``end_trace``, leaving its admission row stuck in ``running`` forever. We
        close those out so the debug trace list reflects reality. The threshold
        sits well above the worst-case turn wall time (LLM timeout + overhead) so
        a slow-but-live turn is never abandoned out from under itself.
        """
        self._run(
            """
            UPDATE ai_trace_runs
            SET status = 'abandoned', ended_at = now()
            WHERE status = 'running'
              AND ended_at IS NULL
              AND started_at < now() - ($1 || ' seconds')::interval
            """,
            str(int(older_than_seconds)),
        )

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


_METADATA_PRIORITY_KEYS = (
    "answer_mode",
    "selected_skill",
    "turn_id",
    "user_id",
    "question_preview",
    "answer_preview",
    "llm_used",
    "llm_live_calls",
    "mcp_used",
    "debug_summary",
    "final_output",
    "control_plane_trace",
    "run_contract",
    "match_path",
    "use_case_id",
    "question_ref",
    "matched_pattern",
    "spl_path",
    "governance_trace",
    "lineage_summary",
    "llm_sidecars",
    "llm_call_count",
    "session_role",
)


def _slim_control_plane_trace(control_plane_trace: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "rag_trace",
        "candidate_spl_generation",
        "evidence_plan",
        "route_adjudication",
        "planning_decision",
        "query_to_intent",
        "spl_artifact_handoff_summary",
        "llm_calls",
        "llm_turn_budget",
        "llm_composer",
        "mcp_execution",
        "evidence_observer",
        "intent_dispatch",
        "pipeline_dispatch",
        "plan_dispatch",
    )
    return {key: control_plane_trace[key] for key in keep if key in control_plane_trace}


def _priority_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    out = {key: metadata[key] for key in _METADATA_PRIORITY_KEYS if key in metadata}
    cp = out.get("control_plane_trace")
    if isinstance(cp, dict):
        out["control_plane_trace"] = _slim_control_plane_trace(cp)
    return out


def _json(value: Any) -> str:
    minimized = _minimize(value)
    serialized = json.dumps(minimized, separators=(",", ":"), sort_keys=True, default=str)
    if len(serialized.encode("utf-8")) <= MAX_SERIALIZED_PAYLOAD_BYTES:
        return serialized
    if isinstance(minimized, dict):
        priority = _priority_metadata(minimized)
        priority_serialized = json.dumps(priority, separators=(",", ":"), sort_keys=True, default=str)
        if len(priority_serialized.encode("utf-8")) <= MAX_SERIALIZED_PAYLOAD_BYTES:
            return priority_serialized
    return json.dumps(
        {"__truncated__": True, "preview": serialized[:512] + "..."},
        separators=(",", ":"),
    )


# Backwards-compatible internal aliases (other modules import these names).
_minimize = minimize
_truncate = truncate
