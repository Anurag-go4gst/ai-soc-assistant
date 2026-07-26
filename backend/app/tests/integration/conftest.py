"""Shared fixtures for PostgreSQL integration tests (plan item 24)."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Iterator

import asyncpg
import pytest

from app.config import settings
from app.db.migration_runner import apply_pending_migrations

pytestmark = pytest.mark.integration

DEFAULT_LOCAL_DATABASE_URL = (
    "postgresql://ai_soc:ai_soc_dev_password@127.0.0.1:5434/ai_soc_assistant"
)


def configured_database_url() -> str | None:
    url = (os.environ.get("DATABASE_URL") or settings.database_url or "").strip()
    if not url or "change-me@postgres" in url:
        return None
    return url


def new_integration_handoff_id(suffix: str) -> str:
    return f"int:{suffix}:{uuid.uuid4().hex[:10]}"


async def _ping_database(url: str) -> None:
    conn = await asyncpg.connect(url, timeout=3.0)
    try:
        await conn.execute("SELECT 1")
    finally:
        await conn.close()


async def _truncate_integration_rows(url: str) -> None:
    conn = await asyncpg.connect(url, timeout=5.0)
    try:
        await conn.execute(
            """
            DELETE FROM canonical_planning_events
            WHERE handoff_id LIKE 'int:%' OR trace_id LIKE 'int-%'
            """
        )
        await conn.execute(
            "DELETE FROM canonical_execution_idempotency WHERE handoff_id LIKE 'int:%'"
        )
        await conn.execute("DELETE FROM canonical_handoffs WHERE handoff_id LIKE 'int:%'")
    finally:
        await conn.close()


@pytest.fixture(scope="session")
def postgres_database_url() -> str:
    url = configured_database_url() or DEFAULT_LOCAL_DATABASE_URL
    try:
        asyncio.run(_ping_database(url))
    except Exception as exc:
        pytest.skip(f"PostgreSQL not available for integration tests: {exc}")
    return url


@pytest.fixture(scope="session")
def postgres_migrated(postgres_database_url: str) -> str:
    os.environ["DATABASE_URL"] = postgres_database_url
    settings.database_url = postgres_database_url

    async def migrate() -> None:
        conn = await asyncpg.connect(postgres_database_url, timeout=5.0)
        try:
            await apply_pending_migrations(conn)
        finally:
            await conn.close()

    asyncio.run(migrate())
    return postgres_database_url


@pytest.fixture
def postgres_integration_runtime(postgres_migrated: str) -> Iterator[None]:
    from app.chat import canonical_execution_idempotency as exec_idem
    from app.chat import canonical_handoff_repository as handoff_repo
    from app.chat import durable_planning_telemetry as telemetry
    from app.chat.canonical_db import reset_canonical_db_for_tests

    settings.database_url = postgres_migrated
    handoff_repo.use_in_memory_store_for_tests(False)
    exec_idem.use_in_memory_store_for_tests(False)
    telemetry.use_test_event_store(False)

    yield

    asyncio.run(_truncate_integration_rows(postgres_migrated))
    reset_canonical_db_for_tests()
