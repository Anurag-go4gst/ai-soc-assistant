"""Migration deployment readiness (plan item 18a)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.chat import canonical_handoff_repository as handoff_repo
from app.db.migration_runner import (
    apply_pending_migrations,
    migration_remediation_command,
    required_migration_versions,
)
from app.db.migration_readiness import build_migration_readiness


def test_required_migration_versions_lists_all_sql_files() -> None:
    versions = required_migration_versions()
    assert versions == [
        "0001_ai_soc_telemetry",
        "0002_answer_quality",
        "0003_ai_soc_telemetry_indexes",
        "0004_canonical_handoffs",
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
