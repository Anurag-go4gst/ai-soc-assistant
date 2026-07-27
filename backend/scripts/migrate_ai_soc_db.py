#!/usr/bin/env python3
"""Apply pending AI-SOC database migrations idempotently."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.db.migration_runner import apply_pending_migrations, list_migration_files  # noqa: E402


async def main() -> int:
    sql_files = list_migration_files()
    if not sql_files:
        print("No SQL migrations found.", file=sys.stderr)
        return 2

    conn = await asyncpg.connect(settings.database_url)
    try:
        applied = await apply_pending_migrations(conn)
    finally:
        await conn.close()

    if applied:
        for version in applied:
            print(f"Applied {version}")
    else:
        print("No pending migrations.")
    print("AI-SOC database migrations complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
