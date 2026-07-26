"""Production routing contract: unsafe actions emit policy_blocked outcomes (Item 21)."""

from __future__ import annotations

from typing import Any

import pytest

from app.chat.canonical_policy_boundary import POLICY_REASON_UNSAFE_ACTION
from app.chat.contracts.canonical_planning_outcome import outcome_from_state
from app.chat.pipeline import build_live_chat_response
from app.chat.planning_telemetry import planning_events, reset_planning_telemetry_for_tests
from app.chat.response_validation import validate_final_response
from app.schemas.requests import ChatRequest
from app.tests.support.canonical_flow import run_canonical_flow

_UNSAFE_BLOCK_QUERY = "Block IP 10.0.0.5 immediately"
_CLARIFICATION_QUERY = "What happened with that alert?"


@pytest.fixture(autouse=True)
def _canonical_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "ai_soc_session_context_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_live_chat_ec_parity_enabled", False)
    monkeypatch.setattr(settings, "telemetry_mode", "none")
    monkeypatch.setattr(settings, "ai_soc_telemetry_sink", "none")


@pytest.fixture(autouse=True)
def _reset_telemetry() -> None:
    reset_planning_telemetry_for_tests()
    yield
    reset_planning_telemetry_for_tests()


def _plan_dispatch(body: dict[str, Any]) -> dict[str, Any]:
    trace = body.get("control_plane_trace")
    if isinstance(trace, dict):
        dispatch = trace.get("plan_dispatch")
        if isinstance(dispatch, dict):
            return dispatch
    return {}


def test_unsafe_block_live_query_emits_policy_blocked_outcome() -> None:
    response = build_live_chat_response(ChatRequest(message=_UNSAFE_BLOCK_QUERY))
    body = response.model_dump()
    dispatch = _plan_dispatch(body)
    trace = body.get("control_plane_trace") or {}
    blocked = trace.get("blocked_action_state") or {}

    assert dispatch.get("canonical_status") == "policy_blocked"
    assert dispatch.get("dispatch_source") == "canonical_non_planned"
    assert dispatch.get("dispatch_schedule") == []
    assert blocked.get("status") == "blocked"
    assert blocked.get("reason") == POLICY_REASON_UNSAFE_ACTION
    assert response.evidence_plan is None
    assert response.human_review is not None
    assert response.human_review.reason == POLICY_REASON_UNSAFE_ACTION
    assert (response.planning_decision or {}).get("path_type") == "unsafe_blocked"


def test_unsafe_block_canonical_flow_has_no_plan_or_execution_events() -> None:
    result = run_canonical_flow(_UNSAFE_BLOCK_QUERY, session_id="sess-policy", trace_id="trace-policy")
    outcome = outcome_from_state(result.state)
    assert outcome is not None
    assert outcome.status == "policy_blocked"
    assert outcome.policy_reason == POLICY_REASON_UNSAFE_ACTION
    assert "evidence_plan" not in result.state

    events = [event.get("event") for event in planning_events()]
    assert "resource_plan.created" not in events
    assert "execution.started" not in events
    assert "execution.completed" not in events
    assert "clarification.requested" not in events

    status, reasons = validate_final_response(result.state)
    assert (status, reasons) == ("ok", [])


def test_clarification_query_still_emits_clarification_not_policy_blocked() -> None:
    result = run_canonical_flow(_CLARIFICATION_QUERY, session_id="sess-clarify-policy")
    outcome = outcome_from_state(result.state)
    assert outcome is not None
    assert outcome.status == "clarification_required"
    assert outcome.status != "policy_blocked"

    events = [event.get("event") for event in planning_events()]
    assert "clarification.requested" in events
    assert "resource_plan.created" not in events
