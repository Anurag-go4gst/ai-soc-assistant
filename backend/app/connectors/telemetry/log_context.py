"""Phase 4 — correlate log lines with the active chat trace.

A ``contextvars`` holds the current ``trace_id``; a ``LogRecordFactory`` stamps
it onto every ``LogRecord`` so any log line emitted while handling a turn can be
pivoted back to its trace (and vice-versa). Outside a request the value is ``-``.
"""

from __future__ import annotations

import contextvars
import logging
from typing import Any
from uuid import UUID, uuid4

# Client-known correlation headers. The client (e.g. the efficacy runner) mints a
# request id, sends it as ``X-Request-ID``, and the server echoes the adopted trace
# id as ``X-Trace-ID``. Because the client already knows the id, it can query the
# trace after a transport timeout — when it never received the response header.
REQUEST_ID_HEADER = "X-Request-ID"
TRACE_ID_HEADER = "X-Trace-ID"

_TRACE_ID: contextvars.ContextVar[str] = contextvars.ContextVar("ai_soc_trace_id", default="-")

_factory_installed = False


def coerce_request_id(raw: str | None) -> str:
    """Return a canonical UUID trace id from an untrusted client header value.

    Accept the client's ``X-Request-ID`` only when it is a syntactically valid
    UUID (prevents log/trace-id injection and unbounded values); otherwise mint a
    fresh server-side UUID so every turn still has a correlatable id.
    """
    if raw:
        try:
            candidate = UUID(raw.strip())
            # Accept only random UUIDv4 identifiers. This rejects nil, timestamp-
            # based, and other structurally valid but unsuitable caller values.
            if candidate.version == 4:
                return str(candidate)
        except (ValueError, AttributeError, TypeError):
            pass
    return str(uuid4())


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
