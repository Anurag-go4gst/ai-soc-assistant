"""Retention purge for canonical handoffs and planning events (item 28)."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg
import pytest

from app.chat.canonical_db import reset_canonical_db_for_tests
from app.chat.canonical_retention import (
    CanonicalPurgeResult,
    diagnostic_event_retention_days,
    handoff_grace_hours,
    last_purge_summary,
    retention_policy_snapshot,
    run_canonical_retention_purge,
    run_canonical_retention_purge_until_idle,
)
from app.chat.planning_telemetry_policy import (
    AUDIT_CRITICAL_PLANNING_EVENTS,
    DIAGNOSTIC_PLANNING_EVENTS,
)
from app.db.migration_runner import apply_pending_migrations, required_migration_versions
from app.tests.integration.conftest import new_integration_handoff_id

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _postgres_runtime(postgres_integration_runtime: None) -> None:
    reset_canonical_db_for_tests()
    return None


def _handoff_id(suffix: str) -> str:
    return new_integration_handoff_id(f"ret-{suffix}")


async def _insert_handoff(
    url: str,
    *,
    handoff_id: str,
    handoff_version: int,
    status: str,
    expires_at: datetime,
    original_query: str = "sensitive analyst query text",
) -> None:
    conn = await asyncpg.connect(url, timeout=5.0)
    try:
        await conn.execute(
            """
            INSERT INTO canonical_handoffs (
                handoff_id, handoff_version, status, expires_at, original_query, session_id
            ) VALUES ($1, $2, $3, $4, $5, $6)
            """,
            handoff_id,
            handoff_version,
            status,
            expires_at,
            original_query,
            "sess-retention",
        )
    finally:
        await conn.close()


async def _insert_event(
    url: str,
    *,
    event: str,
    created_at: datetime,
    handoff_id: str | None = None,
    handoff_version: int | None = None,
    payload: dict[str, Any] | None = None,
) -> str:
    resolved_handoff_id = handoff_id or new_integration_handoff_id("evt")
    conn = await asyncpg.connect(url, timeout=5.0)
    try:
        await conn.execute(
            """
            INSERT INTO canonical_planning_events (
                event, created_at, handoff_id, handoff_version, payload, trace_id
            ) VALUES ($1, $2, $3, $4, $5::jsonb, $6)
            """,
            event,
            created_at,
            resolved_handoff_id,
            handoff_version if handoff_version is not None else 1,
            json.dumps(payload or {"user_query": "sensitive analyst query text"}),
            f"int-trace-{uuid.uuid4().hex[:8]}",
        )
    finally:
        await conn.close()
    return resolved_handoff_id


async def _count_handoffs(url: str, handoff_id: str) -> int:
    conn = await asyncpg.connect(url, timeout=5.0)
    try:
        return int(
            await conn.fetchval(
                "SELECT COUNT(*) FROM canonical_handoffs WHERE handoff_id = $1",
                handoff_id,
            )
        )
    finally:
        await conn.close()


async def _count_events(
    url: str,
    *,
    event: str | None = None,
    handoff_id: str | None = None,
) -> int:
    conn = await asyncpg.connect(url, timeout=5.0)
    try:
        if event is not None and handoff_id is not None:
            return int(
                await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM canonical_planning_events
                    WHERE event = $1 AND handoff_id = $2
                    """,
                    event,
                    handoff_id,
                )
            )
        if handoff_id is not None:
            return int(
                await conn.fetchval(
                    "SELECT COUNT(*) FROM canonical_planning_events WHERE handoff_id = $1",
                    handoff_id,
                )
            )
        if event is not None:
            return int(
                await conn.fetchval(
                    "SELECT COUNT(*) FROM canonical_planning_events WHERE event = $1",
                    event,
                )
            )
        return int(await conn.fetchval("SELECT COUNT(*) FROM canonical_planning_events"))
    finally:
        await conn.close()


@pytest.fixture()
def retention_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.ai_soc_canonical_handoff_retention_grace_hours", 1)
    monkeypatch.setattr("app.config.settings.ai_soc_canonical_planning_event_diagnostic_retention_days", 1)
    monkeypatch.setattr("app.config.settings.ai_soc_canonical_planning_event_audit_retention_days", 2)
    monkeypatch.setattr("app.config.settings.ai_soc_canonical_retention_purge_batch_size", 2)


def test_required_migrations_include_0006_retention_indexes() -> None:
    versions = required_migration_versions()
    assert "0006_canonical_retention_indexes" in versions


def test_retention_policy_documents_ai_trace_runs_and_windows() -> None:
    policy = retention_policy_snapshot()
    assert policy["ai_trace_runs_automated_purge"] is False
    assert policy["handoff_grace_hours"] == handoff_grace_hours()
    assert policy["diagnostic_event_retention_days"] == diagnostic_event_retention_days()
    assert "handoff.persisted" in AUDIT_CRITICAL_PLANNING_EVENTS
    assert "lane_router.decided" in DIAGNOSTIC_PLANNING_EVENTS


@pytest.mark.asyncio
async def test_migration_0006_is_idempotent(postgres_migrated: str) -> None:
    conn = await asyncpg.connect(postgres_migrated, timeout=5.0)
    try:
        first = await apply_pending_migrations(conn)
        second = await apply_pending_migrations(conn)
        assert second == []
        row = await conn.fetchrow(
            "SELECT 1 FROM pg_indexes WHERE indexname = 'canonical_handoffs_expires_at_status_idx'"
        )
        assert row is not None
        assert "0006_canonical_retention_indexes" in required_migration_versions()
        assert first == [] or "0006_canonical_retention_indexes" in first
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_expired_terminal_handoffs_removed(
    postgres_migrated: str,
    retention_settings: None,
) -> None:
    handoff_id = _handoff_id("terminal")
    expired = datetime.now(UTC) - timedelta(hours=handoff_grace_hours() + 2)
    await _insert_handoff(
        postgres_migrated,
        handoff_id=handoff_id,
        handoff_version=1,
        status="completed",
        expires_at=expired,
    )
    result = run_canonical_retention_purge(batch_size=10)
    assert isinstance(result, CanonicalPurgeResult)
    assert result.handoffs_deleted >= 1
    assert await _count_handoffs(postgres_migrated, handoff_id) == 0


@pytest.mark.asyncio
async def test_live_and_awaiting_clarification_handoffs_preserved(
    postgres_migrated: str,
    retention_settings: None,
) -> None:
    live_id = _handoff_id("live")
    clarify_id = _handoff_id("clarify")
    future = datetime.now(UTC) + timedelta(hours=2)
    await _insert_handoff(
        postgres_migrated,
        handoff_id=live_id,
        handoff_version=1,
        status="planning",
        expires_at=future,
    )
    await _insert_handoff(
        postgres_migrated,
        handoff_id=clarify_id,
        handoff_version=1,
        status="awaiting_clarification",
        expires_at=future,
    )
    run_canonical_retention_purge(batch_size=10)
    assert await _count_handoffs(postgres_migrated, live_id) == 1
    assert await _count_handoffs(postgres_migrated, clarify_id) == 1


@pytest.mark.asyncio
async def test_resumable_current_handoff_versions_preserved(
    postgres_migrated: str,
    retention_settings: None,
) -> None:
    handoff_id = _handoff_id("chain")
    expired = datetime.now(UTC) - timedelta(hours=handoff_grace_hours() + 2)
    future = datetime.now(UTC) + timedelta(hours=2)
    await _insert_handoff(
        postgres_migrated,
        handoff_id=handoff_id,
        handoff_version=1,
        status="completed",
        expires_at=expired,
    )
    await _insert_handoff(
        postgres_migrated,
        handoff_id=handoff_id,
        handoff_version=2,
        status="awaiting_clarification",
        expires_at=future,
    )
    run_canonical_retention_purge(batch_size=10)
    assert await _count_handoffs(postgres_migrated, handoff_id) == 2


@pytest.mark.asyncio
async def test_old_eligible_events_removed_recent_events_preserved(
    postgres_migrated: str,
    retention_settings: None,
) -> None:
    old_at = datetime.now(UTC) - timedelta(days=diagnostic_event_retention_days() + 1)
    recent_at = datetime.now(UTC) - timedelta(hours=1)
    scope_id = new_integration_handoff_id("evt-scope")
    await _insert_event(
        postgres_migrated,
        event="lane_router.decided",
        created_at=old_at,
        handoff_id=scope_id,
    )
    await _insert_event(
        postgres_migrated,
        event="lane_router.decided",
        created_at=recent_at,
        handoff_id=scope_id,
    )
    before = await _count_events(
        postgres_migrated,
        event="lane_router.decided",
        handoff_id=scope_id,
    )
    result = run_canonical_retention_purge(batch_size=10)
    assert result.diagnostic_events_deleted >= 1
    after = await _count_events(
        postgres_migrated,
        event="lane_router.decided",
        handoff_id=scope_id,
    )
    assert after < before
    assert after >= 1


@pytest.mark.asyncio
async def test_audit_critical_retention_window_longer_than_diagnostic(
    postgres_migrated: str,
    retention_settings: None,
) -> None:
    diag_old = datetime.now(UTC) - timedelta(days=diagnostic_event_retention_days() + 1)
    audit_mid = datetime.now(UTC) - timedelta(days=diagnostic_event_retention_days())
    scope_id = new_integration_handoff_id("audit-scope")
    await _insert_event(
        postgres_migrated,
        event="lane_router.decided",
        created_at=diag_old,
        handoff_id=scope_id,
    )
    await _insert_event(
        postgres_migrated,
        event="handoff.persisted",
        created_at=audit_mid,
        handoff_id=scope_id,
    )
    run_canonical_retention_purge(batch_size=10)
    assert (
        await _count_events(
            postgres_migrated,
            event="lane_router.decided",
            handoff_id=scope_id,
        )
        == 0
    )
    assert (
        await _count_events(
            postgres_migrated,
            event="handoff.persisted",
            handoff_id=scope_id,
        )
        == 1
    )


@pytest.mark.asyncio
async def test_bounded_batch_size(
    postgres_migrated: str,
    retention_settings: None,
) -> None:
    expired = datetime.now(UTC) - timedelta(hours=handoff_grace_hours() + 2)
    for idx in range(4):
        await _insert_handoff(
            postgres_migrated,
            handoff_id=_handoff_id(f"batch-{idx}"),
            handoff_version=1,
            status="failed",
            expires_at=expired,
        )
    result = run_canonical_retention_purge(batch_size=2)
    assert result.handoffs_deleted == 2


@pytest.mark.asyncio
async def test_multiple_batches_eventually_clear_all_eligible_rows(
    postgres_migrated: str,
    retention_settings: None,
) -> None:
    expired = datetime.now(UTC) - timedelta(hours=handoff_grace_hours() + 2)
    ids = [_handoff_id(f"multi-{idx}") for idx in range(5)]
    for handoff_id in ids:
        await _insert_handoff(
            postgres_migrated,
            handoff_id=handoff_id,
            handoff_version=1,
            status="expired",
            expires_at=expired,
        )
    result = run_canonical_retention_purge_until_idle(batch_size=2, max_batches=10)
    assert result.handoffs_deleted >= 5
    for handoff_id in ids:
        assert await _count_handoffs(postgres_migrated, handoff_id) == 0


@pytest.mark.asyncio
async def test_purge_is_idempotent(
    postgres_migrated: str,
    retention_settings: None,
) -> None:
    handoff_id = _handoff_id("idempotent")
    expired = datetime.now(UTC) - timedelta(hours=handoff_grace_hours() + 2)
    await _insert_handoff(
        postgres_migrated,
        handoff_id=handoff_id,
        handoff_version=1,
        status="completed",
        expires_at=expired,
    )
    first = run_canonical_retention_purge(batch_size=10)
    second = run_canonical_retention_purge(batch_size=10)
    assert first.handoffs_deleted >= 1
    assert second.handoffs_deleted == 0
    assert second.error_category is None


@pytest.mark.asyncio
async def test_concurrent_resumption_protected_rows_not_deleted(
    postgres_migrated: str,
    retention_settings: None,
) -> None:
    handoff_id = _handoff_id("lease")
    expired = datetime.now(UTC) - timedelta(hours=handoff_grace_hours() + 2)
    await _insert_handoff(
        postgres_migrated,
        handoff_id=handoff_id,
        handoff_version=1,
        status="completed",
        expires_at=expired,
    )
    conn = await asyncpg.connect(postgres_migrated, timeout=5.0)
    try:
        await conn.execute(
            """
            INSERT INTO canonical_execution_idempotency (
                resource_plan_id, step_id, idempotency_key, handoff_id, handoff_version,
                status, lease_owner, lease_expires_at
            ) VALUES ($1, $2, $3, $4, 1, 'running', 'worker-a', now() + interval '1 hour')
            """,
            "rp:lease",
            "step-1",
            f"idem-{uuid.uuid4().hex}",
            handoff_id,
        )
    finally:
        await conn.close()
    result = run_canonical_retention_purge(batch_size=10)
    assert result.handoffs_deleted == 0
    assert await _count_handoffs(postgres_migrated, handoff_id) == 1


@pytest.mark.asyncio
async def test_rollback_on_failure_leaves_rows(
    postgres_migrated: str,
    retention_settings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handoff_id = _handoff_id("rollback")
    expired = datetime.now(UTC) - timedelta(hours=handoff_grace_hours() + 2)
    await _insert_handoff(
        postgres_migrated,
        handoff_id=handoff_id,
        handoff_version=1,
        status="completed",
        expires_at=expired,
    )

    async def _boom(*_args: Any, **_kwargs: Any) -> int:
        raise RuntimeError("simulated purge failure")

    monkeypatch.setattr(
        "app.chat.canonical_retention._purge_handoffs_batch",
        _boom,
    )
    result = run_canonical_retention_purge(batch_size=10)
    assert result.error_category == "RuntimeError"
    assert await _count_handoffs(postgres_migrated, handoff_id) == 1


def test_logged_counts_contain_no_soc_content(
    postgres_migrated: str,
    retention_settings: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="ai_soc.canonical_retention")
    expired = datetime.now(UTC) - timedelta(hours=handoff_grace_hours() + 2)
    asyncio.run(
        _insert_handoff(
            postgres_migrated,
            handoff_id=_handoff_id("log"),
            handoff_version=1,
            status="failed",
            expires_at=expired,
            original_query="TOP SECRET analyst query must not appear in logs",
        )
    )
    run_canonical_retention_purge(batch_size=5)
    summary = last_purge_summary()
    assert summary is not None
    serialized = str(summary) + caplog.text
    assert "TOP SECRET analyst query must not appear in logs" not in serialized
    assert "handoffs_deleted" in serialized
