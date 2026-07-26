"""Audit-critical vs diagnostic planning telemetry persistence (plan item 21b)."""

from __future__ import annotations

from typing import Any

import pytest

from app.chat import durable_planning_telemetry as telemetry
from app.chat.contracts.canonical_planning_outcome import outcome_from_state
from app.chat.planning_telemetry import emit_planning_event, planning_events, reset_planning_telemetry_for_tests
from app.chat.planning_telemetry_policy import (
    AUDIT_CRITICAL_PLANNING_EVENTS,
    DIAGNOSTIC_PLANNING_EVENTS,
    AuditCriticalTelemetryPersistenceError,
    is_audit_critical_planning_event,
    is_diagnostic_planning_event,
)
from app.chat.response_validation import emit_request_failed
from app.planner.executor import DispatchHooks, execute_plan_dispatch

@pytest.fixture(autouse=True)
def _reset() -> Any:
    telemetry.use_test_event_store(False)
    telemetry.clear_persisted_events_for_tests()
    reset_planning_telemetry_for_tests()
    yield
    telemetry.use_test_event_store(False)
    telemetry.clear_persisted_events_for_tests()
    reset_planning_telemetry_for_tests()


def test_event_catalog_partitions_all_twenty_eight_events() -> None:
    union = AUDIT_CRITICAL_PLANNING_EVENTS | DIAGNOSTIC_PLANNING_EVENTS
    assert len(union) == 28
    assert is_audit_critical_planning_event("execution.started")
    assert is_diagnostic_planning_event("lane_router.decided")
    assert not is_audit_critical_planning_event("planner_handoff.created")


def test_audit_critical_db_unavailable_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(telemetry, "canonical_db_disabled", lambda: False)

    def _boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("connection refused")

    monkeypatch.setattr(telemetry, "run_in_canonical_unit_of_work", _boom)

    with pytest.raises(AuditCriticalTelemetryPersistenceError):
        telemetry.persist_planning_event(
            {"event": "execution.started", "trace_id": "t-audit"},
            immediate=True,
        )


def test_diagnostic_db_unavailable_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(telemetry, "canonical_db_disabled", lambda: True)
    state: dict[str, Any] = {"trace_id": "t-diag"}
    result = emit_planning_event(
        state,
        event="lane_router.decided",
        node_name="lane_router",
        decision_reason="lane_router_decided",
        payload={"trace_id": "t-diag"},
    )
    assert result is not None
    assert planning_events()


def test_diagnostic_persist_failure_surfaces_degradation_without_blocking(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(telemetry, "canonical_db_disabled", lambda: False)

    def _boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("db write failed")

    monkeypatch.setattr(telemetry, "run_in_canonical_unit_of_work", _boom)

    state: dict[str, Any] = {"trace_id": "t-degrade"}
    result = emit_planning_event(
        state,
        event="lane_router.decided",
        node_name="lane_router",
        decision_reason="lane_router_decided",
        payload={"trace_id": "t-degrade"},
    )
    assert result is not None
    assert outcome_from_state(result) is None or outcome_from_state(result).status != "persistence_failed"
    degradation = result.get("planning_telemetry_degradation") or []
    assert degradation and degradation[-1]["event"] == "lane_router.decided"


def test_audit_critical_request_failed_does_not_recurse_on_persist_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(telemetry, "canonical_db_disabled", lambda: False)

    def _boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("connection refused")

    monkeypatch.setattr(telemetry, "run_in_canonical_unit_of_work", _boom)

    state: dict[str, Any] = {
        "trace_id": "t-recurse",
        "canonical_planning_failure": {
            "outcome": "persistence_failed",
            "reason": "execution.started",
            "detail": "connection refused",
        },
    }
    result = emit_request_failed(state, reason="audit_critical_persist_failed", error_category="database")
    assert result.get("canonical_request_terminal_event") == "request.failed"
    degradation = result.get("planning_telemetry_degradation") or []
    assert degradation


def test_audit_critical_failure_blocks_execution_before_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(telemetry, "canonical_db_disabled", lambda: False)

    def _boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("connection refused")

    monkeypatch.setattr(telemetry, "run_in_canonical_unit_of_work", _boom)

    state = {
        "trace_id": "t-exec",
        "handoff_id": "h-1",
        "handoff_version": 1,
        "evidence_plan": {
            "resource_plan": {
                "steps": [{"step_id": "s1", "resource_id": "rag", "purpose": "knowledge_retrieval", "status": "planned"}],
                "provenance": {
                    "committed": True,
                    "resource_plan_id": "rp:test",
                    "handoff_id": "h-1",
                    "handoff_version": 1,
                },
            }
        },
    }

    hooks = DispatchHooks(
        uses_rag_only_path=lambda _s: False,
        uses_pre_mcp_rag=lambda _s: False,
        prepare_rag_only=lambda _s: _s,
        rag_early=lambda _s: _s,
        spl_source_resolve=lambda _s: _s,
        workflow_spl=lambda _s: _s,
        spl_postprocessor=lambda _s: _s,
        ensure_workflow_plan=lambda _s: _s,
        reference_finalize=lambda _s: _s,
        execution=lambda _s: _s,
    )

    result = execute_plan_dispatch(state, hooks=hooks)

    failure = result.get("canonical_planning_failure") or {}
    assert failure.get("outcome") == "persistence_failed"
    assert result.get("plan_dispatch_trace", {}).get("dispatch_source") != "plan_dispatch"


def test_diagnostic_skip_is_logged_not_silent(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "telemetry_mode", "db")
    monkeypatch.setattr(settings, "ai_soc_telemetry_sink", "none")
    monkeypatch.setattr(telemetry, "canonical_db_disabled", lambda: False)

    with caplog.at_level("INFO"):
        telemetry.persist_planning_event({"event": "response.validated", "trace_id": "t-skip"}, immediate=True)

    assert any("diagnostic_planning_event_skipped" in record.message for record in caplog.records)
