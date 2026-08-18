"""Migration deployment readiness (plan item 18a)."""

from __future__ import annotations

import asyncio
import os
import warnings
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock

import asyncpg
import pytest

from app.api.routes_health import health
from app.chat import canonical_handoff_repository as handoff_repo
from app.config import settings
from app.db.migration_runner import (
    apply_pending_migrations,
    migration_remediation_command,
    required_migration_versions,
)
from app.db.migration_readiness import build_migration_readiness

DEFAULT_LOCAL_DATABASE_URL = (
    "postgresql://ai_soc:ai_soc_dev_password@127.0.0.1:5434/ai_soc_assistant"
)


@pytest.fixture(scope="module")
def migrated_database_url() -> Iterator[str]:
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url or "change-me@postgres" in url:
        url = DEFAULT_LOCAL_DATABASE_URL

    original_settings_url = settings.database_url
    original_env_url = os.environ.get("DATABASE_URL")

    async def _migrate() -> None:
        conn = await asyncpg.connect(url, timeout=5.0)
        try:
            await apply_pending_migrations(conn)
        finally:
            await conn.close()

    try:
        asyncio.run(_migrate())
    except Exception as exc:
        pytest.skip(f"PostgreSQL not available for migration-readiness tests: {exc}")

    os.environ["DATABASE_URL"] = url
    settings.database_url = url
    try:
        yield url
    finally:
        if original_env_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original_env_url
        settings.database_url = original_settings_url


def test_required_migration_versions_lists_all_sql_files() -> None:
    versions = required_migration_versions()
    assert versions == [
        "0001_ai_soc_telemetry",
        "0002_answer_quality",
        "0003_ai_soc_telemetry_indexes",
        "0004_canonical_handoffs",
        "0005_canonical_planning_cutover_constraints",
        "0006_canonical_retention_indexes",
        "0007_mcp_discovery_snapshot",
    ]


@pytest.mark.asyncio
async def test_apply_pending_migrations_skips_recorded_versions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sql_a = tmp_path / "0001_test.sql"
    sql_b = tmp_path / "0002_test.sql"
    sql_a.write_text(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now());\n"
        "INSERT INTO schema_migrations (version) VALUES ('0001_test') ON CONFLICT DO NOTHING;\n",
        encoding="utf-8",
    )
    sql_b.write_text(
        "INSERT INTO schema_migrations (version) VALUES ('0002_test') ON CONFLICT DO NOTHING;\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("app.db.migration_runner.MIGRATIONS_DIR", tmp_path)
    monkeypatch.setattr(
        "app.db.migration_runner.list_migration_files",
        lambda: sorted(tmp_path.glob("*.sql")),
    )

    conn = AsyncMock()
    conn.fetch.return_value = [{"version": "0001_test"}]
    applied = await apply_pending_migrations(conn)
    assert applied == ["0002_test"]
    assert conn.execute.await_count == 2


def test_canonical_handoff_repository_has_no_runtime_sql_migration() -> None:
    source = Path(handoff_repo.__file__).read_text(encoding="utf-8")
    assert "_ensure_schema" not in source
    assert "_MIGRATION_PATH" not in source
    assert ".sql" not in source


def test_health_includes_migration_readiness(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setattr(
        "app.api.routes_health.build_migration_readiness",
        lambda: {
            "ready": True,
            "configured": True,
            "required_versions": required_migration_versions(),
            "missing_versions": [],
            "remediation": migration_remediation_command(),
            "detail": "ok",
        },
    )
    client = TestClient(app)
    payload = client.get("/health").json()
    readiness = payload["readiness"]["database_migrations"]
    assert readiness["ready"] is True
    assert readiness["required_versions"] == required_migration_versions()


def test_migration_remediation_command_is_documented() -> None:
    assert "migrate_ai_soc_db.py" in migration_remediation_command()


@pytest.mark.asyncio
async def test_build_migration_readiness_from_active_event_loop(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "database_url", migrated_database_url)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = build_migration_readiness()
    assert not any("never awaited" in str(warning.message) for warning in caught)
    assert result["ready"] is True
    assert result["configured"] is True
    assert result["missing_versions"] == []
    assert result["detail"] == "ok"


@pytest.mark.asyncio
async def test_health_migration_readiness_from_active_event_loop(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "database_url", migrated_database_url)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for _ in range(3):
            payload = health()
            readiness = payload["readiness"]["database_migrations"]
            assert readiness["ready"] is True
            assert readiness["detail"] == "ok"
    assert not any("never awaited" in str(warning.message) for warning in caught)
    assert not any(
        "asyncio.run() cannot be called from a running event loop" in str(warning.message)
        for warning in caught
    )


@pytest.mark.asyncio
async def test_missing_migrations_fail_closed_from_active_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = AsyncMock()
    conn.fetch.return_value = []

    async def _fake_connect(*_args: object, **_kwargs: object) -> AsyncMock:
        return conn

    monkeypatch.setattr(
        "app.db.migration_readiness.asyncpg.connect",
        _fake_connect,
    )
    monkeypatch.setattr(
        settings,
        "database_url",
        "postgresql://ai_soc:ai_soc_dev_password@127.0.0.1:5434/ai_soc_assistant",
    )
    result = build_migration_readiness()
    assert result["ready"] is False
    assert result["configured"] is True
    assert result["missing_versions"] == required_migration_versions()
    assert result["detail"] == "pending migrations"


@pytest.mark.asyncio
async def test_unexpected_readiness_error_surfaces_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _boom_connect(*_args: object, **_kwargs: object) -> None:
        raise OSError("connection refused")

    monkeypatch.setattr(
        "app.db.migration_readiness.asyncpg.connect",
        _boom_connect,
    )
    monkeypatch.setattr(
        settings,
        "database_url",
        "postgresql://ai_soc:ai_soc_dev_password@127.0.0.1:5434/ai_soc_assistant",
    )
    result = build_migration_readiness()
    assert result["ready"] is False
    assert result["configured"] is True
    assert result["missing_versions"] == required_migration_versions()
    assert result["detail"] == "check_failed:OSError"
