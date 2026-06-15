"""O5c — broaden-on-empty orchestration wiring tests.

No live LLM or MCP: the broadened-SPL generator is monkeypatched and the flags
are toggled in-process. Proves the activation guard (default-off => no broaden)
and the trigger -> LLM-proposed -> HIL-gated envelope.
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.orchestration import broaden_orchestration as bo
from app.spl.llm_fallback import LlmSplFallbackResult


def _executed_empty(spl: str = "index=auth sourcetype=linux_secure action=failure | stats count") -> dict:
    return {
        "status": "executed",
        "result_count": 0,
        "executed_spl": spl,
        "selected_mcp_server": "splunk_local",
        "selected_mcp_tool": "splunk_run_query",
    }


def _approved_broadened(spl: str) -> LlmSplFallbackResult:
    return LlmSplFallbackResult(
        candidate_spl=spl,
        approved=True,
        validation={"approved": True, "normalized_spl": spl},
        status="candidate_generated",
    )


@pytest.fixture
def fallback_on(monkeypatch):
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", True)


# --- activation guard ---------------------------------------------------------


def test_no_broaden_when_fallback_flag_off(monkeypatch):
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", False)
    assert (
        bo.should_attempt_broaden(
            selected_skill="spl_generation",
            execution=_executed_empty(),
            has_incoming_review_action=False,
        )
        is False
    )


def test_no_broaden_on_review_action_turn(fallback_on):
    # A confirm/update/reject turn never re-broadens (blocks second broaden).
    assert (
        bo.should_attempt_broaden(
            selected_skill="spl_generation",
            execution=_executed_empty(),
            has_incoming_review_action=True,
        )
        is False
    )


def test_no_broaden_for_non_eligible_skill(fallback_on):
    assert (
        bo.should_attempt_broaden(
            selected_skill="knowledge_recall",
            execution=_executed_empty(),
            has_incoming_review_action=False,
        )
        is False
    )


def test_no_broaden_when_results_present(fallback_on):
    execution = {**_executed_empty(), "result_count": 4}
    assert (
        bo.should_attempt_broaden(
            selected_skill="spl_generation",
            execution=execution,
            has_incoming_review_action=False,
        )
        is False
    )


def test_no_broaden_when_not_executed(fallback_on):
    execution = {**_executed_empty(), "status": "blocked"}
    assert (
        bo.should_attempt_broaden(
            selected_skill="spl_generation",
            execution=execution,
            has_incoming_review_action=False,
        )
        is False
    )


def test_broaden_triggers_on_eligible_empty(fallback_on):
    assert (
        bo.should_attempt_broaden(
            selected_skill="spl_generation",
            execution=_executed_empty(),
            has_incoming_review_action=False,
        )
        is True
    )


# --- decision build -----------------------------------------------------------


def test_decision_surfaces_broaden_hil_and_envelope(monkeypatch, fallback_on):
    broadened = "index=auth sourcetype=linux_secure action=failure earliest=-7d | stats count"
    monkeypatch.setattr(
        bo, "generate_llm_spl_fallback", lambda **_: _approved_broadened(broadened)
    )
    decision = bo.maybe_build_broaden_decision(
        trace_id="t1",
        user_query="why no failed logins?",
        execution=_executed_empty(),
    )
    assert decision is not None
    # New broaden-specific HIL.
    assert decision.review["review_type"] == "spl_broaden_confirmation"
    assert decision.review["required"] is True
    assert decision.review["proposed_normalized_spl"] == broadened
    assert "confirm_execution" in decision.review["allowed_actions"]
    # Approval rides the existing pending-execution gate.
    assert decision.pending_execution_confirmation["normalized_spl"] == broadened
    assert decision.pending_execution_confirmation["source"] == "broaden_scope_on_empty"
    # Orchestration envelope records the empty primary + pending broadened call.
    orch = decision.orchestration
    assert orch["recipe_id"] == "broaden_scope_on_empty"
    assert orch["status"] == "awaiting_approval"
    assert orch["calls"][0]["outcome"] == "empty"
    assert orch["next_call"]["call_id"] == "c2_broadened_search"
    assert orch["next_call"]["approval_state"] == "pending"
    assert orch["next_call"]["requires_hil"] is True
    assert orch["unresolved_evidence_keys"] == ["broadened_search_rows"]


def test_no_decision_when_generator_blocked(monkeypatch, fallback_on):
    monkeypatch.setattr(bo, "generate_llm_spl_fallback", lambda **_: None)
    assert (
        bo.maybe_build_broaden_decision(
            trace_id="t1", user_query="q", execution=_executed_empty()
        )
        is None
    )


def test_no_decision_when_broadened_equals_primary(monkeypatch, fallback_on):
    spl = _executed_empty()["executed_spl"]
    monkeypatch.setattr(bo, "generate_llm_spl_fallback", lambda **_: _approved_broadened(spl))
    assert (
        bo.maybe_build_broaden_decision(
            trace_id="t1", user_query="q", execution=_executed_empty()
        )
        is None
    )


def test_no_decision_when_primary_missing_tool(monkeypatch, fallback_on):
    monkeypatch.setattr(bo, "generate_llm_spl_fallback", lambda **_: _approved_broadened("index=x | head 1"))
    execution = {**_executed_empty(), "selected_mcp_tool": ""}
    assert (
        bo.maybe_build_broaden_decision(
            trace_id="t1", user_query="q", execution=execution
        )
        is None
    )
