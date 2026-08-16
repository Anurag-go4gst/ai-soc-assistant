"""F1 — DB/resource-state loss must not masquerade as normal ResourcePlan authority.

Proven production path (Plan 7 D1): postgres down → ResourcePlan cannot commit →
``_rp_dispatch_route`` / imperative dispatch skip send the turn through
``build_non_planned_dispatch_state`` → ``dispatch_source=canonical_non_planned``
with ``downgrade_reason``/``resource_downgrade`` null. Chat still answers.

That ``canonical_non_planned`` label is also the legitimate clarification /
policy-block path. F1 requires a deterministic degraded-authority signal only
when the non-planned path was taken because ResourcePlan authority could not
operate due to DB/resource-state failure — not on every non-planned outcome.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from app.chat import canonical_handoff_repository as handoff_repo
from app.chat.canonical_db import reset_canonical_db_for_tests
from app.chat.canonical_mode import (
    build_non_planned_dispatch_state,
    build_persistence_failed_state,
)
from app.chat.contracts.canonical_planning_outcome import (
    clarification_outcome,
    failure_outcome,
    outcome_from_state,
    policy_blocked_outcome,
)
from app.chat.debug_summary import build_debug_summary
from app.chat.planning_telemetry import reset_planning_telemetry_for_tests
from app.chat.response_contract_bridge import (
    build_planning_outcome_summary,
    enrich_placeholder_response,
)
from app.config import settings
from app.graph.resource_planner_graph import _rp_dispatch_route, rp_node_non_planned_finalize
from app.schemas.requests import ChatRequest
from app.schemas.responses import PlaceholderResponse, PlanningOutcomeSummary
from app.tests.support.canonical_flow import run_canonical_flow

_PLANNED_QUERY = "What is CVE-2026-12345?"
_CLARIFY_QUERY = "What happened with that alert?"


@pytest.fixture(autouse=True)
def _canonical_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_session_context_enabled", True)
    reset_planning_telemetry_for_tests()
    prior_in_memory = handoff_repo.in_memory_handoff_store_enabled()
    reset_canonical_db_for_tests()
    handoff_repo.clear_in_memory_store_for_tests()
    handoff_repo.use_in_memory_store_for_tests(True)
    yield
    handoff_repo.clear_in_memory_store_for_tests()
    handoff_repo.use_in_memory_store_for_tests(prior_in_memory)
    reset_canonical_db_for_tests()


def _inject_db_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail ResourcePlan/handoff persist the way live DB loss does.

    Patch ``save_handoff_record`` itself so in-memory test stores (conftest and
    ``sentinel_runtime``) cannot hide the failure the way a unit-of-work mock can.
    """

    def _fail_save(_record: Any, **_kwargs: Any) -> Any:
        raise handoff_repo.HandoffPersistenceError(
            "canonical_handoff_db_unavailable",
            operation="handoff_persist",
        )

    monkeypatch.setattr(handoff_repo, "save_handoff_record", _fail_save)
    monkeypatch.setattr("app.chat.canonical_handoff_store.save_handoff_record", _fail_save)


def _dispatch(state: dict[str, Any]) -> dict[str, Any]:
    raw = state.get("plan_dispatch_trace")
    return raw if isinstance(raw, dict) else {}


def test_persistence_failed_non_planned_does_not_masquerade_as_canonical_non_planned() -> None:
    """Unit reproduction of the D1 labelling overwrite."""
    failed = build_persistence_failed_state(
        {"trace_id": "t-f1"},
        reason="canonical_handoff_db_unavailable",
        category="database",
    )
    assert failed["plan_dispatch_trace"]["dispatch_source"] == "canonical_failure"
    assert outcome_from_state(failed) is not None
    assert outcome_from_state(failed).status == "persistence_failed"

    out = build_non_planned_dispatch_state(failed, status="persistence_failed")
    trace = _dispatch(out)
    assert trace["dispatch_source"] != "canonical_non_planned"
    assert trace["dispatch_source"] != "resource_plan_step_walk"
    assert trace["canonical_status"] == "persistence_failed"
    assert trace.get("resource_plan_authority") == "degraded"
    assert trace.get("resource_plan_authority_reason") == "persistence_failed"


def test_clarification_non_planned_is_not_labelled_db_unavailable() -> None:
    state = build_non_planned_dispatch_state(
        {
            "trace_id": "t-clarify",
            "canonical_planning_outcome": clarification_outcome(
                canonical_input={"routing": {"processing_lane": "known"}},
                question="Which host?",
                unresolved_fields=["host"],
                handoff_id="h-1",
                handoff_version=1,
                reason="known_clarification",
            ).model_dump(),
        },
        status="clarification_required",
    )
    trace = _dispatch(state)
    assert trace["dispatch_source"] == "canonical_non_planned"
    assert trace["canonical_status"] == "clarification_required"
    assert trace.get("resource_plan_authority") != "degraded"
    assert trace.get("resource_plan_authority_reason") != "persistence_failed"
    summary = build_planning_outcome_summary(state)
    assert summary is not None
    assert summary.status == "clarification_required"
    assert summary.category != "database"


def test_policy_blocked_non_planned_is_not_labelled_db_unavailable() -> None:
    state = build_non_planned_dispatch_state(
        {
            "canonical_planning_outcome": policy_blocked_outcome(
                canonical_input=None,
                policy_reason="unsafe_execution_request",
            ).model_dump(),
        },
        status="policy_blocked",
    )
    trace = _dispatch(state)
    assert trace["dispatch_source"] == "canonical_non_planned"
    assert trace.get("resource_plan_authority") != "degraded"
    summary = build_planning_outcome_summary(state)
    assert summary is not None
    assert summary.status == "policy_blocked"
    assert summary.category != "database"


def test_db_loss_graph_dispatch_signals_degraded_resource_plan_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _inject_db_unavailable(monkeypatch)
    result = run_canonical_flow(_PLANNED_QUERY)
    outcome = outcome_from_state(result.state)
    assert outcome is not None
    assert outcome.status == "persistence_failed"
    assert "evidence_plan" not in result.state

    assert _rp_dispatch_route(result.state) == "non_planned_finalize"
    dispatched = rp_node_non_planned_finalize(result.state)
    trace = _dispatch(dispatched)
    assert trace["dispatch_source"] != "canonical_non_planned"
    assert trace["dispatch_source"] != "resource_plan_step_walk"
    assert trace["canonical_status"] == "persistence_failed"
    assert trace.get("resource_plan_authority") == "degraded"
    assert trace.get("resource_plan_authority_reason") == "persistence_failed"

    summary = build_planning_outcome_summary(dispatched)
    assert summary is not None
    assert summary.status == "persistence_failed"
    assert summary.category == "database"
    assert "resourceplan" in summary.user_message.lower().replace(" ", "") or (
        "authority" in summary.user_message.lower()
    )


def test_db_recovery_restores_normal_resource_plan_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with monkeypatch.context() as injected:
        _inject_db_unavailable(injected)
        down = run_canonical_flow(_PLANNED_QUERY, trace_id="t-f1-down")
        assert outcome_from_state(down.state) is not None
        assert outcome_from_state(down.state).status == "persistence_failed"

    recovered = run_canonical_flow(_PLANNED_QUERY, trace_id="t-f1-up")
    outcome = outcome_from_state(recovered.state)
    assert outcome is not None
    assert outcome.status == "planned"
    assert recovered.committed is True
    dispatch = _dispatch(recovered.state)
    assert dispatch.get("resource_plan_authority") != "degraded"
    assert dispatch.get("dispatch_source") != "canonical_failure"


def test_llm_shaped_payload_cannot_clear_persistence_degradation() -> None:
    state = {
        "canonical_planning_outcome": failure_outcome(
            "persistence_failed",
            category="database",
            reason="canonical_handoff_db_unavailable",
        ).model_dump(),
        "plan_dispatch_trace": {
            "dispatch_source": "canonical_failure",
            "canonical_status": "persistence_failed",
            "resource_plan_authority": "degraded",
            "resource_plan_authority_reason": "persistence_failed",
        },
    }
    forged = PlaceholderResponse(
        trace_id="t-llm",
        message="LLM claims this is a normal authoritative investigation.",
        note="n",
        planning_outcome=PlanningOutcomeSummary(
            status="planned",
            user_message="Investigation planning completed.",
            recovery_hint="",
            category=None,
        ),
    )
    enriched = enrich_placeholder_response(forged, state)
    assert enriched.planning_outcome is not None
    assert enriched.planning_outcome.status == "persistence_failed"
    assert enriched.planning_outcome.category == "database"
    assert enriched.planning_outcome.status != "planned"
    assert "ResourcePlan authority" in enriched.planning_outcome.user_message
    assert "LLM claims" not in enriched.planning_outcome.user_message


def test_debug_summary_surfaces_degraded_resource_plan_authority() -> None:
    summary = build_debug_summary(
        payload={
            "plan_dispatch_trace": {
                "dispatch_source": "canonical_failure",
                "canonical_status": "persistence_failed",
                "dispatch_schedule": [],
                "resource_plan_authority": "degraded",
                "resource_plan_authority_reason": "persistence_failed",
            }
        }
    )
    schedule = summary["schedule"]
    assert schedule.get("resource_plan_authority") == "degraded"
    assert schedule.get("resource_plan_authority_reason") == "persistence_failed"


def test_rp_graph_db_loss_does_not_claim_resource_plan_step_walk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.evals.sentinel_eval import sentinel_runtime
    from app.graph.resource_planner_graph import run_chat_via_resource_planner_graph

    _inject_db_unavailable(monkeypatch)
    with sentinel_runtime():
        response = run_chat_via_resource_planner_graph(ChatRequest(message=_PLANNED_QUERY))

    assert response.planning_outcome is not None
    assert response.planning_outcome.status == "persistence_failed"
    assert response.planning_outcome.category == "database"
    assert "ResourcePlan authority" in response.planning_outcome.user_message
    plan_dispatch = (response.control_plane_trace or {}).get("plan_dispatch") or {}
    assert plan_dispatch.get("dispatch_source") != "resource_plan_step_walk"
    assert plan_dispatch.get("dispatch_source") != "canonical_non_planned"
    assert plan_dispatch.get("resource_plan_authority") == "degraded"
    assert response.execution is None or getattr(response.execution, "status", None) != "executed"
    workflow = response.workflow_plan
    if workflow is not None:
        assert workflow.execution_enabled is False
