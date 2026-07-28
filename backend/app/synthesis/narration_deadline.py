"""Monotonic deadline and executor for live synthesis narration.

Never wrap narration in ``with ThreadPoolExecutor()``: ``__exit__`` calls
``shutdown(wait=True)`` and blocks until blocking HTTP failover hops finish,
defeating the outer synthesis wall-clock budget (E5-run-2).
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

# Single worker matches single-slot local model posture; persistent pool avoids
# context-manager shutdown joining orphaned urlopen workers after caller timeout.
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
