"""Phase 4 — log lines carry the active chat trace_id."""

from __future__ import annotations

import logging

from app.connectors.telemetry.log_context import (
    current_trace_id,
    install_trace_id_log_factory,
    reset_trace_id,
    set_trace_id,
)

install_trace_id_log_factory()


def test_record_carries_active_trace_id() -> None:
    token = set_trace_id("trace-abc")
    try:
        record = logging.getLogger("ai_soc.telemetry").makeRecord(
            "ai_soc.telemetry", logging.INFO, __file__, 1, "msg", None, None
        )
        assert record.trace_id == "trace-abc"
        assert current_trace_id() == "trace-abc"
    finally:
        reset_trace_id(token)


def test_record_outside_request_is_dash() -> None:
    reset_trace_id()
    record = logging.getLogger("ai_soc").makeRecord(
        "ai_soc", logging.INFO, __file__, 1, "msg", None, None
    )
    assert record.trace_id == "-"


def test_factory_install_is_idempotent() -> None:
    install_trace_id_log_factory()
    install_trace_id_log_factory()
    record = logging.getLogger("x").makeRecord("x", logging.INFO, __file__, 1, "m", None, None)
    assert hasattr(record, "trace_id")
