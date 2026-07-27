"""Outcome-aware response validation (plan item 22)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.chat.contracts.canonical_planning_outcome import (
    clarification_outcome,
    planned_outcome,
    policy_blocked_outcome,
)
from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.planning_telemetry import planning_events, reset_planning_telemetry_for_tests
from app.chat.response_validation import (
    emit_request_failed,
    emit_response_generated,
    validate_assembled_response,
    validate_final_response,
)
from app.planner.resource_plan import ResourcePlan


def _planned_evidence(**overrides: Any) -> dict[str, Any]:
    base = EvidencePlan(
        answer_mode="live_investigation",
        rag_phase="pre_mcp",
        needs_rag=True,
        needs_spl=True,
        needs_mcp=False,
        needs_mitre=False,
        spl_allowed=True,
        mcp_allowed=False,
        policy_context_required=False,
        policy_context_recommended=False,
    ).model_dump()
    base.update(overrides)
    return base


def _committed_plan(*, plan_id: str = "rp:test", steps: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return ResourcePlan(
        plan_source="deterministic",
        steps=steps or [{"step_id": "s1", "resource_id": "rag", "purpose": "knowledge_retrieval", "status": "executed"}],
        provenance={"committed": True, "resource_plan_id": plan_id},
    ).model_dump()


def _planned_state(**extra: Any) -> dict[str, Any]:
    evidence = _planned_evidence(resource_plan=_committed_plan())
    outcome = planned_outcome(
        canonical_input={"routing": {"answer_goal": "live_results"}},
        evidence_plan=evidence,
        resource_plan=evidence["resource_plan"],
    )
    return {
        "canonical_planning_outcome": outcome.model_dump(),
        "evidence_plan": evidence,
        "plan_dispatch_trace": {"dispatch_source": "plan_dispatch", "resource_plan_id": "rp:test"},
        "execution": {"status": "skipped"},
        **extra,
    }


@pytest.fixture(autouse=True)
def _reset_telemetry() -> None:
    reset_planning_telemetry_for_tests()
    yield
    reset_planning_telemetry_for_tests()


def test_missing_required_evidence_fails_validation() -> None:
    state = _planned_state()
    state["evidence_plan"]["missing_required_evidence"] = ["live_rows"]
    status, reasons = validate_final_response(state)
    assert status == "failed"
    assert "missing_required_evidence" in reasons


def test_failed_execution_step_fails_validation() -> None:
    state = _planned_state(execution={"status": "failed"})
    status, reasons = validate_final_response(state)
    assert status == "failed"
    assert "failed_execution_step" in reasons


def test_resource_plan_id_mismatch_fails_validation() -> None:
    state = _planned_state(plan_dispatch_trace={"dispatch_source": "plan_dispatch", "resource_plan_id": "rp:other"})
    status, reasons = validate_final_response(state)
    assert status == "failed"
    assert "resource_plan_id_mismatch" in reasons


def test_wrong_answer_goal_spl_artifact_unsatisfied() -> None:
    state = _planned_state()
    state["evidence_plan"]["needs_spl"] = True
    state["answer_contract"] = {"answer_goal": ["spl_artifact"]}
    status, reasons = validate_final_response(state)
    assert status == "failed"
    assert "answer_goal_unsatisfied" in reasons


def test_missing_knowledge_citation_on_rag_only_path() -> None:
    evidence = _planned_evidence(
        answer_mode="rag_only",
        needs_rag=True,
        needs_spl=False,
        resource_plan=_committed_plan(),
    )
    outcome = planned_outcome(
        canonical_input={"routing": {"answer_goal": "reference_lookup"}},
        evidence_plan=evidence,
        resource_plan=evidence["resource_plan"],
    )
    state = {
        "canonical_planning_outcome": outcome.model_dump(),
        "evidence_plan": evidence,
        "answer_contract": {"answer_goal": ["reference_lookup"]},
    }
    status, reasons = validate_final_response(state)
    assert status == "failed"
    assert "missing_knowledge_citation" in reasons


def test_unexecuted_remediation_claim_fails_assembled_validation() -> None:
    state = _planned_state(execution={"status": "skipped"})
    analyst_response = SimpleNamespace(
        recommended_actions=["Host WRONG-99 was isolated successfully"],
        investigation_steps=[],
        analyst_checklist=[],
        direct_answer_summary="",
        response_profile="hybrid_alert_review",
        reference_facts=[],
        retrieved_playbook=None,
    )
    status, reasons = validate_assembled_response(state, analyst_response=analyst_response)
    assert status == "failed"
    assert "unexecuted_remediation_claim" in reasons


def test_response_assembly_failure_when_analyst_response_missing() -> None:
    state = _planned_state()
    status, reasons = validate_assembled_response(state, analyst_response=None)
    assert status == "failed"
    assert "response_assembly_failure" in reasons


def test_clarification_still_passes_without_resource_plan() -> None:
    outcome = clarification_outcome(
        canonical_input={"routing": {"processing_lane": "known"}},
        question="Which host?",
        unresolved_fields=["host"],
        handoff_id="h-1",
        handoff_version=1,
    )
    status, reasons = validate_final_response({"canonical_planning_outcome": outcome.model_dump()})
    assert (status, reasons) == ("ok", [])


def test_policy_block_with_execution_fails_pre_assembly() -> None:
    outcome = policy_blocked_outcome(canonical_input=None, policy_reason="unsafe_execution_request")
    state = {
        "canonical_planning_outcome": outcome.model_dump(),
        "execution": {"status": "executed"},
    }
    status, reasons = validate_final_response(state)
    assert status == "failed"
    assert "policy_restriction_violated" in reasons


def test_terminal_failure_skips_response_generated() -> None:
    state = _planned_state()
    state = emit_request_failed(state, reason="response_validation_failed")
    state = emit_response_generated(state)
    events = [event.get("event") for event in planning_events()]
    assert "request.failed" in events
    assert "response.generated" not in events


def test_assembled_validation_allows_knowledge_citation() -> None:
    state = _planned_state()
    evidence = state["evidence_plan"]
    evidence["answer_mode"] = "rag_only"
    state["source_evidence"] = [{"source_id": "kb-1", "snippet": "policy text"}]
    analyst_response = SimpleNamespace(
        recommended_actions=[],
        investigation_steps=[],
        analyst_checklist=[],
        direct_answer_summary="Policy summary",
        response_profile="knowledge_recall",
        reference_facts=[{"id": "kb-1"}],
        retrieved_playbook={"title": "Escalation"},
    )
    status, reasons = validate_assembled_response(state, analyst_response=analyst_response)
    assert status == "ok"
    assert reasons == []
