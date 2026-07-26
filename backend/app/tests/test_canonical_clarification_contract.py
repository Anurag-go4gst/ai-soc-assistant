"""Gate 1 — clarification produces a typed outcome, never a partial EvidencePlan."""

from __future__ import annotations

from typing import Any

import pytest

from app.chat.canonical_mode import build_canonical_failure_state, build_non_planned_dispatch_state
from app.chat.canonical_planning_orchestrator import build_clarification_question
from app.chat.contracts.canonical_planning_outcome import outcome_from_state
from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.response_validation import validate_final_response
from app.schemas.requests import ChatRequest


@pytest.fixture(autouse=True)
def _canonical_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "ai_soc_session_context_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_live_chat_ec_parity_enabled", False)
    monkeypatch.setattr(settings, "telemetry_mode", "none")
    monkeypatch.setattr(settings, "ai_soc_telemetry_sink", "none")


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


def test_clarification_resume_populates_query_to_intent(_memory_handoffs: Any) -> None:
    session_id = "sess-clarify-q2i"
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
    q2i = resumed.get("query_to_intent")
    assert isinstance(q2i, dict)
    assert isinstance(q2i.get("query_signals"), dict)
    assert q2i.get("handoff_resume") is True
    intent = q2i.get("intent_classification")
    assert isinstance(intent, dict)
    assert intent.get("primary_intent")
    provenance = q2i.get("resume_provenance")
    assert isinstance(provenance, dict)
    assert provenance.get("original_skill")


def test_live_chat_two_turn_clarification_via_session_pins(_memory_handoffs: Any) -> None:
    from app.chat.canonical_handoff_store import get_committed_resource_plan, get_handoff
    from app.chat.pipeline import build_live_chat_response
    from app.chat.session_store import clear_all_session_pins_for_tests, get_session_pins

    clear_all_session_pins_for_tests()
    session_id = "sess-live-clarify"
    first = build_live_chat_response(
        ChatRequest(message="What happened with that alert?", session_id=session_id)
    )
    assert first.evidence_plan is None

    pins = get_session_pins(session_id)
    assert pins is not None
    assert pins.pending_handoff_id
    assert pins.pending_handoff_version == 1

    handoff_id = pins.pending_handoff_id
    assert handoff_id is not None
    assert get_committed_resource_plan(handoff_id, 1) is None
    prior = get_handoff(handoff_id, 1)
    assert prior is not None and prior.normalized_status() == "awaiting_clarification"

    second = build_live_chat_response(
        ChatRequest(message="ALT-2024-0891", session_id=session_id)
    )
    assert second.evidence_plan is not None
    resource_plan = second.evidence_plan.get("resource_plan") if second.evidence_plan else None
    assert isinstance(resource_plan, dict)
    assert (resource_plan.get("provenance") or {}).get("committed") is True

    next_version = get_handoff(handoff_id, 2)
    assert next_version is not None
    assert next_version.normalized_status() == "plan_committed"


def test_malformed_handoff_routing_returns_typed_failure(_memory_handoffs: Any) -> None:
    from app.chat.canonical_handoff_store import save_clarification_handoff

    handoff_id = "cpi:malformed-routing"
    save_clarification_handoff(
        handoff_id=handoff_id,
        handoff_version=1,
        canonical_planning_input={
            "routing": {},
            "detail_state": {"field_values": {}, "missing_fields": ["alert_id"]},
        },
        gap_resolution=None,
        unresolved_fields=["alert_id"],
        clarification_reason="missing_alert_id",
        trace_id="trace-malformed",
        session_id="sess-malformed",
        original_query="What happened with that alert?",
        original_skill=None,
        original_use_case_id=None,
        original_answer_goal=None,
        initial_tier="T4",
        resolved_tier="T4",
    )
    state = _run_canonical(
        "ALT-2024-0891",
        session_id="sess-malformed",
        handoff_resume={
            "handoff_id": handoff_id,
            "handoff_version": 1,
            "user_answer": "ALT-2024-0891",
        },
    )
    failure = state.get("canonical_planning_failure")
    assert isinstance(failure, dict)
    assert failure.get("outcome") in {"resolution_failed", "planning_failed"}


def test_duplicate_clarification_answer_reuses_next_version(_memory_handoffs: Any) -> None:
    from app.chat.canonical_handoff_store import get_handoff

    session_id = "sess-dup-live"
    first = _run_canonical("What happened with that alert?", session_id=session_id)
    clarification = outcome_from_state(first).clarification  # type: ignore[union-attr]
    assert clarification is not None

    resume_args = {
        "handoff_id": clarification.handoff_id,
        "handoff_version": clarification.handoff_version,
        "user_answer": "ALT-2024-0891",
    }
    first_resume = _run_canonical("ALT-2024-0891", session_id=session_id, handoff_resume=resume_args)
    second_resume = _run_canonical("ALT-2024-0891", session_id=session_id, handoff_resume=resume_args)
    assert outcome_from_state(first_resume).status == "planned"
    assert outcome_from_state(second_resume).status == "planned"
    v2 = get_handoff(clarification.handoff_id, clarification.handoff_version + 1)
    assert v2 is not None
    assert get_handoff(clarification.handoff_id, clarification.handoff_version + 2) is None


def test_imperative_and_resource_planner_clarification_resume_parity(
    _memory_handoffs: Any,
) -> None:
    from app.chat.canonical_handoff_store import get_handoff
    from app.chat.pipeline import build_live_chat_response
    from app.graph.resource_planner_graph import run_chat_via_resource_planner_graph
    from app.chat.session_store import clear_all_session_pins_for_tests

    clear_all_session_pins_for_tests()
    session_id = "sess-dual-clarify"
    rp_session_id = "sess-dual-clarify-rp"

    build_live_chat_response(
        ChatRequest(message="What happened with that alert?", session_id=session_id)
    )
    run_chat_via_resource_planner_graph(
        ChatRequest(message="What happened with that alert?", session_id=rp_session_id)
    )

    from app.chat.session_store import get_session_pins

    imperative_handoff = get_session_pins(session_id).pending_handoff_id  # type: ignore[union-attr]
    rp_handoff = get_session_pins(rp_session_id).pending_handoff_id  # type: ignore[union-attr]
    assert imperative_handoff and rp_handoff

    imperative_second = build_live_chat_response(
        ChatRequest(message="ALT-2024-0891", session_id=session_id)
    )
    rp_second = run_chat_via_resource_planner_graph(
        ChatRequest(message="ALT-2024-0891", session_id=rp_session_id)
    )
    for label, response in (("imperative", imperative_second), ("resource_planner", rp_second)):
        assert response.evidence_plan is not None, label
        resource_plan = response.evidence_plan.get("resource_plan")
        assert isinstance(resource_plan, dict), label
        assert (resource_plan.get("provenance") or {}).get("committed") is True, label

    assert get_handoff(imperative_handoff, 2) is not None
    assert get_handoff(rp_handoff, 2) is not None


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
