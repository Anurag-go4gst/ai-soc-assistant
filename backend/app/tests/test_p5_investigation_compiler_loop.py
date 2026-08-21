"""P5 — approved envelope compiler, RP-hub observation, and honest stop."""

from __future__ import annotations

import inspect

import pytest

from app.chat.contracts.investigation_envelope import ApprovedInvestigationEnvelope
from app.chat.contracts.investigation_plan import (
    InvestigationCapabilityBinding,
    ValidatedInvestigationPlan,
)
from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.chat.investigation_run_compiler import (
    attach_investigation_observation,
    compile_approved_investigation,
)
from app.chat import pipeline
from app.chat.canonical_handoff_store import clear_all_handoffs_for_tests
from app.chat.pipeline import build_live_chat_response
from app.chat.session_store import clear_all_session_pins_for_tests
from app.config import settings
from app.graph.resource_planner_graph import run_chat_via_resource_planner_graph
from app.schemas.requests import ChatRequest


def _rqc(*, source: str = "deterministic_qualification") -> ResolvedQueryContract:
    return ResolvedQueryContract(
        normalized_goal="Investigate authentication activity for alice",
        intent_family="guided_investigation",
        answer_goal="live_results",
        ambiguity_state="unambiguous",
        required_capabilities=frozenset({"spl", "mcp"}),
        evidence_requirements=["authentication_events"],
        entities={"user": "alice"},
        time_scope="last 24 hours",
        qualification_tier="T4",
        qualification_source="test",
        understanding_source=source,
    )


def _plan() -> ValidatedInvestigationPlan:
    return ValidatedInvestigationPlan(
        investigation_objective="Investigate authentication activity for alice",
        evidence_needed=["authentication_events"],
        data_categories=["authentication_events"],
        capability_bindings=[
            InvestigationCapabilityBinding(
                capability_id="mcp:splunk:splunk_run_query",
                capability_need="required",
                availability="available",
                access_mode="read_only",
            )
        ],
        human_review_required=True,
    )


def _envelope(version: int = 2) -> ApprovedInvestigationEnvelope:
    return ApprovedInvestigationEnvelope(
        envelope_version=version,
        objective="Investigate authentication activity for alice",
        targets=["user:alice"],
        entities={"user": "alice"},
        time_scope="last 24 hours",
        approved_evidence_categories=["authentication_events"],
        allowed_read_only_capabilities=["mcp:splunk:splunk_run_query"],
    )


def test_compiler_requires_matching_envelope_version() -> None:
    with pytest.raises(ValueError, match="envelope_version"):
        compile_approved_investigation(
            envelope=_envelope(1),
            validated_plan=_plan(),
            resolved_query_contract=_rqc(),
            handoff_id="cpi:p5",
            handoff_version=2,
        )


@pytest.mark.parametrize("source", ["deterministic_qualification", "semantic_t4"])
def test_all_tiers_compile_through_same_envelope_compiler(source: str) -> None:
    compiled = compile_approved_investigation(
        envelope=_envelope(),
        validated_plan=_plan(),
        resolved_query_contract=_rqc(source=source),
        handoff_id="cpi:p5",
        handoff_version=2,
        use_case_id="auth_failed_login_spike",
    )
    provenance = compiled.resource_plan.provenance
    assert provenance["committed"] is True
    assert provenance["envelope_version"] == 2
    assert compiled.evidence_plan.resource_plan == compiled.resource_plan.model_dump(mode="json")
    assert "execution" in compiled.phase_contract.names


def test_no_resource_plan_without_envelope() -> None:
    state = attach_investigation_observation({"evidence_plan": {"resource_plan": {"steps": []}}})
    assert "investigation_run_status" not in state


def test_gap_stops_honestly_without_plan_delta_and_progress_has_no_cot() -> None:
    compiled = compile_approved_investigation(
        envelope=_envelope(),
        validated_plan=_plan(),
        resolved_query_contract=_rqc(),
        handoff_id="cpi:p5",
        handoff_version=2,
    )
    state = attach_investigation_observation(
        {
            "approved_investigation_envelope": _envelope().model_dump(mode="json"),
            "evidence_plan": compiled.evidence_plan.model_dump(mode="json"),
            "evidence_sufficiency": {"status": "INSUFFICIENT", "missing": ["authentication_events"]},
            "evidence_state": {"missing": ["authentication_events"]},
            "execution": {"status": "blocked", "block_reason": "human_review_required"},
        }
    )
    assert state["investigation_run_status"] == {
        "status": "incomplete",
        "stop_reason": "missing_evidence_no_plan_delta_in_p5",
        "missing_evidence": ["authentication_events"],
        "next_action": "stop",
        "plan_delta_emitted": False,
    }
    text = str(state["investigation_progress"]).lower()
    assert "chain-of-thought" not in text
    assert "reasoning" not in text
    assert "finding: -" not in text


def test_p5_does_not_import_plan_delta_and_retires_live_guided_loop() -> None:
    compiler_source = inspect.getsource(compile_approved_investigation)
    pipeline_source = inspect.getsource(pipeline._run_live_chat_pipeline)
    assert "PlanDelta" not in compiler_source
    assert "ai_soc_resource_plan_execution_enabled" in pipeline_source


def test_existing_execution_flag_is_the_only_p5_activation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", False)
    assert settings.ai_soc_resource_plan_execution_enabled is False
    assert not hasattr(settings, "ai_soc_rp_investigation_loop_enabled")


def test_run_compiles_and_returns_to_rp_hub_before_honest_gap_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_all_handoffs_for_tests()
    clear_all_session_pins_for_tests()
    for name, value in {
        "ai_soc_curated_enrichment_activation_enabled": True,
        "ai_soc_investigation_plan_before_resource_plan_enabled": True,
        "ai_soc_capability_snapshot_enabled": True,
        "ai_soc_guided_composable_planning_enabled": True,
        "ai_soc_investigation_planner_enabled": False,
        "ai_soc_session_context_enabled": True,
        "ai_soc_resource_plan_execution_enabled": True,
        "langgraph_orchestration_enabled": True,
    }.items():
        monkeypatch.setattr(settings, name, value)
    query = (
        "Investigate failed login spike for user:alice host:APP-01 "
        "from 10.0.0.8 in the last 24 hours"
    )
    first = run_chat_via_resource_planner_graph(ChatRequest(message=query))
    approval = first.investigation_approval
    assert approval is not None
    assert first.evidence_plan is None
    assert first.session_context_status is not None

    second = run_chat_via_resource_planner_graph(
        ChatRequest(
            message=query,
            session_id=first.session_context_status.session_id,
            investigation_review_action="run",
            investigation_handoff_id=str(approval["handoff_id"]),
            investigation_handoff_version=int(approval["handoff_version"]),
        )
    )
    assert second.evidence_plan is not None
    resource = second.evidence_plan["resource_plan"]
    assert resource["provenance"]["committed"] is True
    assert resource["provenance"]["envelope_version"] == 2
    assert second.investigation_run_status is not None
    assert second.investigation_run_status["status"] == "incomplete"
    assert second.investigation_run_status["plan_delta_emitted"] is False
    assert second.investigation_progress
    assert second.execution is not None


def test_imperative_rollback_path_uses_same_compiler_and_governed_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_all_handoffs_for_tests()
    clear_all_session_pins_for_tests()
    for name, value in {
        "ai_soc_curated_enrichment_activation_enabled": True,
        "ai_soc_investigation_plan_before_resource_plan_enabled": True,
        "ai_soc_capability_snapshot_enabled": True,
        "ai_soc_guided_composable_planning_enabled": True,
        "ai_soc_investigation_planner_enabled": False,
        "ai_soc_session_context_enabled": True,
        "ai_soc_resource_plan_execution_enabled": True,
        "langgraph_orchestration_enabled": False,
    }.items():
        monkeypatch.setattr(settings, name, value)
    query = (
        "Investigate failed login spike for user:alice host:APP-01 "
        "from 10.0.0.8 in the last 24 hours"
    )
    first = build_live_chat_response(ChatRequest(message=query))
    approval = first.investigation_approval
    assert approval is not None
    assert first.session_context_status is not None
    second = build_live_chat_response(
        ChatRequest(
            message=query,
            session_id=first.session_context_status.session_id,
            investigation_review_action="run",
            investigation_handoff_id=str(approval["handoff_id"]),
            investigation_handoff_version=int(approval["handoff_version"]),
        )
    )
    assert second.evidence_plan is not None
    assert second.evidence_plan["resource_plan"]["provenance"]["committed"] is True
    assert second.execution is not None
