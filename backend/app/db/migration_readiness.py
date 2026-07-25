"""Database migration readiness checks for startup and /health."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import asyncpg

from app.config import settings
from app.db.migration_runner import (
    migration_remediation_command,
    missing_migration_versions,
    required_migration_versions,
)

_LOGGER = logging.getLogger("ai_soc.migrations")


def _database_configured() -> bool:
    url = (settings.database_url or "").strip()
    return bool(url) and "change-me@postgres" not in url


async def _check_with_connection() -> dict[str, Any]:
    if not _database_configured():
        return {
            "ready": False,
            "configured": False,
            "required_versions": required_migration_versions(),
            "missing_versions": required_migration_versions(),
            "remediation": migration_remediation_command(),
            "detail": "database_url not configured",
        }
    conn = await asyncpg.connect(settings.database_url, timeout=2.0)
    try:
        missing = await missing_migration_versions(conn)
    finally:
        await conn.close()
    return {
        "ready": not missing,
        "configured": True,
        "required_versions": required_migration_versions(),
        "missing_versions": missing,
        "remediation": migration_remediation_command(),
        "detail": "ok" if not missing else "pending migrations",
    }


def build_migration_readiness() -> dict[str, Any]:
    if not _database_configured():
        return asyncio.run(_check_with_connection())
    try:
        return asyncio.run(_check_with_connection())
    except Exception as exc:  # noqa: BLE001 — readiness must not break health
        _LOGGER.warning("migration_readiness_check_failed", exc_info=True)
        return {
            "ready": False,
            "configured": True,
            "required_versions": required_migration_versions(),
            "missing_versions": required_migration_versions(),
            "remediation": migration_remediation_command(),
            "detail": f"check_failed:{type(exc).__name__}",
        }


def log_startup_migration_readiness() -> None:
    readiness = build_migration_readiness()
    if readiness.get("ready"):
        _LOGGER.info(
            "database_migrations_ready versions=%s",
            ",".join(readiness.get("required_versions") or []),
        )
        return
    _LOGGER.error(
        "database_migrations_not_ready missing=%s remediation=%s detail=%s",
        readiness.get("missing_versions"),
        readiness.get("remediation"),
        readiness.get("detail"),
    )
