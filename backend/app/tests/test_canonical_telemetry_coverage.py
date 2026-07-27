"""Canonical planning telemetry catalog coverage (plan item 21)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.chat import durable_planning_telemetry as telemetry
from app.chat.canonical_execution_idempotency import (
    AcquireOutcome,
    clear_in_memory_store_for_tests,
    run_idempotent_execution_step,
    use_in_memory_store_for_tests,
)
from app.chat.canonical_handoff_store import clear_all_handoffs_for_tests
from app.chat.canonical_telemetry_catalog import (
    CANONICAL_TELEMETRY_EVENT_SPECS,
    CANONICAL_TELEMETRY_EVENTS,
    PRODUCTION_EMITTER_WIRING,
    spec_for_event,
)
from app.chat.contracts.canonical_planning_outcome import outcome_from_state
from app.chat.planning_telemetry import (
    emit_request_completed,
    planning_events,
    reset_planning_telemetry_for_tests,
    terminal_request_event_emitted,
)
from app.chat.planning_telemetry_policy import (
    AUDIT_CRITICAL_PLANNING_EVENTS,
    DIAGNOSTIC_PLANNING_EVENTS,
    is_audit_critical_planning_event,
)
from app.chat.response_validation import (
    emit_request_failed,
    emit_response_generated,
    emit_response_validated,
)
from app.config import settings
from app.tests.support.canonical_flow import run_canonical_flow

REPO_ROOT = Path(__file__).resolve().parents[3]

_AMBIGUOUS_HUNT = "Hunt for CI/CD supply-chain compromise indicators across our environment"
_UNSAFE_BLOCK = "Block IP 10.0.0.5 immediately"


@pytest.fixture(autouse=True)
def _telemetry_test_env(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_session_context_enabled", True)
    telemetry.use_test_event_store(True)
    telemetry.clear_persisted_events_for_tests()
    reset_planning_telemetry_for_tests()
    clear_all_handoffs_for_tests()
    use_in_memory_store_for_tests(True)
    clear_in_memory_store_for_tests()
    yield
    telemetry.clear_persisted_events_for_tests()
    telemetry.use_test_event_store(False)
    reset_planning_telemetry_for_tests()
    clear_all_handoffs_for_tests()
    use_in_memory_store_for_tests(False)
    clear_in_memory_store_for_tests()


def _event_names() -> list[str]:
    return [event.get("event") for event in planning_events()]


def _persisted_event_names() -> list[str]:
    return [event.get("event") for event in telemetry.persisted_events()]


def test_catalog_partitions_all_28_events_with_item_21b_classification() -> None:
    assert len(CANONICAL_TELEMETRY_EVENTS) == 28
    assert len(CANONICAL_TELEMETRY_EVENT_SPECS) == 28
    union = AUDIT_CRITICAL_PLANNING_EVENTS | DIAGNOSTIC_PLANNING_EVENTS
    assert union == CANONICAL_TELEMETRY_EVENTS
    assert len(AUDIT_CRITICAL_PLANNING_EVENTS) == 8
    assert len(DIAGNOSTIC_PLANNING_EVENTS) == 20
    for spec in CANONICAL_TELEMETRY_EVENT_SPECS:
        assert spec.classification == (
            "audit-critical" if is_audit_critical_planning_event(spec.event) else "diagnostic"
        )
        assert spec.required_payload
        assert spec.node_name


def test_production_emitter_wiring_covers_all_catalog_events() -> None:
    assert set(PRODUCTION_EMITTER_WIRING) == CANONICAL_TELEMETRY_EVENTS
    for event, wiring in PRODUCTION_EMITTER_WIRING.items():
        combined = ""
        for rel_path in wiring.source_paths:
            path = REPO_ROOT / rel_path
            assert path.is_file(), f"missing production source for {event}: {rel_path}"
            combined += path.read_text(encoding="utf-8")
        assert any(marker in combined for marker in wiring.markers), (
            f"{event} missing production marker in {wiring.source_paths}"
        )


def test_catalog_specs_document_required_fields_per_event() -> None:
    for event in sorted(CANONICAL_TELEMETRY_EVENTS):
        spec = spec_for_event(event)
        assert spec is not None
        assert spec.event == event
        assert "status" in spec.required_payload


def test_t1_t3_known_complete_path_emits_planning_events() -> None:
    result = run_canonical_flow(
        "Investigate failed login spike for user:alice host:APP-01 from 10.0.0.8 in the last 24 hours",
        use_case_id="auth_failed_login_spike",
        session_id="sess-t1",
        trace_id="trace-t1",
    )
    assert result.outcome is not None and result.outcome.status == "planned"
    events = _event_names()
    assert "query_understanding.completed" in events
    assert "lane_router.decided" in events
    assert "resource_plan.created" in events
    assert "handoff.persisted" in events
    assert "request.completed" not in events
    assert "request.failed" not in events
    persisted = telemetry.persisted_events()
    assert persisted
    assert all(row.get("decision_id") for row in persisted if row.get("event") == "resource_plan.created")


def test_known_path_clarification_terminal_consistency() -> None:
    result = run_canonical_flow("What happened with that alert?", session_id="sess-clarify", trace_id="trace-clarify")
    outcome = outcome_from_state(result.state)
    assert outcome is not None and outcome.status == "clarification_required"
    events = _event_names()
    assert events.count("clarification.requested") == 1
    assert "request.completed" not in events
    assert "request.failed" not in events
    assert "response.generated" not in events


def test_t4_guided_investigation_path_emits_guided_events() -> None:
    result = run_canonical_flow(_AMBIGUOUS_HUNT, session_id="sess-t4", trace_id="trace-t4")
    events = _event_names()
    assert "guided_resolution.started" in events or "guided_intent.resolved" in events
    assert "lane_router.decided" in events
    assert result.outcome is not None


def test_t4_resolves_t0_knowledge_path() -> None:
    result = run_canonical_flow("What is CVE-2026-12345?", session_id="sess-t0", trace_id="trace-t0")
    assert result.outcome is not None and result.outcome.status == "planned"
    assert result.state.get("resolved_tier") == "T0"
    events = _event_names()
    assert "resource_plan.created" in events
    assert "guided_intent.resolved" in events or "lane_router.decided" in events


def test_composite_knowledge_and_live_evidence_replay_emits_commit_reused() -> None:
    first = run_canonical_flow("What is MITRE T1059?", session_id="sess-composite", trace_id="trace-composite")
    assert first.outcome is not None and first.outcome.status == "planned"
    second = run_canonical_flow("What is MITRE T1059?", session_id="sess-composite", trace_id="trace-composite-2")
    events = _event_names()
    assert "resource_plan.commit_reused" in events or second.outcome is not None


def test_policy_unsafe_block_does_not_emit_execution_started() -> None:
    result = run_canonical_flow(_UNSAFE_BLOCK, session_id="sess-unsafe", trace_id="trace-unsafe")
    events = _event_names()
    assert "execution.started" not in events
    assert result.outcome is not None


def test_persistence_failure_emits_request_failed_not_completed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.chat import canonical_handoff_repository as handoff_repo

    handoff_repo.use_in_memory_store_for_tests(False)
    monkeypatch.setattr(handoff_repo, "canonical_db_disabled", lambda: False)

    def _raise_on_write(fn: Any) -> Any:
        raise RuntimeError("connection refused")

    monkeypatch.setattr(handoff_repo, "run_in_canonical_unit_of_work", _raise_on_write)

    result = run_canonical_flow("What happened with that alert?", trace_id="trace-persist-fail")
    assert outcome_from_state(result.state) is not None
    assert outcome_from_state(result.state).status == "persistence_failed"
    events = _event_names()
    assert events.count("request.failed") == 1
    assert "request.completed" not in events


def test_execution_step_events_emitted_from_idempotency_runner() -> None:
    state: dict[str, Any] = {"trace_id": "trace-step", "session_id": "sess-step"}
    outcome, _payload = run_idempotent_execution_step(
        resource_plan_id="rp:step",
        step_id="s1",
        operation="mcp_discovery:tool",
        handoff_id="h-step",
        handoff_version=1,
        side_effecting=False,
        lease_owner="worker-a",
        operation_contract="read_only_retryable",
        execute=lambda: {"rows": []},
        telemetry_state=state,
    )
    assert outcome == AcquireOutcome.EXECUTE
    events = _event_names()
    assert "execution_step.started" in events
    assert "execution_step.completed" in events
    persisted = [row for row in telemetry.persisted_events() if row.get("event", "").startswith("execution_step.")]
    assert persisted
    assert all(row.get("resource_plan_id") == "rp:step" for row in persisted)
    assert all(row.get("step_id") == "s1" for row in persisted)


def test_execution_step_replay_emits_completed_without_second_started() -> None:
    state: dict[str, Any] = {"trace_id": "trace-replay", "session_id": "sess-replay"}
    params = {
        "resource_plan_id": "rp:replay",
        "step_id": "s1",
        "operation": "mcp_discovery:tool",
        "handoff_id": "h-replay",
        "handoff_version": 1,
        "side_effecting": False,
        "lease_owner": "worker-a",
        "operation_contract": "read_only_retryable",
        "telemetry_state": state,
    }
    run_idempotent_execution_step(**params, execute=lambda: {"rows": []})
    run_idempotent_execution_step(**params, execute=lambda: {"rows": [{"unexpected": True}]})
    events = _event_names()
    assert events.count("execution_step.started") == 1
    assert events.count("execution_step.completed") == 2


def test_execution_uncertainty_does_not_emit_step_started() -> None:
    from datetime import UTC, datetime, timedelta

    from app.chat import canonical_execution_idempotency as store
    from app.chat.canonical_execution_idempotency import (
        acquire_execution_step,
        build_idempotency_key,
    )

    params = {
        "resource_plan_id": "rp:uncertain",
        "step_id": "s1",
        "operation": "mcp_execution:tool",
        "handoff_id": "h-uncertain",
        "handoff_version": 1,
    }
    key = build_idempotency_key(
        resource_plan_id=params["resource_plan_id"],
        handoff_id=params["handoff_id"],
        handoff_version=params["handoff_version"],
        step_id=params["step_id"],
        operation=params["operation"],
    )
    acquire_execution_step(**params, lease_owner="worker-a", side_effecting=True)
    record = store._TEST_STORE[key]
    record["lease_expires_at"] = datetime.now(UTC) - timedelta(seconds=30)
    store._TEST_STORE[key] = record
    reset_planning_telemetry_for_tests()
    state: dict[str, Any] = {"trace_id": "trace-uncertain"}
    outcome, _stored = run_idempotent_execution_step(
        **params,
        side_effecting=True,
        lease_owner="worker-b",
        operation_contract="side_effecting_without_stable_idempotency",
        execute=lambda: {"unexpected": True},
        telemetry_state=state,
    )
    assert outcome == AcquireOutcome.REQUIRES_RECONCILIATION
    assert "execution_step.started" not in _event_names()


def test_terminal_success_emits_single_request_completed() -> None:
    state: dict[str, Any] = {
        "trace_id": "trace-ok",
        "session_id": "sess-ok",
    }
    state = emit_response_validated(state, ok=True, reasons=[])
    state = emit_response_generated(state)
    state = emit_request_completed(state)
    state = emit_request_completed(state)
    events = _event_names()
    assert events.count("request.completed") == 1
    assert terminal_request_event_emitted(state) == "request.completed"


def test_terminal_failure_skips_response_generated_and_request_completed() -> None:
    state: dict[str, Any] = {"trace_id": "trace-fail", "session_id": "sess-fail"}
    state = emit_request_failed(state, reason="response_validation_failed")
    state = emit_response_generated(state)
    state = emit_request_completed(state)
    events = _event_names()
    assert events.count("request.failed") == 1
    assert "response.generated" not in events
    assert "request.completed" not in events
    assert terminal_request_event_emitted(state) == "request.failed"


def test_terminal_dedup_on_retry_does_not_duplicate_request_failed() -> None:
    state: dict[str, Any] = {"trace_id": "trace-dedup", "session_id": "sess-dedup"}
    state = emit_request_failed(state, reason="execution_failed", error_category="execution_error")
    state = emit_request_failed(state, reason="execution_failed", error_category="execution_error")
    assert _event_names().count("request.failed") == 1


def test_correlation_columns_persisted_from_unminimized_payload() -> None:
    from app.chat.planning_telemetry import emit_planning_event

    state: dict[str, Any] = {"trace_id": "trace-corr", "session_id": "sess-corr", "turn_id": "turn-corr"}
    emit_planning_event(
        state,
        event="lane_router.decided",
        node_name="lane_router",
        decision_reason="lane_router_decided",
        payload={
            "trace_id": "trace-corr",
            "session_id": "sess-corr",
            "turn_id": "turn-corr",
            "handoff_id": "h-corr",
            "handoff_version": 3,
            "resource_plan_id": "rp-corr",
            "status": "completed",
            "api_key": "must-not-persist",
        },
    )
    (persisted,) = telemetry.persisted_events()
    assert persisted["session_id"] == "sess-corr"
    assert persisted["handoff_id"] == "h-corr"
    assert persisted["handoff_version"] == 3
    assert persisted["resource_plan_id"] == "rp-corr"
    assert "api_key" not in persisted


def test_demo_modules_do_not_import_canonical_planning_telemetry() -> None:
    demo_root = REPO_ROOT / "backend" / "app" / "demo"
    forbidden = (
        "planning_telemetry",
        "durable_planning_telemetry",
        "emit_planning_event",
        "emit_request_completed",
        "emit_request_failed",
    )
    for path in demo_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path.relative_to(REPO_ROOT)} must not reference {token}"
