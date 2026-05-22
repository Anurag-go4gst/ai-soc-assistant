#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402


async def main() -> int:
    migrations_dir = ROOT / "app" / "db" / "migrations"
    sql_files = sorted(migrations_dir.glob("*.sql"))
    if not sql_files:
        print(f"No SQL migrations found in {migrations_dir}", file=sys.stderr)
        return 2

    conn = await asyncpg.connect(settings.database_url)
    try:
        for sql_file in sql_files:
            print(f"Applying {sql_file.name} ...")
            await conn.execute(sql_file.read_text(encoding="utf-8"))
    finally:
        await conn.close()

    print("AI-SOC database migrations complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
