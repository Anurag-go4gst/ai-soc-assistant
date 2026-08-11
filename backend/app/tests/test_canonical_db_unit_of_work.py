"""Canonical DB unit-of-work and pool (plan item 19a)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.chat import canonical_db, durable_planning_telemetry as telemetry


def _mock_pool() -> tuple[MagicMock, AsyncMock]:
    conn = AsyncMock()

    @asynccontextmanager
    async def _transaction():
        yield None

    conn.transaction = MagicMock(side_effect=lambda: _transaction())

    pool = MagicMock()

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool.acquire = MagicMock(side_effect=lambda: _acquire())
    return pool, conn


@pytest.fixture(autouse=True)
def _reset_canonical_db() -> Any:
    canonical_db.reset_canonical_db_for_tests()
    telemetry.use_test_event_store(False)
    telemetry.clear_persisted_events_for_tests()
    yield
    canonical_db.reset_canonical_db_for_tests()
    telemetry.use_test_event_store(False)
    telemetry.clear_persisted_events_for_tests()


def test_unit_of_work_rollback_discards_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    pool, conn = _mock_pool()

    async def _get_pool() -> Any:
        return pool

    monkeypatch.setattr(canonical_db._CanonicalDbLoop.instance(), "get_pool", _get_pool)
    monkeypatch.setattr(canonical_db, "canonical_db_disabled", lambda: False)

    async def _write(active_conn: Any) -> None:
        await active_conn.execute("INSERT INTO canonical_planning_events DEFAULT VALUES")
        raise RuntimeError("force rollback")

    with pytest.raises(RuntimeError, match="force rollback"):
        canonical_db.run_in_canonical_unit_of_work(_write)

    conn.execute.assert_awaited_once()
    conn.transaction.assert_called_once()


def test_two_operations_share_one_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    pool, conn = _mock_pool()

    async def _get_pool() -> Any:
        return pool

    monkeypatch.setattr(canonical_db._CanonicalDbLoop.instance(), "get_pool", _get_pool)
    monkeypatch.setattr(canonical_db, "canonical_db_disabled", lambda: False)

    seen: list[int] = []

    async def _work(active_conn: Any) -> None:
        seen.append(id(active_conn))
        await active_conn.execute("SELECT 1")
        seen.append(id(active_conn))
        await active_conn.execute("SELECT 2")

    canonical_db.run_in_canonical_unit_of_work(_work)

    assert len(seen) == 2
    assert seen[0] == seen[1]
    assert conn.transaction.call_count == 1


def test_pool_reused_across_turns(monkeypatch: pytest.MonkeyPatch) -> None:
    pool, conn = _mock_pool()
    get_pool_calls = 0

    async def _get_pool() -> Any:
        nonlocal get_pool_calls
        get_pool_calls += 1
        return pool

    monkeypatch.setattr(canonical_db._CanonicalDbLoop.instance(), "get_pool", _get_pool)
    monkeypatch.setattr(canonical_db, "canonical_db_disabled", lambda: False)

    async def _noop(active_conn: Any) -> None:
        await active_conn.execute("SELECT 1")

    canonical_db.run_in_canonical_unit_of_work(_noop)
    canonical_db.run_in_canonical_unit_of_work(_noop)

    assert get_pool_calls == 2
    assert conn.transaction.call_count == 2


def test_buffered_events_flush_in_one_unit_of_work(monkeypatch: pytest.MonkeyPatch) -> None:
    pool, conn = _mock_pool()

    async def _get_pool() -> Any:
        return pool

    monkeypatch.setattr(canonical_db._CanonicalDbLoop.instance(), "get_pool", _get_pool)
    monkeypatch.setattr(telemetry, "canonical_db_disabled", lambda: False)

    with canonical_db.planning_turn_scope(turn_id="turn-budget"):
        for _idx in range(12):
            telemetry.persist_planning_event({"event": "lane_router.decided", "trace_id": "t-1"})

    assert conn.transaction.call_count == 1
    assert conn.execute.await_count == 12


def test_connections_per_turn_stays_within_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    pool, conn = _mock_pool()

    async def _get_pool() -> Any:
        return pool

    monkeypatch.setattr(canonical_db._CanonicalDbLoop.instance(), "get_pool", _get_pool)
    monkeypatch.setattr(telemetry, "canonical_db_disabled", lambda: False)

    with canonical_db.planning_turn_scope(turn_id="turn-budget-2"):
        for _idx in range(20):
            telemetry.persist_planning_event({"event": "detail_tool.completed", "trace_id": "t-2"})

        async def _one(active: Any) -> None:
            if active is not None:
                await active.execute("SELECT 1")

        async def _two(active: Any) -> None:
            if active is not None:
                await active.execute("SELECT 2")

        canonical_db.run_in_canonical_unit_of_work(_one)
        canonical_db.run_in_canonical_unit_of_work(_two)
        assert canonical_db.turn_connection_acquisitions() <= canonical_db.MAX_CONNECTIONS_PER_TURN

    assert conn.transaction.call_count <= canonical_db.MAX_CONNECTIONS_PER_TURN
