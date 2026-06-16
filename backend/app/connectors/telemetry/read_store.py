"""Read-side telemetry assembly for the COE debug API."""

from __future__ import annotations

import asyncio
import glob
import json
import os
from datetime import UTC, datetime
from typing import Any

import asyncpg

from app.config import settings
from app.connectors.telemetry.redaction import minimize

_EVENT_TABLES: tuple[tuple[str, str], ...] = (
    ("step", "ai_trace_steps"),
    ("routing_decision", "routing_decisions"),
    ("routing_disagreement", "routing_disagreements"),
    ("spl_validation", "spl_validation_results"),
    ("mcp_execution", "mcp_execution_logs"),
    ("rag_retrieval", "rag_retrieval_logs"),
    ("llm_call", "llm_call_logs"),
)
_EVENT_KINDS = frozenset(kind for kind, _ in _EVENT_TABLES)


def _file_sink_active() -> bool:
    return settings.ai_soc_telemetry_sink.strip().lower() == "file"


def list_trace_runs(
    *,
    limit: int = 50,
    entrypoint: str | None = None,
    status: str | None = None,
    since: datetime | None = None,
) -> list[dict[str, Any]]:
    if _file_sink_active():
        return _file_list_trace_runs(limit=limit, entrypoint=entrypoint, status=status, since=since)
    return asyncio.run(_list_trace_runs_async(limit=limit, entrypoint=entrypoint, status=status, since=since))


def fetch_trace_timeline(trace_id: str, *, max_events: int | None = None) -> dict[str, Any] | None:
    if _file_sink_active():
        return _file_fetch_trace_timeline(trace_id, max_events=max_events)
    return asyncio.run(_fetch_trace_timeline_async(trace_id, max_events=max_events))


def fetch_trace_bundle(trace_id: str, *, max_events: int | None = None) -> dict[str, Any] | None:
    timeline = fetch_trace_timeline(trace_id, max_events=max_events)
    if timeline is None:
        return None
    run = timeline.get("run") or {}
    metadata = run.get("metadata") if isinstance(run.get("metadata"), dict) else {}
    events = timeline.get("events") or []
    return {
        "trace_id": trace_id,
        "run": run,
        "timeline": events,
        "explainability": {
            "control_plane_trace": metadata.get("control_plane_trace"),
            "governance_trace": metadata.get("governance_trace"),
            "lineage_summary": metadata.get("lineage_summary"),
            "llm_sidecars": metadata.get("llm_sidecars"),
        },
        "turn_id": metadata.get("turn_id"),
        "event_truncated": bool(timeline.get("event_truncated")),
        "event_limit": timeline.get("event_limit"),
    }


async def _list_trace_runs_async(
    *,
    limit: int,
    entrypoint: str | None,
    status: str | None,
    since: datetime | None,
) -> list[dict[str, Any]]:
    capped = max(1, min(limit, 200))
    conn = await _connect()
    try:
        rows = await conn.fetch(
            """
            SELECT trace_id, run_id, user_id, entrypoint, status, metadata, started_at, ended_at
            FROM ai_trace_runs
            WHERE ($1::text IS NULL OR entrypoint = $1)
              AND ($2::text IS NULL OR status = $2)
              AND ($3::timestamptz IS NULL OR started_at >= $3)
            ORDER BY started_at DESC NULLS LAST
            LIMIT $4
            """,
            entrypoint,
            status,
            since,
            capped,
        )
        runs = [_serialize_run(row) for row in rows]
        if runs:
            return runs
        orphan_rows = await conn.fetch(
            """
            SELECT trace_id, MAX(created_at) AS last_event_at, COUNT(*)::int AS event_count
            FROM ai_trace_steps
            GROUP BY trace_id
            ORDER BY last_event_at DESC
            LIMIT $1
            """,
            capped,
        )
        return [
            {
                "trace_id": row["trace_id"],
                "run_id": row["trace_id"],
                "user_id": None,
                "entrypoint": "unknown",
                "status": "orphan_steps",
                "metadata": {"event_count": row["event_count"], "synthetic": True},
                "started_at": _iso(row["last_event_at"]),
                "ended_at": None,
                "duration_ms": None,
                "answer_mode": None,
                "selected_skill": None,
            }
            for row in orphan_rows
        ]
    finally:
        await conn.close()


async def _fetch_trace_timeline_async(trace_id: str, *, max_events: int | None = None) -> dict[str, Any] | None:
    conn = await _connect()
    try:
        run_row = await conn.fetchrow(
            """
            SELECT trace_id, run_id, user_id, entrypoint, status, metadata, started_at, ended_at
            FROM ai_trace_runs
            WHERE trace_id = $1
            """,
            trace_id,
        )
        events: list[dict[str, Any]] = []
        for kind, table in _EVENT_TABLES:
            events.extend(await _fetch_events_for_table(conn, kind, table, trace_id))
        if run_row is None and not events:
            return None
        events.sort(key=lambda item: item.get("created_at") or "")
        events, truncated = _cap_events(events, max_events=max_events)
        run = _serialize_run(run_row) if run_row else {
            "trace_id": trace_id,
            "run_id": trace_id,
            "user_id": None,
            "entrypoint": "unknown",
            "status": "orphan_steps",
            "metadata": {"synthetic": True},
            "started_at": events[0]["created_at"] if events else None,
            "ended_at": events[-1]["created_at"] if events else None,
            "duration_ms": None,
            "answer_mode": None,
            "selected_skill": None,
        }
        if isinstance(run.get("metadata"), dict):
            run["answer_mode"] = run["metadata"].get("answer_mode")
            run["selected_skill"] = run["metadata"].get("selected_skill")
        return {
            "run": run,
            "events": events,
            "event_count": len(events),
            "event_truncated": truncated,
            "event_limit": max_events,
        }
    finally:
        await conn.close()


async def _fetch_events_for_table(
    conn: asyncpg.Connection,
    kind: str,
    table: str,
    trace_id: str,
) -> list[dict[str, Any]]:
    if table not in {name for _, name in _EVENT_TABLES}:
        return []
    if table == "ai_trace_steps":
        rows = await conn.fetch(
            """
            SELECT trace_id, step_name, status, event, created_at
            FROM ai_trace_steps
            WHERE trace_id = $1
            ORDER BY created_at ASC
            """,
            trace_id,
        )
        return [
            {
                "kind": kind,
                "created_at": _iso(row["created_at"]),
                "step_name": row["step_name"],
                "status": row["status"],
                "event": minimize(dict(row["event"] or {})),
            }
            for row in rows
        ]
    rows = await conn.fetch(
        f"""
        SELECT trace_id, event, created_at
        FROM {table}
        WHERE trace_id = $1
        ORDER BY created_at ASC
        """,
        trace_id,
    )
    return [
        {
            "kind": kind,
            "created_at": _iso(row["created_at"]),
            "event": minimize(dict(row["event"] or {})),
        }
        for row in rows
    ]


def _serialize_run(row: asyncpg.Record | None) -> dict[str, Any]:
    if row is None:
        return {}
    metadata = minimize(dict(row["metadata"] or {}))
    started_at = row["started_at"]
    ended_at = row["ended_at"]
    duration_ms = None
    if isinstance(started_at, datetime) and isinstance(ended_at, datetime):
        duration_ms = int((ended_at - started_at).total_seconds() * 1000)
    return {
        "trace_id": row["trace_id"],
        "run_id": row["run_id"],
        "user_id": row["user_id"],
        "entrypoint": row["entrypoint"],
        "status": row["status"],
        "metadata": metadata,
        "started_at": _iso(started_at),
        "ended_at": _iso(ended_at),
        "duration_ms": duration_ms,
        "answer_mode": metadata.get("answer_mode"),
        "selected_skill": metadata.get("selected_skill"),
        "turn_id": metadata.get("turn_id"),
    }


async def _connect() -> asyncpg.Connection:
    return await asyncpg.connect(settings.database_url, timeout=2.0)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _cap_events(events: list[dict[str, Any]], *, max_events: int | None) -> tuple[list[dict[str, Any]], bool]:
    if max_events is None or max_events <= 0 or len(events) <= max_events:
        return events, False
    return events[:max_events], True


# ---------------------------------------------------------------------------
# File-sink reader (AI_SOC_TELEMETRY_SINK=file). Parses the append-only NDJSON
# the FileTelemetryConnector writes and reconstructs the same run/timeline
# shapes the asyncpg reader returns, so the debug API is backend-agnostic.
# ---------------------------------------------------------------------------


def _read_all_file_records() -> list[dict[str, Any]]:
    directory = settings.ai_soc_telemetry_file_dir.strip()
    if not directory or not os.path.isdir(directory):
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(glob.glob(os.path.join(directory, "ai_soc_telemetry_*.ndjson"))):
        try:
            with open(path, encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue
    return records


def _file_assemble_runs(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    runs: dict[str, dict[str, Any]] = {}
    for rec in records:
        rec_type = rec.get("type")
        trace_id = rec.get("trace_id")
        if not trace_id or rec_type not in {"run_start", "run_end", "run_merge"}:
            continue
        run = runs.setdefault(
            trace_id,
            {
                "trace_id": trace_id,
                "run_id": trace_id,
                "user_id": None,
                "entrypoint": "unknown",
                "status": "running",
                "metadata": {},
                "started_at": None,
                "ended_at": None,
            },
        )
        meta = rec.get("metadata")
        if isinstance(meta, dict):
            run["metadata"] = {**run["metadata"], **meta}
        if rec_type == "run_start":
            run["run_id"] = rec.get("run_id") or trace_id
            run["user_id"] = rec.get("user_id") or run["user_id"]
            run["entrypoint"] = rec.get("entrypoint") or run["entrypoint"]
            run["status"] = rec.get("status") or run["status"]
            run["started_at"] = run["started_at"] or rec.get("started_at")
        elif rec_type == "run_end":
            run["status"] = rec.get("status") or run["status"]
            run["ended_at"] = rec.get("ended_at") or rec.get("created_at")
        elif rec_type == "run_merge":
            meta_user = (meta or {}).get("user_id") if isinstance(meta, dict) else None
            if meta_user:
                run["user_id"] = meta_user
    for run in runs.values():
        _finalize_file_run(run)
    return runs


def _finalize_file_run(run: dict[str, Any]) -> None:
    metadata = run.get("metadata") if isinstance(run.get("metadata"), dict) else {}
    duration_ms = None
    started = _parse_iso(run.get("started_at"))
    ended = _parse_iso(run.get("ended_at"))
    if started and ended:
        duration_ms = int((ended - started).total_seconds() * 1000)
    run["metadata"] = minimize(metadata)
    run["duration_ms"] = duration_ms
    run["answer_mode"] = metadata.get("answer_mode")
    run["selected_skill"] = metadata.get("selected_skill")
    run["turn_id"] = metadata.get("turn_id")


def _file_list_trace_runs(
    *,
    limit: int,
    entrypoint: str | None,
    status: str | None,
    since: datetime | None,
) -> list[dict[str, Any]]:
    capped = max(1, min(limit, 200))
    records = _read_all_file_records()
    runs = list(_file_assemble_runs(records).values())
    if entrypoint is not None:
        runs = [r for r in runs if r.get("entrypoint") == entrypoint]
    if status is not None:
        runs = [r for r in runs if r.get("status") == status]
    if since is not None:
        runs = [r for r in runs if (_parse_iso(r.get("started_at")) or _EPOCH) >= since]
    runs.sort(key=lambda r: r.get("started_at") or "", reverse=True)
    return runs[:capped]


def _file_fetch_trace_timeline(trace_id: str, *, max_events: int | None) -> dict[str, Any] | None:
    records = _read_all_file_records()
    runs = _file_assemble_runs(records)
    run = runs.get(trace_id)
    events: list[dict[str, Any]] = []
    for rec in records:
        if rec.get("trace_id") != trace_id:
            continue
        kind = rec.get("type")
        if kind not in _EVENT_KINDS:
            continue
        event = {"kind": kind, "created_at": rec.get("created_at"), "event": minimize(rec.get("event") or {})}
        if kind == "step":
            event["step_name"] = rec.get("step_name")
            event["status"] = rec.get("status")
        events.append(event)
    if run is None and not events:
        return None
    events.sort(key=lambda item: item.get("created_at") or "")
    if run is None:
        run = {
            "trace_id": trace_id,
            "run_id": trace_id,
            "user_id": None,
            "entrypoint": "unknown",
            "status": "orphan_steps",
            "metadata": {"synthetic": True},
            "started_at": events[0]["created_at"] if events else None,
            "ended_at": events[-1]["created_at"] if events else None,
            "duration_ms": None,
            "answer_mode": None,
            "selected_skill": None,
            "turn_id": None,
        }
    capped, truncated = _cap_events(events, max_events=max_events)
    return {
        "run": run,
        "events": capped,
        "event_count": len(capped),
        "event_truncated": truncated,
        "event_limit": max_events,
    }


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
