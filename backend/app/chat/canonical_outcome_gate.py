"""Shared canonical outcome invariant gate — runs after lane planning, before route resolution."""

from __future__ import annotations

from typing import Any

from app.chat.canonical_mode import build_typed_planning_failure_state
from app.chat.canonical_outcome_read import (
    OutcomeReadKind,
    read_canonical_planning_outcome,
    validate_cross_state_consistency,
)
from app.chat.contracts.canonical_planning_outcome import (
    FAILURE_STATUSES,
    CanonicalPlanningStatus,
)
from app.chat.response_validation import emit_request_failed, terminal_request_event_emitted

_REQUEST_FAILED_STATUSES: frozenset[str] = frozenset(
    {
        "planning_failed",
        "resolution_failed",
        "unsupported",
        "execution_failed",
    }
)


def _strip_executable_artifacts(state: dict[str, Any]) -> dict[str, Any]:
    next_state = dict(state)
    next_state.pop("evidence_plan", None)
    next_state.pop("execution", None)
    next_state.pop("mcp_evidence", None)
    return next_state


def _emit_request_failed_if_needed(
    state: dict[str, Any],
    *,
    reason: str,
    status: CanonicalPlanningStatus,
) -> dict[str, Any]:
    if status not in _REQUEST_FAILED_STATUSES:
        return state
    if terminal_request_event_emitted(state) is not None:
        return state
    category = "canonical_invariant"
    if status == "resolution_failed":
        category = "resolution"
    return emit_request_failed(state, reason=reason, error_category=category)


def _normalize_failure(
    state: dict[str, Any],
    *,
    reason: str,
    detail: str | None = None,
    category: str = "invariant",
    failure_status: CanonicalPlanningStatus = "planning_failed",
) -> dict[str, Any]:
    next_state = build_typed_planning_failure_state(
        state,
        failure_status=failure_status,
        reason=reason,
        detail=detail,
        category=category,
    )
    next_state = _strip_executable_artifacts(next_state)
    return _emit_request_failed_if_needed(next_state, reason=reason, status=failure_status)


def _apply_legacy_failure_mapping(state: dict[str, Any], legacy: dict[str, Any]) -> dict[str, Any]:
    outcome_name = str(legacy.get("outcome") or "").strip()
    reason = str(legacy.get("reason") or "canonical_legacy_failure")
    detail = legacy.get("detail")
    if outcome_name == "resolution_failed":
        return _normalize_failure(
            state,
            reason=reason,
            detail=str(detail) if detail is not None else None,
            category="resolution",
            failure_status="resolution_failed",
        )
    if outcome_name == "planning_failed":
        return _normalize_failure(
            state,
            reason=reason,
            detail=str(detail) if detail is not None else None,
            category="planning",
            failure_status="planning_failed",
        )
    return _normalize_failure(
        state,
        reason="invalid_legacy_failure_outcome",
        detail=f"legacy_outcome={outcome_name or 'missing'}",
        category="legacy_failure",
        failure_status="planning_failed",
    )


def enforce_canonical_outcome_invariant(state: dict[str, Any]) -> dict[str, Any]:
    """Ensure a valid typed outcome exists and state artifacts are consistent before dispatch."""
    read = read_canonical_planning_outcome(state)
    if read.kind == OutcomeReadKind.MALFORMED:
        return _normalize_failure(
            state,
            reason="malformed_canonical_outcome",
            detail=read.error,
            category="malformed_outcome",
        )

    if read.kind == OutcomeReadKind.ABSENT:
        legacy = state.get("canonical_planning_failure")
        if isinstance(legacy, dict) and legacy.get("outcome"):
            return _apply_legacy_failure_mapping(state, legacy)
        return _normalize_failure(
            state,
            reason="missing_canonical_outcome",
            category="missing_outcome",
        )

    assert read.outcome is not None
    outcome = read.outcome
    inconsistencies = validate_cross_state_consistency(state, outcome)
    if inconsistencies:
        return _normalize_failure(
            state,
            reason="contradictory_canonical_state",
            detail=";".join(inconsistencies),
            category="cross_state",
        )

    if outcome.status != "planned":
        next_state = _strip_executable_artifacts(state)
        if outcome.status == "persistence_failed":
            return next_state
        if outcome.status in FAILURE_STATUSES:
            return _emit_request_failed_if_needed(
                next_state,
                reason=outcome.failure.reason if outcome.failure else outcome.status,
                status=outcome.status,
            )
        return next_state

    return state
