"""Periodic canonical retention purge scheduler (item 28)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.chat.canonical_retention import purge_enabled, purge_interval_seconds, run_canonical_retention_purge

_LOGGER = logging.getLogger("ai_soc.canonical_retention_scheduler")

_TASK: asyncio.Task[None] | None = None


async def _purge_loop() -> None:
    interval = purge_interval_seconds()
    while True:
        try:
            await asyncio.to_thread(run_canonical_retention_purge)
        except Exception:
            _LOGGER.warning("canonical_retention_scheduler_tick_failed", exc_info=True)
        await asyncio.sleep(interval)


def start_canonical_retention_scheduler() -> asyncio.Task[None] | None:
    """Start the background purge loop when enabled and canonical DB is configured."""
    global _TASK
    if not purge_enabled():
        return None
    if _TASK is not None and not _TASK.done():
        return _TASK
    _TASK = asyncio.create_task(_purge_loop(), name="canonical-retention-purge")
    _LOGGER.info(
        "canonical_retention_scheduler_started",
        extra={"interval_seconds": purge_interval_seconds()},
    )
    return _TASK


async def stop_canonical_retention_scheduler(task: asyncio.Task[None] | None = None) -> None:
    global _TASK
    active = task or _TASK
    if active is None:
        return
    active.cancel()
    try:
        await active
    except asyncio.CancelledError:
        pass
    if _TASK is active:
        _TASK = None
    _LOGGER.info("canonical_retention_scheduler_stopped")


def scheduler_status() -> dict[str, Any]:
    running = _TASK is not None and not _TASK.done()
    return {
        "enabled": purge_enabled(),
        "running": running,
        "interval_seconds": purge_interval_seconds(),
    }
