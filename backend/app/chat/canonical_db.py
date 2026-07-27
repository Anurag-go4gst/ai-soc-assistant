"""Pooled asyncpg unit-of-work for canonical handoff and planning telemetry.

Canonical persistence uses this module exclusively (plan item 19a). SQLAlchemy
session access stays in ``app/db/session.py``; legacy telemetry tables use
``app/connectors/telemetry/db.py``.
"""

from __future__ import annotations

import asyncio
import contextvars
import logging
import threading
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, contextmanager
from typing import Any, TypeVar

import asyncpg

from app.config import settings

_LOGGER = logging.getLogger("ai_soc.canonical_db")

T = TypeVar("T")

_active_conn: contextvars.ContextVar[asyncpg.Connection | None] = contextvars.ContextVar(
    "canonical_active_conn",
    default=None,
)
_turn_buffer: contextvars.ContextVar[list[dict[str, Any]] | None] = contextvars.ContextVar(
    "canonical_turn_event_buffer",
    default=None,
)
_turn_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "canonical_turn_id",
    default=None,
)
_turn_connection_acquisitions: contextvars.ContextVar[int] = contextvars.ContextVar(
    "canonical_turn_connection_acquisitions",
    default=0,
)

# Per-turn budget pinned by item 19a verification (planning events buffered + handoff UoWs).
MAX_CONNECTIONS_PER_TURN = 5


def canonical_db_disabled() -> bool:
    url = (settings.database_url or "").strip()
    return not url or "change-me@postgres" in url


def active_canonical_connection() -> asyncpg.Connection | None:
    return _active_conn.get()


def turn_connection_acquisitions() -> int:
    return _turn_connection_acquisitions.get()


def current_turn_id() -> str | None:
    return _turn_id.get()


def _record_connection_acquisition() -> None:
    _turn_connection_acquisitions.set(_turn_connection_acquisitions.get() + 1)


class _CanonicalDbLoop:
    """Dedicated event loop so asyncpg pool survives per-request ``asyncio.run`` threads."""

    _instance: _CanonicalDbLoop | None = None
    _guard = threading.Lock()

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._pool: asyncpg.Pool | None = None
        self._ready = threading.Event()

    @classmethod
    def instance(cls) -> _CanonicalDbLoop:
        with cls._guard:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._ready.set()
        loop.run_forever()

    def ensure_started(self) -> asyncio.AbstractEventLoop:
        if self._thread is None:
            self._thread = threading.Thread(
                target=self._thread_main,
                name="canonical-db",
                daemon=True,
            )
            self._thread.start()
        if not self._ready.wait(timeout=5.0):
            raise RuntimeError("canonical DB loop failed to start")
        assert self._loop is not None
        return self._loop

    def run(self, coro: Awaitable[T], *, timeout: float = 30.0) -> T:
        loop = self.ensure_started()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=timeout)

    async def get_pool(self) -> asyncpg.Pool | None:
        if canonical_db_disabled():
            return None
        if self._pool is not None:
            return self._pool
        self._pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=1,
            max_size=5,
            timeout=2.0,
            command_timeout=10.0,
        )
        return self._pool

    async def close_pool(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None


def reset_canonical_db_for_tests() -> None:
    """Tear down the background loop/pool between tests."""
    global _CanonicalDbLoop
    with _CanonicalDbLoop._guard:
        runner = _CanonicalDbLoop._instance
        _CanonicalDbLoop._instance = None
    if runner is None or runner._loop is None:
        return
    try:
        runner.run(runner.close_pool(), timeout=5.0)
    except Exception:
        _LOGGER.debug("canonical_db_test_teardown_failed", exc_info=True)
    runner._loop.call_soon_threadsafe(runner._loop.stop)
    if runner._thread is not None:
        runner._thread.join(timeout=2.0)


@asynccontextmanager
async def canonical_unit_of_work() -> AsyncIterator[asyncpg.Connection | None]:
    """Yield one pooled connection inside a single database transaction."""
    existing = _active_conn.get()
    if existing is not None:
        yield existing
        return

    pool = await _CanonicalDbLoop.instance().get_pool()
    if pool is None:
        yield None
        return

    _record_connection_acquisition()
    async with pool.acquire() as conn:
        token = _active_conn.set(conn)
        try:
            async with conn.transaction():
                yield conn
        finally:
            _active_conn.reset(token)


def run_on_canonical_loop(coro: Awaitable[T], *, timeout: float = 30.0) -> T:
    return _CanonicalDbLoop.instance().run(coro, timeout=timeout)


def run_in_canonical_unit_of_work(
    fn: Callable[[asyncpg.Connection | None], Awaitable[T]],
    *,
    timeout: float = 30.0,
) -> T:
    """Bridge sync callers: one event-loop hop and one transaction per invocation."""

    async def _invoke() -> T:
        async with canonical_unit_of_work() as conn:
            return await fn(conn)

    return _CanonicalDbLoop.instance().run(_invoke(), timeout=timeout)


@contextmanager
def planning_turn_scope(*, turn_id: str | None = None) -> Any:
    """Buffer per-turn planning events and flush them in one transaction."""
    tid = turn_id or str(uuid.uuid4())
    buffer: list[dict[str, Any]] = []
    buffer_token = _turn_buffer.set(buffer)
    turn_token = _turn_id.set(tid)
    acquire_token = _turn_connection_acquisitions.set(0)
    try:
        yield tid
    finally:
        try:
            from app.chat.durable_planning_telemetry import flush_buffered_planning_events

            flush_buffered_planning_events()
        except Exception:
            _LOGGER.warning("planning_turn_flush_failed", exc_info=True)
        acquisitions = _turn_connection_acquisitions.get()
        if acquisitions > MAX_CONNECTIONS_PER_TURN:
            _LOGGER.warning(
                "canonical_turn_connection_budget_exceeded",
                extra={"turn_id": tid, "acquisitions": acquisitions, "budget": MAX_CONNECTIONS_PER_TURN},
            )
        _turn_buffer.reset(buffer_token)
        _turn_id.reset(turn_token)
        _turn_connection_acquisitions.reset(acquire_token)


def append_turn_buffered_event(payload: dict[str, Any]) -> bool:
    """Queue a planning event for end-of-turn flush. Returns False when not buffering."""
    buffer = _turn_buffer.get()
    if buffer is None:
        return False
    buffer.append(payload)
    return True


def drain_turn_buffered_events() -> list[dict[str, Any]]:
    buffer = _turn_buffer.get()
    if not buffer:
        return []
    events = list(buffer)
    buffer.clear()
    return events
