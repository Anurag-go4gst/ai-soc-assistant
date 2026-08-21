"""P4 — readable Run/Edit/Cancel HIL and immutable investigation envelope."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.routes_chat import chat
from app.chat.canonical_handoff_store import clear_all_handoffs_for_tests
from app.chat.canonical_planning_orchestrator import graph_node_lane_and_canonical_planning
from app.chat.contracts.investigation_envelope import ApprovedInvestigationEnvelope
from app.chat.investigation_envelope_runtime import (
    InvestigationEnvelopeError,
    build_plan_summary,
    maybe_handle_investigation_review,
)
from app.chat.session_store import clear_all_session_pins_for_tests
from app.config import settings
from app.graph.resource_planner_graph import run_chat_via_resource_planner_graph
from app.query_understanding.parser import understand_query
from app.routing.select_route_from_understanding import select_route_from_understanding
from app.schemas.requests import ChatRequest


QUERY = (
    "Investigate failed login spike for user:alice host:APP-01 "
    "from 10.0.0.8 in the last 24 hours"
)
REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def _p4_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_all_handoffs_for_tests()
    clear_all_session_pins_for_tests()
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_investigation_plan_before_resource_plan_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_capability_snapshot_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_guided_composable_planning_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_investigation_planner_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_session_context_enabled", True)
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", True)


def _initial_state(*, session_id: str = "p4-session") -> dict:
    qu = understand_query(QUERY)
    route, provenance = select_route_from_understanding(qu, QUERY)
    return graph_node_lane_and_canonical_planning(
        {
            "request": SimpleNamespace(message=QUERY, investigation_review_action=None),
            "effective_query": QUERY,
            "query_understanding": qu,
            "routed": {**route, "routing_provenance": provenance},
            "trace_id": "p4-trace",
            "session_id": session_id,
            "route_plan_shadow": {},
        }
    )


def _review(state: dict, action: str, *, edits: dict | None = None) -> dict:
    approval = state["investigation_approval"]
    request = ChatRequest(
        message=QUERY,
        session_id="p4-session",
        investigation_review_action=action,
        investigation_handoff_id=approval["handoff_id"],
        investigation_handoff_version=approval["handoff_version"],
        investigation_plan_edits=edits,
    )
    reviewed = maybe_handle_investigation_review(
        {"request": request, "session_id": "p4-session", "routed": state.get("routed")}
    )
    assert reviewed is not None
    return reviewed


def test_deterministic_plan_is_readable_without_live_reasoning() -> None:
    state = _initial_state()
    approval = state["investigation_approval"]
    assert approval["status"] == "awaiting_approval"
    assert approval["allowed_actions"] == ["run", "edit", "cancel"]
    assert approval["plan_summary"]["what_will_be_checked"]
    assert approval["plan_summary"]["why_it_matters"]
    assert approval["plan_summary"]["scope_and_time"]
    assert approval["plan_summary"]["resources_and_capabilities"]
    assert state["investigation_planning_trace"]["llm_attempted"] is False
    assert "resource_plan" not in state
    assert "evidence_plan" not in state
    assert "execution" not in state


def test_run_mints_immutable_read_only_envelope_without_compiling() -> None:
    reviewed = _review(_initial_state(), "run")
    envelope = reviewed["approved_investigation_envelope"]
    assert reviewed["investigation_approval"]["status"] == "approved"
    assert envelope["envelope_version"] == 2
    assert "all_writes" in envelope["prohibited_actions"]
    assert "remediation" in envelope["prohibited_actions"]
    assert all(not item.startswith("action:") for item in envelope["allowed_read_only_capabilities"])
    assert reviewed.get("evidence_plan") is None
    assert reviewed.get("execution") is None

    contract = ApprovedInvestigationEnvelope.model_validate(envelope)
    with pytest.raises(ValidationError):
        contract.objective = "mutated"  # type: ignore[misc]


def test_run_replay_is_idempotent_and_conflicting_decision_is_rejected() -> None:
    state = _initial_state()
    first = _review(state, "run")
    replay = _review(state, "run")
    assert replay["approved_investigation_envelope"] == first["approved_investigation_envelope"]
    with pytest.raises(InvestigationEnvelopeError, match="already_decided"):
        _review(state, "cancel")


def test_edit_is_deterministically_revalidated_and_does_not_compile() -> None:
    state = _initial_state()
    reviewed = _review(
        state,
        "edit",
        edits={"evidence_needed": ["Correlate successful logins after the failure spike."]},
    )
    approval = reviewed["investigation_approval"]
    assert approval["status"] == "edited_revalidated"
    assert "Correlate successful logins after the failure spike." in approval["validated_plan"]["evidence_needed"]
    assert "analyst_edit_revalidated" in approval["revalidation_warnings"] or (
        "analyst_edit_revalidated" in approval["validated_plan"]["validation_warnings"]
    )
    assert reviewed.get("approved_investigation_envelope") is None
    assert reviewed.get("evidence_plan") is None
    assert reviewed.get("execution") is None


def test_material_edit_returns_to_replanning_without_mutating_rqc() -> None:
    state = _initial_state()
    original_rqc = dict(state["resolved_query_contract"])
    reviewed = _review(state, "edit", edits={"time_scope": "last 60 days"})
    approval = reviewed["investigation_approval"]
    assert approval["status"] == "replanning_required"
    assert "material_scope_change_requires_new_rqc" in approval["revalidation_warnings"]
    assert reviewed["resolved_query_contract"] == original_rqc
    assert reviewed.get("approved_investigation_envelope") is None
    assert reviewed.get("evidence_plan") is None
    assert reviewed.get("execution") is None


def test_cancel_ends_without_envelope_resource_plan_or_execution() -> None:
    reviewed = _review(_initial_state(), "cancel")
    assert reviewed["investigation_approval"]["status"] == "cancelled"
    assert reviewed.get("approved_investigation_envelope") is None
    assert reviewed.get("evidence_plan") is None
    assert reviewed.get("execution") is None


def test_unknown_or_write_capability_edit_cannot_enter_plan() -> None:
    reviewed = _review(
        _initial_state(),
        "edit",
        edits={"capability_requests": ["mcp:invented:read", "action:firewall_block"]},
    )
    plan = reviewed["validated_investigation_plan"]
    ids = {row["capability_id"] for row in plan["capability_bindings"]}
    assert "mcp:invented:read" not in ids
    assert "action:firewall_block" not in ids
    assert any("dropped_unknown_capability" in warning for warning in plan["validation_warnings"])


def test_t13_and_t4_equivalent_plans_have_same_approval_summary() -> None:
    state = _initial_state()
    plan = state["validated_investigation_plan"]
    from app.chat.contracts.investigation_plan import ValidatedInvestigationPlan

    contract = ValidatedInvestigationPlan.model_validate(plan)
    t13 = {**state["resolved_query_contract"], "understanding_source": "deterministic_qualification"}
    t4 = {**state["resolved_query_contract"], "understanding_source": "semantic_t4"}
    assert build_plan_summary(contract, t13) == build_plan_summary(contract, t4)


def test_chat_request_requires_version_bound_review() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(message=QUERY, investigation_review_action="run")
    with pytest.raises(ValidationError):
        ChatRequest(
            message=QUERY,
            investigation_review_action="edit",
            investigation_handoff_id="cpi:test",
            investigation_handoff_version=1,
        )


def test_production_chatpanel_has_readable_actions_without_ec_contracts() -> None:
    card = (REPO_ROOT / "frontend/src/components/InvestigationPlanApprovalCard.tsx").read_text()
    chat_panel = (REPO_ROOT / "frontend/src/components/ChatPanel.tsx").read_text()
    chat_bubble = (REPO_ROOT / "frontend/src/components/ChatBubble.tsx").read_text()
    assert "What will be checked" in card
    assert "Why" in card
    assert "Scope and time" in card
    assert "Useful resources and capabilities" in card
    assert "Run investigation" in card
    assert "Edit plan" in card
    assert "Cancel" in card
    combined = "\n".join((card, chat_panel, chat_bubble))
    assert "app/demo" not in combined
    assert "components/ec/" not in combined


def test_langgraph_two_turn_run_surfaces_envelope_and_no_execution() -> None:
    first = run_chat_via_resource_planner_graph(ChatRequest(message=QUERY))
    assert first.investigation_approval is not None
    approval = first.investigation_approval
    session_id = first.session_context_status.session_id if first.session_context_status else None
    assert session_id

    second = run_chat_via_resource_planner_graph(
        ChatRequest(
            message=QUERY,
            session_id=session_id,
            investigation_review_action="run",
            investigation_handoff_id=str(approval["handoff_id"]),
            investigation_handoff_version=int(approval["handoff_version"]),
        )
    )
    assert second.investigation_approval is not None
    assert second.investigation_approval["status"] == "approved"
    assert second.approved_investigation_envelope is not None
    assert second.evidence_plan is None
    assert second.execution is not None
    assert second.execution.status == "skipped"
    assert second.execution.selected_mcp_tool is None


def test_imperative_chat_two_turn_cancel_has_no_resource_plan_or_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", False)
    first = chat(ChatRequest(message=QUERY))
    assert first.investigation_approval is not None
    approval = first.investigation_approval
    session_id = first.session_context_status.session_id if first.session_context_status else None
    assert session_id

    second = chat(
        ChatRequest(
            message=QUERY,
            session_id=session_id,
            investigation_review_action="cancel",
            investigation_handoff_id=str(approval["handoff_id"]),
            investigation_handoff_version=int(approval["handoff_version"]),
        )
    )
    assert second.investigation_approval is not None
    assert second.investigation_approval["status"] == "cancelled"
    assert second.approved_investigation_envelope is None
    assert second.evidence_plan is None
    assert second.execution is not None
    assert second.execution.status == "skipped"
    assert second.execution.selected_mcp_tool is None
