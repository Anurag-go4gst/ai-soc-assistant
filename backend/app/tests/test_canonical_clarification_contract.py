"""Gate 1 — clarification produces a typed outcome, never a partial EvidencePlan."""

from __future__ import annotations

from typing import Any

import pytest

from app.chat.canonical_mode import build_canonical_failure_state, build_non_planned_dispatch_state
from app.chat.canonical_planning_orchestrator import build_clarification_question
from app.chat.contracts.canonical_planning_outcome import outcome_from_state
from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.response_validation import validate_final_response


def _clarification_state() -> dict[str, Any]:
    from app.chat.contracts.canonical_planning_outcome import clarification_outcome

    outcome = clarification_outcome(
        canonical_input={"routing": {"processing_lane": "known"}},
        question=build_clarification_question(["host"]),
        unresolved_fields=["host"],
        handoff_id="h-1",
        handoff_version=1,
        reason="known_clarification",
    )
    return {"canonical_planning_outcome": outcome.model_dump()}


def test_clarification_question_is_deterministic_and_non_empty() -> None:
    assert build_clarification_question(["host"]) == "Which host should I scope this investigation to?"
    assert build_clarification_question(["unmapped_field"]).startswith("I need more detail")
    assert build_clarification_question([])


def test_clarification_state_carries_no_evidence_plan() -> None:
    state = _clarification_state()
    assert "evidence_plan" not in state
    outcome = outcome_from_state(state)
    assert outcome is not None
    assert outcome.evidence_plan is None
    assert outcome.resource_plan is None


def test_clarification_passes_response_validation_without_resource_plan() -> None:
    status, reasons = validate_final_response(_clarification_state())
    assert (status, reasons) == ("ok", [])


def test_response_validation_rejects_clarification_carrying_evidence_plan() -> None:
    state = _clarification_state()
    state["evidence_plan"] = {"answer_mode": "clarification"}
    status, reasons = validate_final_response(state)
    assert status == "failed"
    assert "clarification_must_not_carry_evidence_plan" in reasons


def test_canonical_failure_state_does_not_synthesise_evidence_plan() -> None:
    """A dict of only reasons+canonical_failure fails EvidencePlan validation."""
    state = build_canonical_failure_state(
        {"trace_id": "t-1"},
        outcome="planning_failed",
        reason="canonical_missing_resource_plan_at_dispatch",
    )
    assert "evidence_plan" not in state
    assert state["canonical_planning_failure"]["reason"] == "canonical_missing_resource_plan_at_dispatch"


def test_canonical_failure_state_annotates_an_existing_valid_plan() -> None:
    valid = EvidencePlan(
        answer_mode="rag_only",
        rag_phase="rag_only",
        needs_rag=True,
        needs_spl=False,
        needs_mcp=False,
        needs_mitre=False,
        spl_allowed=False,
        mcp_allowed=False,
        policy_context_required=False,
        policy_context_recommended=False,
    ).model_dump()

    state = build_canonical_failure_state(
        {"evidence_plan": valid},
        outcome="policy_blocked",
        reason="unsafe_execution_request",
    )

    assert state["evidence_plan"]["canonical_failure"]["outcome"] == "policy_blocked"
    EvidencePlan.model_validate(state["evidence_plan"])  # still a valid plan


def test_non_planned_dispatch_is_not_labelled_a_planning_failure() -> None:
    state = build_non_planned_dispatch_state({"trace_id": "t-1"}, status="clarification_required")
    trace = state["plan_dispatch_trace"]
    assert trace["dispatch_source"] == "canonical_non_planned"
    assert trace["canonical_status"] == "clarification_required"
    assert "canonical_planning_failure" not in state


def _run_canonical(message: str, **extra: Any) -> dict[str, Any]:
    from app.tests.support.canonical_flow import run_canonical_flow

    return run_canonical_flow(message, **extra).state


@pytest.fixture()
def _memory_handoffs() -> Any:
    from app.chat import canonical_handoff_repository as repo

    repo.use_in_memory_store_for_tests(True)
    yield
    repo.clear_in_memory_store_for_tests()
    repo.use_in_memory_store_for_tests(False)


def test_live_clarification_turn_creates_no_resource_plan(_memory_handoffs: Any) -> None:
    from app.chat.canonical_handoff_store import get_committed_resource_plan, get_handoff

    state = _run_canonical("What happened with that alert?")
    outcome = outcome_from_state(state)
    assert outcome is not None and outcome.status == "clarification_required"

    assert "evidence_plan" not in state
    assert outcome.resource_plan is None

    clarification = outcome.clarification
    assert clarification is not None
    assert clarification.question
    assert clarification.unresolved_fields

    assert get_committed_resource_plan(clarification.handoff_id, clarification.handoff_version) is None
    record = get_handoff(clarification.handoff_id, clarification.handoff_version)
    assert record is not None
    assert record.normalized_status() == "awaiting_clarification"


def test_clarification_answer_resumes_and_plans(_memory_handoffs: Any) -> None:
    """The resume comparison used the raw status, so an answer never resumed."""
    from app.chat.canonical_handoff_store import get_handoff

    session_id = "sess-clarify-contract"
    first = _run_canonical("What happened with that alert?", session_id=session_id)
    clarification = outcome_from_state(first).clarification  # type: ignore[union-attr]
    assert clarification is not None

    resumed = _run_canonical(
        "ALT-2024-0891",
        session_id=session_id,
        handoff_resume={
            "handoff_id": clarification.handoff_id,
            "handoff_version": clarification.handoff_version,
            "user_answer": "ALT-2024-0891",
        },
    )

    outcome = outcome_from_state(resumed)
    assert outcome is not None and outcome.status == "planned"
    assert outcome.resource_plan is not None

    next_version = get_handoff(clarification.handoff_id, clarification.handoff_version + 1)
    assert next_version is not None
    assert next_version.normalized_status() == "plan_committed"


@pytest.mark.parametrize("status", ["planning_failed", "policy_blocked", "unsupported"])
def test_non_planned_outcomes_never_require_a_resource_plan(status: str) -> None:
    from app.chat.contracts.canonical_planning_outcome import (
        failure_outcome,
        policy_blocked_outcome,
    )

    outcome = (
        policy_blocked_outcome(canonical_input=None, policy_reason="blocked")
        if status == "policy_blocked"
        else failure_outcome(status, category="planner", reason="no_plan")  # type: ignore[arg-type]
    )
    result, reasons = validate_final_response({"canonical_planning_outcome": outcome.model_dump()})
    assert result == "ok"
    assert reasons == []
