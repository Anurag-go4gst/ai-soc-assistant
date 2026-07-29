"""Monotonic deadline and executor for live synthesis narration.

Never wrap narration in ``with ThreadPoolExecutor()``: ``__exit__`` calls
``shutdown(wait=True)`` and blocks until blocking HTTP failover hops finish,
defeating the outer synthesis wall-clock budget (E5-run-2).

Admission uses a single-slot semaphore acquired *before* executor submit so
saturated requests fail closed instead of queueing past their deadline.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import TypeVar

T = TypeVar("T")

# One in-flight narration matches single-slot local model posture. try_acquire only —
# do not queue synthesis jobs behind an orphaned urlopen worker.
_NARRATION_SLOT = threading.BoundedSemaphore(1)

SYNTHESIS_NARRATION_EXECUTOR = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="synthesis-narration",
)

# Do not start a new failover hop when less than this remains on the deadline.
_MIN_HOP_BUDGET_SECONDS = 0.05


def remaining_seconds(deadline: float) -> float:
    """Seconds left until monotonic ``deadline``."""
    return deadline - time.monotonic()


def budget_exhausted(deadline: float | None) -> bool:
    if deadline is None:
        return False
    return remaining_seconds(deadline) <= _MIN_HOP_BUDGET_SECONDS


def hop_timeout_seconds(client_timeout: int, deadline: float | None) -> float | None:
    """Per-hop socket timeout capped by remaining deadline; ``None`` = use client default."""
    if deadline is None:
        return None
    remaining = remaining_seconds(deadline)
    if remaining <= _MIN_HOP_BUDGET_SECONDS:
        return None
    return min(float(client_timeout), remaining)


def should_attempt_hop(deadline: float | None) -> bool:
    if deadline is None:
        return True
    return remaining_seconds(deadline) > _MIN_HOP_BUDGET_SECONDS


def narration_slot_available() -> bool:
    """Non-blocking probe: True when narration can start immediately."""
    acquired = _NARRATION_SLOT.acquire(blocking=False)
    if acquired:
        _NARRATION_SLOT.release()
        return True
    return False


def try_submit_narration(
    fn: Callable[..., T],
    /,
    *args: object,
    **kwargs: object,
) -> Future[T] | None:
    """
    Submit ``fn`` only when the narration slot is free.

    Returns ``None`` when saturated (another narration is in-flight) so callers
    fail closed to deterministic fallback without queueing past the deadline.
    """
    if not _NARRATION_SLOT.acquire(blocking=False):
        return None

    def _guarded() -> T:
        try:
            return fn(*args, **kwargs)
        finally:
            _NARRATION_SLOT.release()

    try:
        return SYNTHESIS_NARRATION_EXECUTOR.submit(_guarded)
    except Exception:
        _NARRATION_SLOT.release()
        return None


def release_narration_slot_for_tests() -> None:
    """Best-effort slot release for isolated executor safety tests."""
    try:
        _NARRATION_SLOT.release()
    except ValueError:
        pass
