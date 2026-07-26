"""Canonical handoff persistence integration tests."""

from __future__ import annotations

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

from app.chat.canonical_db import reset_canonical_db_for_tests
from app.chat.canonical_handoff_models import CanonicalHandoffRecord
from app.chat.canonical_handoff_store import (
    commit_resource_plan,
    get_handoff,
    save_clarification_handoff,
    save_handoff,
)
from app.tests.integration.conftest import new_integration_handoff_id

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _postgres_runtime(postgres_integration_runtime: None) -> None:
    """Bind each module to the shared Postgres runtime fixture."""
    return None


def test_handoff_creation_round_trip(postgres_migrated: str) -> None:
    handoff_id = new_integration_handoff_id("create")
    saved = save_handoff(
        CanonicalHandoffRecord(
            handoff_id=handoff_id,
            handoff_version=1,
            status="in_progress",
            session_id="sess-create",
            original_query="integration handoff create",
        )
    )
    loaded = get_handoff(handoff_id, 1)
    assert loaded is not None
    assert loaded.handoff_id == handoff_id
    assert loaded.status == saved.status
    assert loaded.original_query == "integration handoff create"


@pytest.mark.asyncio
async def test_unique_handoff_version_constraint(postgres_migrated: str) -> None:
    handoff_id = new_integration_handoff_id("uniq")
    conn = await asyncpg.connect(postgres_migrated, timeout=5.0)
    try:
        await conn.execute(
            """
            INSERT INTO canonical_handoffs (handoff_id, handoff_version, status, expires_at)
            VALUES ($1, 1, 'created', now() + interval '1 hour')
            """,
            handoff_id,
        )
        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(
                """
                INSERT INTO canonical_handoffs (handoff_id, handoff_version, status, expires_at)
                VALUES ($1, 1, 'awaiting_clarification', now() + interval '1 hour')
                """,
                handoff_id,
            )
    finally:
        await conn.close()


def test_concurrent_resource_plan_commit_is_idempotent(postgres_migrated: str) -> None:
    handoff_id = new_integration_handoff_id("commit-race")
    save_handoff(
        CanonicalHandoffRecord(
            handoff_id=handoff_id,
            handoff_version=1,
            status="in_progress",
            session_id="sess-commit",
        )
    )
    resource_plan = {
        "steps": [],
        "plan_source": "deterministic",
        "provenance": {"committed": True},
    }
    evidence_plan = {"answer_mode": "rag_only", "resource_plan": resource_plan}

    def _commit() -> CanonicalHandoffRecord:
        return commit_resource_plan(
            handoff_id=handoff_id,
            handoff_version=1,
            resource_plan_id="rp:race",
            resource_plan=resource_plan,
            evidence_plan=evidence_plan,
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(lambda _: _commit(), range(4)))

    assert all(record.committed_resource_plan_id == "rp:race" for record in records)
    loaded = get_handoff(handoff_id, 1)
    assert loaded is not None
    assert loaded.status == "plan_committed"


def test_process_restart_reload_preserves_handoff(postgres_migrated: str) -> None:
    handoff_id = new_integration_handoff_id("restart")
    save_clarification_handoff(
        handoff_id=handoff_id,
        handoff_version=1,
        canonical_planning_input={"routing": {"processing_lane": "known"}},
        gap_resolution=None,
        unresolved_fields=["alert_id"],
        clarification_reason="missing_alert_id",
        session_id="sess-restart",
        original_query="What happened?",
    )
    reset_canonical_db_for_tests()
    reloaded = get_handoff(handoff_id, 1)
    assert reloaded is not None
    assert reloaded.status == "awaiting_clarification"
    assert reloaded.unresolved_fields == ["alert_id"]


def test_expired_handoff_is_not_returned(postgres_migrated: str) -> None:
    handoff_id = new_integration_handoff_id("expired")
    expired_at = datetime.now(UTC) - timedelta(minutes=5)
    save_handoff(
        CanonicalHandoffRecord(
            handoff_id=handoff_id,
            handoff_version=1,
            status="awaiting_clarification",
            session_id="sess-expired",
            expires_at=expired_at,
        ),
        refresh_ttl=False,
    )
    assert get_handoff(handoff_id, 1) is None


@pytest.mark.asyncio
async def test_transaction_rollback_leaves_no_partial_handoff(postgres_migrated: str) -> None:
    handoff_id = new_integration_handoff_id("rollback")
    conn = await asyncpg.connect(postgres_migrated, timeout=5.0)
    try:
        transaction = conn.transaction()
        await transaction.start()
        try:
            await conn.execute(
                """
                INSERT INTO canonical_handoffs (handoff_id, handoff_version, status, expires_at)
                VALUES ($1, 1, 'created', now() + interval '1 hour')
                """,
                handoff_id,
            )
        finally:
            await transaction.rollback()

        row = await conn.fetchrow(
            "SELECT 1 FROM canonical_handoffs WHERE handoff_id = $1 AND handoff_version = 1",
            handoff_id,
        )
        assert row is None
    finally:
        await conn.close()


def test_multiple_pending_handoffs_remain_isolated(postgres_migrated: str) -> None:
    session_id = f"sess-multi-{uuid.uuid4().hex[:8]}"
    first_id = new_integration_handoff_id("pending-a")
    second_id = new_integration_handoff_id("pending-b")
    save_clarification_handoff(
        handoff_id=first_id,
        handoff_version=1,
        canonical_planning_input={"routing": {"answer_goal": "live_investigation"}},
        gap_resolution=None,
        unresolved_fields=["alert_id"],
        clarification_reason="missing_alert_id",
        session_id=session_id,
    )
    save_clarification_handoff(
        handoff_id=second_id,
        handoff_version=1,
        canonical_planning_input={"routing": {"answer_goal": "spl_artifact"}},
        gap_resolution=None,
        unresolved_fields=["index"],
        clarification_reason="missing_index",
        session_id=session_id,
    )
    first = get_handoff(first_id, 1)
    second = get_handoff(second_id, 1)
    assert first is not None and second is not None
    assert first.original_answer_goal != second.original_answer_goal or first.unresolved_fields != second.unresolved_fields


def test_material_goal_change_creates_separate_handoff(postgres_migrated: str) -> None:
    session_id = f"sess-goal-{uuid.uuid4().hex[:8]}"
    original_id = new_integration_handoff_id("goal-original")
    superseding_id = new_integration_handoff_id("goal-new")
    save_clarification_handoff(
        handoff_id=original_id,
        handoff_version=1,
        canonical_planning_input={"routing": {"answer_goal": "live_investigation"}},
        gap_resolution=None,
        unresolved_fields=["alert_id"],
        clarification_reason="missing_alert_id",
        session_id=session_id,
        original_answer_goal="live_investigation",
    )
    save_handoff(
        CanonicalHandoffRecord(
            handoff_id=superseding_id,
            handoff_version=1,
            status="in_progress",
            session_id=session_id,
            original_answer_goal="spl_artifact",
            original_query="Generate SPL for failed logins",
        )
    )
    original = get_handoff(original_id, 1)
    superseding = get_handoff(superseding_id, 1)
    assert original is not None and superseding is not None
    assert original.status == "awaiting_clarification"
    assert superseding.original_answer_goal == "spl_artifact"
