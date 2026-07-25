"""Idempotent AI-SOC database migration runner."""

from __future__ import annotations

from pathlib import Path

import asyncpg

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
REMEDIATION_COMMAND = "docker compose exec backend python scripts/migrate_ai_soc_db.py"

_SCHEMA_MIGRATIONS_BOOTSTRAP = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def list_migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def required_migration_versions() -> list[str]:
    return [path.stem for path in list_migration_files()]


def migration_remediation_command() -> str:
    return REMEDIATION_COMMAND


async def _applied_versions(conn: asyncpg.Connection) -> set[str]:
    await conn.execute(_SCHEMA_MIGRATIONS_BOOTSTRAP)
    rows = await conn.fetch("SELECT version FROM schema_migrations")
    return {str(row["version"]) for row in rows}


async def apply_pending_migrations(conn: asyncpg.Connection) -> list[str]:
    """Apply migrations not yet recorded in ``schema_migrations``."""
    applied_versions = await _applied_versions(conn)
    newly_applied: list[str] = []
    for sql_file in list_migration_files():
        version = sql_file.stem
        if version in applied_versions:
            continue
        await conn.execute(sql_file.read_text(encoding="utf-8"))
        newly_applied.append(version)
        applied_versions.add(version)
    return newly_applied


async def missing_migration_versions(conn: asyncpg.Connection) -> list[str]:
    applied_versions = await _applied_versions(conn)
    return [version for version in required_migration_versions() if version not in applied_versions]


async def migrations_ready(conn: asyncpg.Connection) -> bool:
    return not await missing_migration_versions(conn)
