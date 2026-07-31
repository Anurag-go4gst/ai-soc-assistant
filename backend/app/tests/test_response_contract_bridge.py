"""Tests for additive response contract bridge (G1 planning_outcome + G2 execution uncertainty)."""

from __future__ import annotations

import pytest

from app.chat.contracts.canonical_planning_outcome import (
    clarification_outcome,
    failure_outcome,
    policy_blocked_outcome,
)
from app.chat.response_contract_bridge import (
    build_planning_outcome_summary,
    enrich_placeholder_response,
    normalize_execution_envelope,
    sanitize_reconciliation_reason,
)
from app.schemas.responses import PlaceholderResponse, PlanningOutcomeSummary


def _clarification_state() -> dict:
    outcome = clarification_outcome(
        canonical_input={"query": "test"},
        question="Which alert should I investigate?",
        unresolved_fields=["alert_id"],
        handoff_id="handoff-1",
        handoff_version=1,
        reason="clarification_required",
    )
    return {"canonical_planning_outcome": outcome.model_dump()}


@pytest.mark.parametrize(
    ("status", "category", "builder"),
    [
        (
            "clarification_required",
            "clarification",
            lambda: _clarification_state(),
        ),
        (
            "policy_blocked",
            "policy",
            lambda: {
                "canonical_planning_outcome": policy_blocked_outcome(
                    canonical_input={"query": "block ip"},
                    policy_reason="unsafe_execution_request",
                ).model_dump(),
            },
        ),
        (
            "planning_failed",
            "planner",
            lambda: {
                "canonical_planning_outcome": failure_outcome(
                    "planning_failed",
                    category="planner",
                    reason="no_plan_produced",
                ).model_dump(),
            },
        ),
        (
            "persistence_failed",
            "database",
            lambda: {
                "canonical_planning_outcome": failure_outcome(
                    "persistence_failed",
                    category="database",
                    reason="handoff_write_failed",
                    detail="asyncpg connection refused host=internal",
                ).model_dump(),
            },
        ),
        (
            "resolution_failed",
            "resolution",
            lambda: {
                "canonical_planning_outcome": failure_outcome(
                    "resolution_failed",
                    category="resolution",
                    reason="gap_unresolved",
                ).model_dump(),
            },
        ),
    ],
)
def test_planning_outcome_summary_terminal_states(status: str, category: str, builder) -> None:
    state = builder()
    summary = build_planning_outcome_summary(state)
    assert summary is not None
    assert summary.status == status
    assert summary.category == category
    assert summary.user_message
    assert summary.recovery_hint
    assert "asyncpg" not in summary.user_message.lower()
    assert "connection refused" not in summary.recovery_hint.lower()


def test_planned_outcome_omits_summary() -> None:
    summary = build_planning_outcome_summary({"plan_dispatch_trace": {"canonical_status": "planned"}})
    assert summary is None


def test_normalize_execution_uncertainty_fields() -> None:
    envelope = normalize_execution_envelope(
        {
            "status": "requires_human_review",
            "execution_intent": "spl_search",
            "tool_selection_status": "blocked_by_idempotency",
            "tool_selection_reason": "execution_outcome_uncertain",
            "result_count": 0,
            "results_preview": [],
            "duration_ms": 0,
            "outcome_uncertain": True,
            "block_reason": "execution_outcome_uncertain",
            "internal_trace": "must not serialize",
        }
    )
    assert envelope is not None
    assert envelope.outcome_uncertain is True
    assert envelope.reconciliation_reason == "execution_outcome_uncertain"
    dumped = envelope.model_dump()
    assert "internal_trace" not in dumped


def test_sanitize_reconciliation_reason_rejects_arbitrary_text() -> None:
    reason = sanitize_reconciliation_reason(
        "postgresql://user:pass@db/internal error detail",
        outcome_uncertain=True,
    )
    assert reason == "execution_outcome_uncertain"


def test_enrich_placeholder_response_attaches_fields() -> None:
    base = PlaceholderResponse(
        trace_id="t-1",
        message="blocked",
        note="n",
        execution={
            "status": "requires_human_review",
            "execution_intent": "spl_search",
            "tool_selection_status": "blocked",
            "tool_selection_reason": "execution_outcome_uncertain",
            "result_count": 0,
            "results_preview": [],
            "duration_ms": 0,
            "outcome_uncertain": True,
            "block_reason": "execution_outcome_uncertain",
        },
    )
    state = {
        "canonical_planning_outcome": failure_outcome(
            "persistence_failed",
            category="database",
            reason="handoff_write_failed",
        ).model_dump(),
    }
    enriched = enrich_placeholder_response(base, state)
    assert enriched.planning_outcome is not None
    assert enriched.planning_outcome.status == "persistence_failed"
    assert enriched.execution is not None
    assert enriched.execution.outcome_uncertain is True
    assert enriched.execution.reconciliation_reason == "execution_outcome_uncertain"
    payload = enriched.model_dump()
    assert "evidence_plan" not in payload.get("planning_outcome", {})
    assert "resource_plan" not in payload


def test_planner_executor_reconciliation_shape_serializes() -> None:
    """Mirror test_planner_executor uncertain side-effect envelope."""
    execution = {
        "status": "requires_human_review",
        "execution_intent": "spl_search",
        "block_reason": "execution_outcome_uncertain",
        "outcome_uncertain": True,
        "tool_selection_status": "blocked_by_idempotency",
        "tool_selection_reason": "execution_outcome_uncertain",
        "selected_mcp_server": None,
        "selected_mcp_tool": None,
        "executed_spl": None,
        "result_count": 0,
        "results_preview": [],
        "duration_ms": 0,
        "evidence_source": "unavailable",
        "execution_status_label": "not_executed",
    }
    envelope = normalize_execution_envelope(execution)
    assert envelope is not None
    assert envelope.outcome_uncertain
    assert envelope.reconciliation_reason == "execution_outcome_uncertain"
