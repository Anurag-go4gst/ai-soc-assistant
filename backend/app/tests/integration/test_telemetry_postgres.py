"""Planning telemetry persistence integration tests."""

from __future__ import annotations

import asyncio
import uuid

import asyncpg
import pytest

from app.chat.durable_planning_telemetry import persist_planning_event
from app.tests.integration.conftest import new_integration_handoff_id

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _postgres_runtime(postgres_integration_runtime: None) -> None:
    return None


def test_audit_critical_planning_event_persisted_to_postgres(postgres_migrated: str) -> None:
    trace_id = f"int-{uuid.uuid4().hex}"
    decision_id = f"int-decision-{uuid.uuid4().hex[:12]}"
    handoff_id = new_integration_handoff_id("telemetry")
    persist_planning_event(
        {
            "event": "execution.started",
            "trace_id": trace_id,
            "decision_id": decision_id,
            "handoff_id": handoff_id,
            "handoff_version": 1,
            "resource_plan_id": "rp:int-telemetry",
            "node_name": "execution",
            "status": "started",
        },
        immediate=True,
    )

    async def _fetch() -> asyncpg.Record | None:
        conn = await asyncpg.connect(postgres_migrated, timeout=5.0)
        try:
            return await conn.fetchrow(
                "SELECT event, trace_id, decision_id FROM canonical_planning_events WHERE decision_id = $1",
                decision_id,
            )
        finally:
            await conn.close()

    row = asyncio.run(_fetch())
    assert row is not None
    assert row["event"] == "execution.started"
    assert row["trace_id"] == trace_id


@pytest.mark.asyncio
async def test_planning_event_decision_id_unique_constraint(postgres_migrated: str) -> None:
    decision_id = f"int-dedup-{uuid.uuid4().hex[:12]}"
    trace_id = f"int-{uuid.uuid4().hex}"
    conn = await asyncpg.connect(postgres_migrated, timeout=5.0)
    try:
        await conn.execute(
            """
            INSERT INTO canonical_planning_events (event, trace_id, decision_id, payload)
            VALUES ('execution.started', $1, $2, '{}'::jsonb)
            """,
            trace_id,
            decision_id,
        )
        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(
                """
                INSERT INTO canonical_planning_events (event, trace_id, decision_id, payload)
                VALUES ('execution.completed', $1, $2, '{}'::jsonb)
                """,
                trace_id,
                decision_id,
            )
    finally:
        await conn.close()
