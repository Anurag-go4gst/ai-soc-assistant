"""Tests for pure typed failure builder and invariant gate."""

from __future__ import annotations

from app.chat.canonical_mode import build_typed_planning_failure_state
from app.chat.canonical_outcome_gate import enforce_canonical_outcome_invariant
from app.chat.canonical_outcome_read import OutcomeReadKind, read_canonical_planning_outcome
from app.chat.contracts.canonical_planning_outcome import clarification_outcome, outcome_from_state
from app.chat.planning_telemetry import planning_events, reset_planning_telemetry_for_tests
from app.chat.response_validation import terminal_request_event_emitted, validate_final_response


def test_build_typed_planning_failure_state_is_pure() -> None:
    state = build_typed_planning_failure_state(
        {},
        failure_status="planning_failed",
        reason="missing_canonical_outcome",
        category="missing_outcome",
    )
    assert state["canonical_planning_outcome"]["status"] == "planning_failed"
    assert state["canonical_planning_failure"]["outcome"] == "planning_failed"
    assert terminal_request_event_emitted(state) is None


def test_gate_normalizes_missing_outcome_and_strips_ep() -> None:
    reset_planning_telemetry_for_tests()
    state = enforce_canonical_outcome_invariant(
        {
            "evidence_plan": {"answer_mode": "workflow_spl", "resource_plan": {"steps": []}},
            "trace_id": "gate-test",
            "session_id": "sess",
        }
    )
    read = read_canonical_planning_outcome(state)
    assert read.kind == OutcomeReadKind.VALID
    assert read.outcome is not None
    assert read.outcome.status == "planning_failed"
    assert "evidence_plan" not in state
    read = read_canonical_planning_outcome(state)
    assert read.outcome is not None
    assert read.outcome.status == "planning_failed"


def test_gate_maps_legacy_resolution_failed() -> None:
    reset_planning_telemetry_for_tests()
    state = enforce_canonical_outcome_invariant(
        {
            "canonical_planning_failure": {
                "outcome": "resolution_failed",
                "reason": "detail_tool_unavailable",
                "detail": "tool down",
            },
            "trace_id": "gate-res",
            "session_id": "sess",
        }
    )
    read = read_canonical_planning_outcome(state)
    assert read.outcome is not None
    assert read.outcome.status == "resolution_failed"
    assert terminal_request_event_emitted(state) == "request.failed"


def test_gate_rejects_contradictory_clarification_with_ep() -> None:
    outcome = clarification_outcome(
        canonical_input={"routing": {}},
        question="Which host?",
        unresolved_fields=["host"],
        handoff_id="h-1",
        handoff_version=1,
    )
    state = enforce_canonical_outcome_invariant(
        {
            "canonical_planning_outcome": outcome.model_dump(),
            "evidence_plan": {"answer_mode": "clarification"},
            "trace_id": "gate-contra",
            "session_id": "sess",
        }
    )
    read = read_canonical_planning_outcome(state)
    assert read.outcome is not None
    assert read.outcome.status == "planning_failed"
    assert "evidence_plan" not in state


def test_gate_preserves_valid_clarification() -> None:
    outcome = clarification_outcome(
        canonical_input={"routing": {}},
        question="Which host?",
        unresolved_fields=["host"],
        handoff_id="h-1",
        handoff_version=1,
    )
    state = enforce_canonical_outcome_invariant(
        {
            "canonical_planning_outcome": outcome.model_dump(),
            "trace_id": "gate-ok",
            "session_id": "sess",
        }
    )
    restored = outcome_from_state(state)
    assert restored is not None
    assert restored.status == "clarification_required"
    status, reasons = validate_final_response(state)
    assert (status, reasons) == ("ok", [])
