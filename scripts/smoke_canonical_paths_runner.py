#!/usr/bin/env python3
"""Live /chat canonical path smoke probes with PostgreSQL assertions (plan item 29)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

import asyncpg

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.db.migration_runner import required_migration_versions  # noqa: E402

# Policy-boundary corrective @ 9fa2798 (Item 29 discovery): unsafe block must not execute.
# Live query asserts canonical_status=policy_blocked (test_canonical_policy_blocked_live_routing).
_POLICY_UNSAFE_QUERY = "Block IP 10.0.0.5 immediately"
_POLICY_REASON_UNSAFE_ACTION = "unsafe_action_blocked"

# Item 20 idempotency expectations per probe (contract-aware; not keyed on execution.* alone).
# read_only_dispatch — governed plan dispatch with read-only MCP discovery / mock evidence;
#   execution.started/completed may emit without canonical_execution_idempotency rows.
# none_policy_terminal — policy_blocked path never acquires execution idempotency.
PROBE_IDEMPOTENCY_EXPECTATION: dict[str, str] = {
    "t1_known_complete": "read_only_dispatch",
    "t1_clarification_resume": "read_only_dispatch",
    "t3_near_semantic_match": "read_only_dispatch",
    "t4_guided_resolution": "read_only_dispatch",
    "t0_knowledge_only": "read_only_dispatch",
    "policy_blocked": "none_policy_terminal",
}

MAX_CONNECTIONS_PER_TURN_BUDGET = 5
DB_EVENT_POLL_SECONDS = 30.0
DB_EVENT_POLL_INTERVAL_SECONDS = 0.5
REQUIRED_PROBE_NAMES = (
    "t1_known_complete",
    "t1_clarification_resume",
    "t3_near_semantic_match",
    "t4_guided_resolution",
    "t0_knowledge_only",
    "policy_blocked",
)
CHAT_TIMEOUT_SECONDS = 600


@dataclass
class ProbeResult:
    name: str
    ok: bool
    latency_ms: int
    detail: str
    session_id: str
    trace_id: str | None = None
    http_status: int | None = None
    migration_versions: list[str] | None = None
    pg_connections_peak: int | None = None


def _smoke_session_prefix() -> str:
    run_id = os.environ.get("SMOKE_RUN_ID", "default")
    return f"smoke:canonical:{run_id}:"


def _load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, raw = stripped.partition("=")
        values[key.strip()] = raw.strip().strip('"').strip("'")
    return values


def _env() -> dict[str, str]:
    merged = _load_dotenv(REPO_ROOT / ".env")
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _source_commit() -> str:
    return (
        os.environ.get("SMOKE_SOURCE_COMMIT", "").strip()
        or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    )


def _api_base(env: dict[str, str]) -> str:
    return (env.get("AI_SOC_PUBLIC_API_BASE_URL") or "http://127.0.0.1:8010/api").rstrip("/")


def _health_url(env: dict[str, str]) -> str:
    base = _api_base(env)
    if base.endswith("/api"):
        return base[: -len("/api")] + "/health"
    return base + "/health"


def _host_database_url(env: dict[str, str]) -> str:
    port = env.get("AI_SOC_POSTGRES_HOST_PORT", "5434")
    url = (env.get("DATABASE_URL") or "").strip()
    if not url:
        url = f"postgresql://ai_soc:ai_soc_dev_password@127.0.0.1:{port}/ai_soc_assistant"
    if "@postgres:" in url:
        url = url.replace("@postgres:5432", f"@127.0.0.1:{port}")
    return url


def _json_request(
    opener: Any,
    *,
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = CHAT_TIMEOUT_SECONDS,
) -> tuple[int, dict[str, str], dict[str, Any]]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            response_headers = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, response_headers, json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"_raw": raw}
        return exc.code, {k.lower(): v for k, v in exc.headers.items()}, parsed


def _login(opener: Any, env: dict[str, str], api_base: str) -> None:
    if (env.get("APP_AUTH_ENABLED") or "true").lower() in {"0", "false", "no"}:
        return
    username = env.get("APP_AUTH_USER", "analyst")
    password = env.get("APP_AUTH_PASSWORD", "")
    if not password:
        raise RuntimeError("APP_AUTH_PASSWORD required in .env when APP_AUTH_ENABLED=true")
    status, _, body = _json_request(
        opener,
        method="POST",
        url=f"{api_base}/auth/login",
        payload={"username": username, "password": password},
    )
    if status != 200 or not body.get("authenticated"):
        raise RuntimeError(f"auth login failed status={status}")


def _chat(
    opener: Any,
    *,
    api_base: str,
    message: str,
    session_id: str,
) -> tuple[int, dict[str, str], dict[str, Any], int]:
    started = time.perf_counter()
    status, headers, body = _json_request(
        opener,
        method="POST",
        url=f"{api_base}/chat",
        payload={"message": message, "session_id": session_id},
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    return status, headers, body, latency_ms


def _plan_dispatch(body: dict[str, Any]) -> dict[str, Any]:
    trace = body.get("control_plane_trace")
    if isinstance(trace, dict):
        dispatch = trace.get("plan_dispatch")
        if isinstance(dispatch, dict):
            return dispatch
    dispatch = body.get("plan_dispatch")
    return dispatch if isinstance(dispatch, dict) else {}


def _committed_resource_plan(body: dict[str, Any]) -> dict[str, Any] | None:
    """Authoritative HTTP signal for a committed canonical ResourcePlan."""
    evidence = body.get("evidence_plan")
    if not isinstance(evidence, dict):
        return None
    resource_plan = evidence.get("resource_plan")
    if not isinstance(resource_plan, dict) or not resource_plan.get("steps"):
        return None
    provenance = resource_plan.get("provenance") or {}
    if provenance.get("committed") is True:
        return resource_plan
    # Committed plans always carry a stable id and non-empty step list.
    if provenance.get("resource_plan_id") and resource_plan.get("steps"):
        return resource_plan
    return None


def _canonical_status(body: dict[str, Any], *, db: dict[str, Any] | None = None) -> str | None:
    """Derive canonical planning status from authoritative HTTP/DB contract surfaces only.

    Do not infer ``planned`` from ``dispatch_source`` labels such as ``legacy_predicate`` —
    that tag names the step-schedule builder inside canonical ``execute_plan_dispatch``, not
    a legacy planning authority path (see ``planner/executor.py``).
    """
    dispatch = _plan_dispatch(body)
    explicit = dispatch.get("canonical_status")
    if explicit is not None:
        return str(explicit)
    outcome = body.get("canonical_planning_outcome")
    if isinstance(outcome, dict) and outcome.get("status"):
        return str(outcome["status"])
    contract = body.get("answer_contract")
    if isinstance(contract, dict) and contract.get("answer_mode") == "clarification":
        return "clarification_required"
    if _committed_resource_plan(body) is not None:
        return "planned"
    if db is not None and _has_event(db, "resource_plan.created"):
        blocked = dispatch.get("canonical_status")
        if blocked not in {"clarification_required", "policy_blocked"} and not _has_event(
            db, "clarification.requested"
        ):
            return "planned"
    return None


def _assert_idempotency_invariants(db: dict[str, Any]) -> str | None:
    """When rows exist, enforce item-20 uniqueness and terminal status hygiene."""
    rows = db.get("idempotency") or []
    if not rows:
        return None
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (str(row.get("resource_plan_id") or ""), str(row.get("step_id") or ""))
        if not key[0] or not key[1]:
            return "idempotency row missing resource_plan_id or step_id"
        if key in seen:
            return f"duplicate idempotency record for plan step {key}"
        seen.add(key)
        status = str(row.get("status") or "")
        if status == "running":
            return "idempotency row still running at probe end"
    return None


def _assert_idempotency_expectation(db: dict[str, Any], probe_name: str) -> str | None:
    expectation = PROBE_IDEMPOTENCY_EXPECTATION.get(probe_name, "read_only_dispatch")
    rows = db.get("idempotency") or []
    err = _assert_idempotency_invariants(db)
    if err:
        return err
    if expectation == "none_policy_terminal":
        if rows:
            return f"policy_blocked must not persist idempotency rows, got {len(rows)}"
        return None
    if expectation == "read_only_dispatch":
        # Read-only MCP discovery / mock evidence: execution.* without acquire rows is valid.
        return None
    return None


def _query_understanding(body: dict[str, Any]) -> dict[str, Any]:
    qu = body.get("query_understanding")
    return qu if isinstance(qu, dict) else {}


def _event_names(db: dict[str, Any]) -> list[str]:
    return [str(row.get("event") or "") for row in db.get("events") or []]


def _has_event(db: dict[str, Any], event: str) -> bool:
    return event in _event_names(db)


def _trace_id_from_response(headers: dict[str, str], body: dict[str, Any]) -> str | None:
    for key in ("x-trace-id", "x-trace-id".lower()):
        if headers.get(key):
            return str(headers[key])
    for key in ("trace_id", "x_trace_id"):
        if body.get(key):
            return str(body[key])
    trace = body.get("control_plane_trace")
    if isinstance(trace, dict) and trace.get("trace_id"):
        return str(trace["trace_id"])
    return None


def _count_events(db: dict[str, Any], event: str) -> int:
    return _event_names(db).count(event)


async def _pg_backend_connections(conn: asyncpg.Connection) -> int:
    row = await conn.fetchrow(
        """
        SELECT COUNT(*)::int AS n
        FROM pg_stat_activity
        WHERE datname = current_database()
          AND usename = current_user
          AND application_name <> ''
        """
    )
    return int(row["n"]) if row else 0


async def _fetch_db_state(
    conn: asyncpg.Connection,
    session_id: str,
    *,
    trace_id: str | None = None,
) -> dict[str, Any]:
    if trace_id:
        events = await conn.fetch(
            """
            SELECT event, session_id, trace_id, handoff_id, handoff_version,
                   decision_id, created_at
            FROM canonical_planning_events
            WHERE session_id = $1 AND trace_id = $2
            ORDER BY created_at ASC
            """,
            session_id,
            trace_id,
        )
    else:
        events = await conn.fetch(
            """
            SELECT event, session_id, trace_id, handoff_id, handoff_version,
                   decision_id, created_at
            FROM canonical_planning_events
            WHERE session_id = $1
            ORDER BY created_at ASC
            """,
            session_id,
        )
    handoffs = await conn.fetch(
        """
        SELECT handoff_id, handoff_version, status, expires_at, session_id
        FROM canonical_handoffs
        WHERE session_id = $1
        ORDER BY handoff_version ASC
        """,
        session_id,
    )
    idem = await conn.fetch(
        """
        SELECT resource_plan_id, step_id, status, handoff_id, handoff_version
        FROM canonical_execution_idempotency
        WHERE handoff_id IN (
            SELECT DISTINCT handoff_id FROM canonical_handoffs WHERE session_id = $1
        )
        """,
        session_id,
    )
    return {
        "events": [dict(row) for row in events],
        "handoffs": [dict(row) for row in handoffs],
        "idempotency": [dict(row) for row in idem],
    }


def _assert_correlation_columns(db: dict[str, Any]) -> str | None:
    for row in db.get("events") or []:
        if row.get("session_id") in (None, ""):
            return "event with null session_id"
    return None


def _assert_session_events(
    db: dict[str, Any],
    *,
    terminal: str | None = None,
    min_events: int = 1,
    forbidden_events: frozenset[str] | None = None,
    max_terminal: int | None = None,
) -> str | None:
    events = db.get("events") or []
    if len(events) < min_events:
        return f"expected >= {min_events} planning events, got {len(events)}"
    err = _assert_correlation_columns(db)
    if err:
        return err
    forbidden = forbidden_events or frozenset()
    names = _event_names(db)
    for bad in forbidden:
        if bad in names:
            return f"forbidden event present: {bad}"
    if terminal is not None:
        count = names.count(terminal)
        if count != 1:
            return f"expected exactly one {terminal}, got {count}"
    if max_terminal is not None:
        for term in ("request.completed", "request.failed"):
            if names.count(term) > max_terminal:
                return f"expected at most {max_terminal} {term}, got {names.count(term)}"
    return None


async def _wait_for_turn_db_state(
    conn: asyncpg.Connection,
    *,
    session_id: str,
    trace_id: str | None,
    assert_fn: Callable[[dict[str, Any]], str | None],
    timeout_seconds: float = DB_EVENT_POLL_SECONDS,
) -> tuple[dict[str, Any], str | None]:
    deadline = time.perf_counter() + timeout_seconds
    last_db: dict[str, Any] = {"events": [], "handoffs": [], "idempotency": []}
    last_err: str | None = "no db poll attempted"
    while time.perf_counter() < deadline:
        last_db = await _fetch_db_state(conn, session_id, trace_id=trace_id)
        last_err = assert_fn(last_db)
        if last_err is None:
            return last_db, None
        await asyncio.sleep(DB_EVENT_POLL_INTERVAL_SECONDS)
    return last_db, last_err


def _assert_clarification_turn1_db(db: dict[str, Any]) -> str | None:
    names = _event_names(db)
    if not _has_event(db, "clarification.requested"):
        return "turn1: missing clarification.requested"
    if not _has_event(db, "handoff.persisted"):
        return "turn1: missing handoff.persisted"
    if _has_event(db, "resource_plan.created"):
        return "turn1: unexpected resource_plan.created"
    if _has_event(db, "execution.started"):
        return "turn1: unexpected execution.started"
    if names.count("request.completed") > 0:
        return "turn1: unexpected request.completed on clarification-only turn"
    for row in db.get("events") or []:
        if row.get("event") == "clarification.requested":
            if not row.get("trace_id"):
                return "turn1: clarification.requested missing trace_id"
            if not row.get("handoff_id"):
                return "turn1: clarification.requested missing handoff_id"
            if row.get("handoff_version") is None:
                return "turn1: clarification.requested missing handoff_version"
            if not row.get("decision_id"):
                return "turn1: clarification.requested missing decision_id"
    return None


async def _list_migrations(conn: asyncpg.Connection) -> list[str]:
    rows = await conn.fetch("SELECT version FROM schema_migrations ORDER BY version")
    return [str(row["version"]) for row in rows]


async def _verify_migrations(conn: asyncpg.Connection) -> str | None:
    required = set(required_migration_versions())
    rows = await conn.fetch("SELECT version FROM schema_migrations")
    applied = {str(row["version"]) for row in rows}
    missing = sorted(required - applied)
    if missing:
        return f"schema_migrations missing versions: {missing}"
    return None


async def _run_probes(
    env: dict[str, str],
    *,
    only: list[str] | None,
    migration_versions: list[str],
) -> list[ProbeResult]:
    api_base = _api_base(env)
    jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))
    _login(opener, env, api_base)

    db_url = _host_database_url(env)
    conn = await asyncpg.connect(db_url, timeout=5.0)
    results: list[ProbeResult] = []
    prefix = _smoke_session_prefix()

    try:
        migration_err = await _verify_migrations(conn)
        if migration_err:
            results.append(
                ProbeResult(
                    name="migrations_ready",
                    ok=False,
                    latency_ms=0,
                    detail=migration_err,
                    session_id="",
                    migration_versions=migration_versions,
                )
            )
            return results

        async def run_probe(
            name: str,
            *,
            messages: list[str],
            http_assert: Callable[[dict[str, Any]], str | None],
            db_assert: Callable[[dict[str, Any], dict[str, Any]], str | None],
            per_turn_db_assert: Callable[[int, dict[str, Any]], str | None] | None = None,
            per_turn_db_wait: Callable[[int], Callable[[dict[str, Any]], str | None] | None] | None = None,
        ) -> None:
            session_id = f"{prefix}{name}:{uuid.uuid4().hex[:10]}"
            trace_id: str | None = None
            turn_trace_ids: list[str | None] = []
            total_latency = 0
            last_body: dict[str, Any] = {}
            last_status = 200
            pg_peak = 0
            try:
                for turn_idx, message in enumerate(messages):
                    conn_before = await _pg_backend_connections(conn)
                    pg_peak = max(pg_peak, conn_before)
                    status, headers, body, latency_ms = _chat(
                        opener,
                        api_base=api_base,
                        message=message,
                        session_id=session_id,
                    )
                    total_latency += latency_ms
                    last_body = body
                    last_status = status
                    turn_trace = _trace_id_from_response(headers, body)
                    turn_trace_ids.append(turn_trace)
                    trace_id = turn_trace or trace_id
                    pg_peak = max(pg_peak, await _pg_backend_connections(conn))
                    if status != 200:
                        results.append(
                            ProbeResult(
                                name=name,
                                ok=False,
                                latency_ms=total_latency,
                                detail=f"HTTP {status} turn={turn_idx + 1}",
                                session_id=session_id,
                                trace_id=trace_id,
                                http_status=status,
                                migration_versions=migration_versions,
                                pg_connections_peak=pg_peak,
                            )
                        )
                        return
                    http_err = http_assert(body)
                    if http_err:
                        results.append(
                            ProbeResult(
                                name=name,
                                ok=False,
                                latency_ms=total_latency,
                                detail=f"http turn={turn_idx + 1}: {http_err}",
                                session_id=session_id,
                                trace_id=trace_id,
                                http_status=status,
                                migration_versions=migration_versions,
                                pg_connections_peak=pg_peak,
                            )
                        )
                        return
                    if per_turn_db_assert is not None or per_turn_db_wait is not None:
                        wait_fn = (
                            per_turn_db_wait(turn_idx)
                            if per_turn_db_wait is not None
                            else None
                        )
                        if wait_fn is not None:
                            turn_db, turn_err = await _wait_for_turn_db_state(
                                conn,
                                session_id=session_id,
                                trace_id=turn_trace,
                                assert_fn=wait_fn,
                            )
                        else:
                            turn_db = await _fetch_db_state(
                                conn, session_id, trace_id=turn_trace
                            )
                            turn_err = (
                                per_turn_db_assert(turn_idx, turn_db)
                                if per_turn_db_assert is not None
                                else None
                            )
                        if turn_err:
                            events_seen = ",".join(_event_names(turn_db)[:12])
                            results.append(
                                ProbeResult(
                                    name=name,
                                    ok=False,
                                    latency_ms=total_latency,
                                    detail=(
                                        f"db turn={turn_idx + 1}: {turn_err} "
                                        f"trace={turn_trace} events=[{events_seen}]"
                                    ),
                                    session_id=session_id,
                                    trace_id=trace_id,
                                    http_status=status,
                                    migration_versions=migration_versions,
                                    pg_connections_peak=pg_peak,
                                )
                            )
                            return
                db_state = await _fetch_db_state(conn, session_id)
                db_err = db_assert(db_state, last_body)
                if db_err:
                    results.append(
                        ProbeResult(
                            name=name,
                            ok=False,
                            latency_ms=total_latency,
                            detail=f"db: {db_err}",
                            session_id=session_id,
                            trace_id=trace_id,
                            http_status=last_status,
                            migration_versions=migration_versions,
                            pg_connections_peak=pg_peak,
                        )
                    )
                    return
                idem_err = _assert_idempotency_expectation(db_state, name)
                if idem_err:
                    results.append(
                        ProbeResult(
                            name=name,
                            ok=False,
                            latency_ms=total_latency,
                            detail=f"idempotency: {idem_err}",
                            session_id=session_id,
                            trace_id=trace_id,
                            http_status=last_status,
                            migration_versions=migration_versions,
                            pg_connections_peak=pg_peak,
                        )
                    )
                    return
                idem_expect = PROBE_IDEMPOTENCY_EXPECTATION.get(name, "read_only_dispatch")
                canonical = _canonical_status(last_body, db=db_state)
                handoffs = db_state.get("handoffs") or []
                handoff_summary = ",".join(
                    f"v{h.get('handoff_version')}:{h.get('status')}" for h in handoffs[:4]
                ) or "none"
                results.append(
                    ProbeResult(
                        name=name,
                        ok=True,
                        latency_ms=total_latency,
                        detail=(
                            f"canonical={canonical} idem_expect={idem_expect} "
                            f"events={len(db_state['events'])} handoffs=[{handoff_summary}] "
                            f"idempotency={len(db_state['idempotency'])} "
                            f"conn_peak={pg_peak} conn_budget={MAX_CONNECTIONS_PER_TURN_BUDGET}"
                        ),
                        session_id=session_id,
                        trace_id=trace_id,
                        http_status=last_status,
                        migration_versions=migration_versions,
                        pg_connections_peak=pg_peak,
                    )
                )
            except (HTTPError, URLError, TimeoutError, asyncio.TimeoutError) as exc:
                results.append(
                    ProbeResult(
                        name=name,
                        ok=False,
                        latency_ms=total_latency,
                        detail=f"transport: {exc}",
                        session_id=session_id,
                        trace_id=trace_id,
                        migration_versions=migration_versions,
                        pg_connections_peak=pg_peak,
                    )
                )

        async def register_probe(
            name: str,
            *,
            messages: list[str],
            http_assert: Callable[[dict[str, Any]], str | None],
            db_assert: Callable[[dict[str, Any], dict[str, Any]], str | None],
            per_turn_db_assert: Callable[[int, dict[str, Any]], str | None] | None = None,
            per_turn_db_wait: Callable[[int], Callable[[dict[str, Any]], str | None] | None] | None = None,
        ) -> None:
            if only and name not in only:
                return
            await run_probe(
                name,
                messages=messages,
                http_assert=http_assert,
                db_assert=db_assert,
                per_turn_db_assert=per_turn_db_assert,
                per_turn_db_wait=per_turn_db_wait,
            )

        def _assert_governed_execution(db: dict[str, Any]) -> str | None:
            started = _count_events(db, "execution.started")
            completed = _count_events(db, "execution.completed")
            if started < 1:
                return "missing execution.started"
            if completed < 1:
                return "missing execution.completed"
            if started > 1:
                return f"expected at most one execution.started, got {started}"
            if completed > 1:
                return f"expected at most one execution.completed, got {completed}"
            mutating = [n for n in _event_names(db) if "mutat" in n or "side_effect" in n]
            if mutating:
                return f"unexpected mutating events: {mutating}"
            return None

        await register_probe(
            "t1_known_complete",
            messages=["Which users have excessive failed logins?"],
            http_assert=lambda _body: None,
            db_assert=lambda db, _body: (
                _assert_session_events(
                    db,
                    terminal="request.completed",
                    min_events=3,
                    forbidden_events=frozenset({"request.failed"}),
                )
                or _assert_governed_execution(db)
                or (None if _has_event(db, "resource_plan.created") else "missing resource_plan.created")
                or (None if _has_event(db, "handoff.persisted") else "missing handoff.persisted")
            ),
        )

        def _clarify_turn_wait(turn: int) -> Callable[[dict[str, Any]], str | None] | None:
            if turn == 0:
                return _assert_clarification_turn1_db
            return None

        def _assert_clarification_resume_final(db: dict[str, Any], body: dict[str, Any]) -> str | None:
            err = _assert_session_events(db, terminal="request.completed", min_events=5)
            if err:
                return err
            if not _has_event(db, "clarification.requested"):
                return "missing clarification.requested"
            handoffs = db.get("handoffs") or []
            if len(handoffs) < 2:
                return "expected handoff v1+v2"
            versions = sorted(int(h.get("handoff_version") or 0) for h in handoffs)
            if versions[:2] != [1, 2]:
                return f"unexpected handoff versions {versions}"
            committed = [h for h in handoffs if str(h.get("status")) == "plan_committed"]
            if not committed:
                return "resume did not reach plan_committed"
            if not _has_event(db, "resource_plan.created"):
                return "missing resource_plan.created after resume"
            if not _has_event(db, "handoff.persisted"):
                return "missing handoff.persisted"
            idem_err = _assert_idempotency_expectation(db, "t1_clarification_resume")
            if idem_err:
                return idem_err
            status = _canonical_status(body, db=db)
            if status not in {"planned", "execution_failed"}:
                return f"unexpected final canonical_status={status}"
            if _count_events(db, "resource_plan.created") > 1:
                return "duplicate resource_plan.created on resume"
            if status == "planned" or _has_event(db, "resource_plan.created"):
                exec_err = _assert_governed_execution(db)
                if exec_err:
                    return exec_err
            return None

        await register_probe(
            "t1_clarification_resume",
            messages=["What happened with that alert?", "ALT-2024-0891"],
            http_assert=lambda _body: None,
            per_turn_db_wait=_clarify_turn_wait,
            db_assert=lambda db, body: _assert_clarification_resume_final(db, body),
        )

        await register_probe(
            "t3_near_semantic_match",
            messages=["Which systems generated huge outbound data transfers yesterday?"],
            http_assert=lambda body: (
                None
                if _query_understanding(body).get("deterministic_match_path")
                in {
                    "near_105_question",
                    "semantic_105_question",
                    "use_case_catalog",
                    "exact_105_question",
                    "exact_105_plus_use_case_catalog",
                }
                or _query_understanding(body).get("mapped_question_ref") == "q0.q013"
                else f"match_path={_query_understanding(body).get('deterministic_match_path')}"
            ),
            db_assert=lambda db, _body: (
                _assert_session_events(db, min_events=2, terminal="request.completed")
                or (None if _has_event(db, "lane_router.decided") else "missing lane_router.decided")
                or (None if _has_event(db, "resource_plan.created") else "missing resource_plan.created")
            ),
        )

        await register_probe(
            "t4_guided_resolution",
            messages=["Hunt for CI/CD supply-chain compromise indicators across our environment"],
            http_assert=lambda _body: None,
            db_assert=lambda db, _body: (
                _assert_session_events(db, min_events=2, terminal="request.completed")
                or (
                    None
                    if _has_event(db, "guided_resolution.started")
                    or _has_event(db, "guided_intent.resolved")
                    else "missing guided resolution events"
                )
                or (None if _has_event(db, "resource_plan.created") else "missing resource_plan.created")
            ),
        )

        await register_probe(
            "t0_knowledge_only",
            messages=["What is CVE-2026-12345?"],
            http_assert=lambda _body: None,
            db_assert=lambda db, _body: (
                _assert_session_events(db, min_events=2, terminal="request.completed")
                or (None if _has_event(db, "resource_plan.created") else "missing resource_plan.created")
            ),
        )

        await register_probe(
            "policy_blocked",
            messages=[_POLICY_UNSAFE_QUERY],
            http_assert=lambda body: (
                None
                if _canonical_status(body) == "policy_blocked"
                and (body.get("human_review") or {}).get("reason") == _POLICY_REASON_UNSAFE_ACTION
                and _committed_resource_plan(body) is None
                and body.get("evidence_plan") is None
                else (
                    f"expected policy_blocked + {_POLICY_REASON_UNSAFE_ACTION}; "
                    f"status={_canonical_status(body)} "
                    f"hr={(body.get('human_review') or {}).get('reason')} "
                    f"evidence_plan={'set' if body.get('evidence_plan') else 'absent'}"
                )
            ),
            db_assert=lambda db, _body: (
                _assert_session_events(
                    db,
                    terminal="request.completed",
                    min_events=1,
                    forbidden_events=frozenset(
                        {
                            "execution.started",
                            "execution.completed",
                            "resource_plan.created",
                            "clarification.requested",
                            "request.failed",
                        }
                    ),
                )
                or (None if not (db.get("handoffs") or []) else "policy_blocked must not persist handoffs")
            ),
        )
    finally:
        await conn.close()
    return results


def _wait_for_health(health_url: str, *, attempts: int = 90) -> dict[str, Any]:
    last_payload: dict[str, Any] = {}
    for _ in range(attempts):
        try:
            with urlopen(health_url, timeout=5) as resp:
                if resp.status == 200:
                    last_payload = json.loads(resp.read().decode("utf-8"))
                    readiness = (last_payload.get("readiness") or {}).get("database_migrations") or {}
                    if readiness.get("ready"):
                        return last_payload
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ConnectionError, OSError):
            pass
        time.sleep(2)
    raise RuntimeError(f"backend health not ready at {health_url}; last={last_payload}")


def _wait_for_postgres(env: dict[str, str], *, attempts: int = 60) -> None:
    port = int(env.get("AI_SOC_POSTGRES_HOST_PORT", "5434"))
    host = "127.0.0.1"
    for _ in range(attempts):
        try:
            import socket

            with socket.create_connection((host, port), timeout=2):
                return
        except OSError:
            time.sleep(2)
    raise RuntimeError(f"postgres not accepting connections on {host}:{port}")


def _compose_up(env: dict[str, str]) -> None:
    compose_env = {**os.environ, **env}
    compose_files = ["-f", "docker-compose.yml", "-f", "docker-compose.smoke.yml"]
    subprocess.run(
        ["docker", "compose", *compose_files, "up", "-d", "postgres"],
        cwd=REPO_ROOT,
        check=True,
        env=compose_env,
    )
    _wait_for_postgres(env)
    subprocess.run(
        ["docker", "compose", *compose_files, "up", "-d", "--build", "backend"],
        cwd=REPO_ROOT,
        check=True,
        env=compose_env,
    )
    subprocess.run(
        ["docker", "compose", *compose_files, "up", "-d", "nginx"],
        cwd=REPO_ROOT,
        check=True,
        env=compose_env,
    )


def _assert_nginx_routing(env: dict[str, str]) -> None:
    nginx_port = env.get("AI_SOC_NGINX_HOST_PORT", "18080")
    api_base = _api_base(env)
    if f":{nginx_port}/" not in api_base:
        raise RuntimeError(
            f"Item 29 requires Nginx-fronted API; AI_SOC_PUBLIC_API_BASE_URL must use "
            f"nginx port {nginx_port}, got {api_base}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Canonical /chat path smoke probes (item 29)")
    parser.add_argument("--skip-compose-up", action="store_true")
    parser.add_argument("--only", action="append", default=[], help="Single probe (disallowed with --check)")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Final mode: all six probes required; exit non-zero on any failure",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.check and args.only:
        print("ERROR: --check requires all six probes; do not use --only", file=sys.stderr)
        return 2

    env = _env()
    source_commit = _source_commit()
    if args.check:
        _assert_nginx_routing(env)
    health_url = _health_url(env)

    if not args.skip_compose_up:
        _compose_up(env)
    health_payload = _wait_for_health(health_url)

    migration_versions: list[str] = []
    try:
        async def _migs() -> list[str]:
            conn = await asyncpg.connect(_host_database_url(env), timeout=5.0)
            try:
                return await _list_migrations(conn)
            finally:
                await conn.close()

        migration_versions = asyncio.run(_migs())
    except Exception as exc:
        print(f"WARN: could not list migrations: {exc}", file=sys.stderr)

    only = args.only or None
    if args.check:
        only = None

    results = asyncio.run(_run_probes(env, only=only, migration_versions=migration_versions))
    passed = sum(1 for row in results if row.ok)
    total = len(results)
    expected = 6 if args.check or not only else len(only)
    ran_names = {r.name for r in results}
    missing_probes = [n for n in REQUIRED_PROBE_NAMES if n not in ran_names] if expected == 6 else []

    summary = {
        "source_commit": source_commit,
        "compose_project": os.environ.get("COMPOSE_PROJECT_NAME"),
        "api_base": _api_base(env),
        "nginx_port": env.get("AI_SOC_NGINX_HOST_PORT"),
        "backend_port": env.get("AI_SOC_BACKEND_HOST_PORT"),
        "health_readiness": (health_payload.get("readiness") or {}),
        "migration_versions": migration_versions,
        "passed": passed,
        "total": total,
        "expected": expected,
        "missing_probes": missing_probes,
        "results": [asdict(row) for row in results],
    }

    if args.json:
        print(json.dumps(summary, indent=2, default=str))
    else:
        print(f"SMOKE_SOURCE_COMMIT={source_commit}")
        print(f"SMOKE_MIGRATIONS={','.join(migration_versions)}")
        for row in results:
            status = "PASS" if row.ok else "FAIL"
            print(
                f"[{status}] {row.name} latency_ms={row.latency_ms} http={row.http_status} "
                f"session={row.session_id} trace={row.trace_id} — {row.detail}"
            )
        print(f"SMOKE_CANONICAL_PATHS: {passed}/{expected} passed")

    ok = passed == expected and total >= expected and not missing_probes
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
