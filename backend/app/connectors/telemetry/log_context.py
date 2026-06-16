"""Phase 4 — correlate log lines with the active chat trace.

A ``contextvars`` holds the current ``trace_id``; a ``LogRecordFactory`` stamps
it onto every ``LogRecord`` so any log line emitted while handling a turn can be
pivoted back to its trace (and vice-versa). Outside a request the value is ``-``.
"""

from __future__ import annotations

import contextvars
import logging
from typing import Any

_TRACE_ID: contextvars.ContextVar[str] = contextvars.ContextVar("ai_soc_trace_id", default="-")

_factory_installed = False


def set_trace_id(trace_id: str | None) -> contextvars.Token:
    return _TRACE_ID.set(trace_id or "-")


def reset_trace_id(token: contextvars.Token | None = None) -> None:
    if token is not None:
        _TRACE_ID.reset(token)
    else:
        _TRACE_ID.set("-")


def current_trace_id() -> str:
    return _TRACE_ID.get()


def install_trace_id_log_factory() -> None:
    """Wrap the active LogRecord factory so every record carries ``trace_id``.

    Idempotent: safe to call more than once (e.g. app startup + tests)."""
    global _factory_installed
    if _factory_installed:
        return
    old_factory = logging.getLogRecordFactory()

    def _factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = old_factory(*args, **kwargs)
        if not hasattr(record, "trace_id"):
            record.trace_id = _TRACE_ID.get()
        return record

    logging.setLogRecordFactory(_factory)
    _factory_installed = True
