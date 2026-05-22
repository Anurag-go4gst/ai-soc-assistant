"""In-process counters for telemetry health surfaces.

Intentionally simple: process-local integer counters readable by
``/health`` and ``/settings/status``. No external metrics backend, no
labels, no histograms. Values never include payloads — only counts.
"""

from __future__ import annotations

from threading import Lock


_lock = Lock()
_counters: dict[str, int] = {
    "telemetry_write_failures": 0,
    "telemetry_writes_skipped_null": 0,
}


def increment(name: str, amount: int = 1) -> None:
    with _lock:
        _counters[name] = _counters.get(name, 0) + amount


def snapshot() -> dict[str, int]:
    with _lock:
        return dict(_counters)


def reset_for_tests() -> None:
    with _lock:
        for key in list(_counters.keys()):
            _counters[key] = 0


__all__ = ["increment", "snapshot", "reset_for_tests"]
