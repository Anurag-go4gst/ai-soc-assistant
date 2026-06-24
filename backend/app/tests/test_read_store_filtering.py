"""Read-store list-trace filtering + orphan-fallback gating.

Regression: a filtered ``/debug/traces`` query that legitimately matched zero
run rows used to fall through to the orphan-steps recovery view, which ignores
filters and returned unrelated synthetic rows (e.g. ``?status=abandoned`` showed
``orphan_steps``). The fallback must only fire for an unfiltered list.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.config import settings
from app.connectors.telemetry import read_store


class _FakeConn:
    """Minimal asyncpg-conn stand-in recording each fetched SQL."""

    def __init__(self, *, main_rows: list[Any], orphan_rows: list[Any]) -> None:
        self._main_rows = main_rows
        self._orphan_rows = orphan_rows
        self.fetched_sql: list[str] = []

    async def fetch(self, sql: str, *args: Any) -> list[Any]:
        self.fetched_sql.append(sql)
        return self._orphan_rows if "FROM ai_trace_steps" in sql else self._main_rows

    async def close(self) -> None:  # pragma: no cover - trivial
        return None


@pytest.fixture(autouse=True)
def _db_sink(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_telemetry_sink", "db")


def _patch_conn(monkeypatch: pytest.MonkeyPatch, conn: _FakeConn) -> None:
    async def _fake_connect() -> _FakeConn:
        return conn

    monkeypatch.setattr(read_store, "_connect", _fake_connect)


def test_filtered_empty_query_does_not_fall_back_to_orphans(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _FakeConn(main_rows=[], orphan_rows=[{"trace_id": "x", "last_event_at": None, "event_count": 3}])
    _patch_conn(monkeypatch, conn)

    runs = read_store.list_trace_runs(status="abandoned")

    assert runs == []
    assert not any("FROM ai_trace_steps" in sql for sql in conn.fetched_sql)


def test_unfiltered_empty_query_still_surfaces_orphan_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _FakeConn(main_rows=[], orphan_rows=[{"trace_id": "x", "last_event_at": None, "event_count": 3}])
    _patch_conn(monkeypatch, conn)

    runs = read_store.list_trace_runs()

    assert len(runs) == 1
    assert runs[0]["status"] == "orphan_steps"
    assert any("FROM ai_trace_steps" in sql for sql in conn.fetched_sql)


def test_reaper_present_and_no_op_on_non_db_sinks() -> None:
    from app.connectors.telemetry.file import FileTelemetryConnector
    from app.connectors.telemetry.null import NullTelemetryConnector

    # No-op sinks must accept the call without raising (best-effort contract).
    NullTelemetryConnector().reap_stale_running_runs()
    FileTelemetryConnector().reap_stale_running_runs(older_than_seconds=10)
