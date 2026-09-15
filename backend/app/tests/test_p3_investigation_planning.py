"""P3 — advisory reasoning proposal -> DET ValidatedInvestigationPlan."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.chat.contracts.investigation_plan import InvestigationPlan
from app.chat.canonical_handoff_store import clear_all_handoffs_for_tests
from app.chat.canonical_planning_orchestrator import graph_node_lane_and_canonical_planning
from app.chat.guided_investigation_plan_llm import (
    InvestigationPlanLlmResult,
    propose_investigation_plan_llm,
)
from app.chat.guided_investigation_planner import validate_investigation_plan
from app.chat.investigation_plan_builder import build_deterministic_investigation_plan
from app.chat.investigation_plan_runtime import maybe_attach_validated_investigation_plan
from app.chat.pipeline import ChatPipelineState
from app.config import settings
from app.llm.registry_settings import REASONING_PROVIDER_ID, ROLE_DEFAULTS
from app.llm.sidecar_clients import SidecarInvocationResult
from app.graph.resource_planner_graph import run_chat_via_resource_planner_graph
from app.query_understanding.parser import understand_query
from app.routing.select_route_from_understanding import select_route_from_understanding
from app.safeguards.trust_boundary import CONTROL_PREAMBLE, wrap_untrusted_source
from app.schemas.requests import ChatRequest


RQC = {
    "normalized_goal": "Investigate an authentication anomaly",
    "intent_family": "live_investigation",
    "answer_goal": "live_results",
    "required_capabilities": ["spl_required", "mcp_required"],
    "evidence_requirements": ["authentication events", "identity context"],
    "entities": {"user": ["alice"], "host": ["APP-01"]},
    "time_scope": "last 24 hours",
    "locked_fields": {"entities": True, "time_scope": True},
    "unresolved_fields": [],
}
SNAPSHOT = {
    "schema_version": "capability_snapshot_v1",
    "rows": [
        {
            "capability_id": "mcp:splunk_soc:splunk_run_query",
            "capability_need": "required",
            "availability": "available",
        },
        {
            "capability_id": "mcp:agilius:agilius_list_patches",
            "capability_need": "recommended",
            "availability": "unavailable",
        },
        {
            "capability_id": "action:firewall_block",
            "capability_need": "recommended",
            "availability": "unavailable",
        },
    ],
}


@pytest.fixture(autouse=True)
def _flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_investigation_planner_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", False)


def _baseline(rqc: dict | None = None) -> InvestigationPlan:
    payload = dict(rqc or RQC)
    return build_deterministic_investigation_plan(
        query=str(payload["normalized_goal"]),
        resolved_query_contract=payload,
        capability_snapshot=SNAPSHOT,
    )


def test_investigation_planner_is_reasoning_family_advisory_only() -> None:
    role = next(item for item in ROLE_DEFAULTS if item["role"] == "investigation_planner")
    assert role["preferred_provider"] == REASONING_PROVIDER_ID
    assert role["authority"] == "advisory"
    assert role["validator_required"] is True
    assert role["execution_eligible"] is False


def test_det_validator_preserves_t13_facts_and_binds_snapshot_only() -> None:
    proposal = {
        "hypotheses": ["A valid generic hypothesis."],
        "evidence_needed": ["Corroborating evidence."],
        "capability_requests": [
            "mcp:agilius:agilius_list_patches",
            "mcp:invented:invented_read",
            "action:firewall_block",
        ],
        "success_criteria": ["Record corroborating or negative evidence."],
    }
    validated = validate_investigation_plan(
        _baseline(),
        proposal,
        llm_attempted=True,
        capability_snapshot=SNAPSHOT,
    )
    bindings = {item.capability_id: item for item in validated.capability_bindings}
    assert bindings["mcp:splunk_soc:splunk_run_query"].access_mode == "read_only"
    assert bindings["mcp:agilius:agilius_list_patches"].access_mode == "manual_or_alternate"
    assert "mcp:invented:invented_read" not in bindings
    assert "action:firewall_block" not in bindings
    assert any(item.startswith("entity:user=") for item in validated.authoritative_facts)
    assert "time_scope:last 24 hours" in validated.authoritative_facts
    assert any("dropped_unknown_capability" in item for item in validated.validation_warnings)
    assert any("dropped_non_read_capability" in item for item in validated.validation_warnings)
    dumped = validated.model_dump()
    for forbidden in ("resource_plan", "execution", "auth0", "execution_eligible", "mcp_allowed"):
        assert forbidden not in dumped


def test_same_final_rqc_semantics_converge_for_t13_and_t4() -> None:
    t13 = {**RQC, "understanding_source": "deterministic_qualification", "provenance": {"t13": True}}
    t4 = {**RQC, "understanding_source": "semantic_t4", "provenance": {"t4": True}}
    a = validate_investigation_plan(_baseline(t13), capability_snapshot=SNAPSHOT)
    b = validate_investigation_plan(_baseline(t4), capability_snapshot=SNAPSHOT)
    assert a.model_dump() == b.model_dump()


def test_reasoning_prompt_grounds_the_case_inside_the_trust_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The planner sees THIS investigation — as labelled untrusted input only.

    A planner given no case data can only return generic SOC filler, which the
    validator then merges into the analyst-visible plan. So the query IS sent,
    but it must arrive inside the untrusted-source delimiters with the control
    preamble ahead of it, and the tool vocabulary offered to the model must come
    from the CapabilitySnapshot rather than the raw estate.
    """
    captured: dict[str, str] = {}

    def _invoke(**kwargs: object) -> SidecarInvocationResult:
        captured["prompt"] = str(kwargs["user_prompt"])
        return SidecarInvocationResult(
            raw_output=json.dumps(
                {
                    "hypotheses": ["Review a benign and an adversarial explanation."],
                    "evidence_needed": ["Seek independent corroboration."],
                    "dependencies": [],
                    "conditions": [],
                    "success_criteria": ["Record supported and unsupported hypotheses."],
                    "capability_requests": ["mcp:not_in_snapshot:evil_tool"],
                }
            ),
            timed_out=False,
            answered_label="reasoning-test",
            circuit_state="closed",
        )

    monkeypatch.setattr(
        "app.chat.guided_investigation_plan_llm.invoke_sidecar_role_with_metadata",
        _invoke,
    )
    query = "Investigate repeated DNS lookups and denied firewall sessions from 10.20.4.51"
    baseline = build_deterministic_investigation_plan(
        query=query,
        resolved_query_contract={**RQC, "normalized_goal": query},
        capability_snapshot=SNAPSHOT,
    )
    result = propose_investigation_plan_llm(
        query=query,
        baseline=baseline,
        capability_ids=["mcp:splunk_soc:splunk_run_query"],
    )
    assert result.attempted is True
    assert result.provider_label == "reasoning-test"

    prompt = captured["prompt"]
    # The case reaches the model...
    assert "10.20.4.51" in prompt
    # ...as untrusted data, behind the control preamble.
    assert CONTROL_PREAMBLE in prompt
    assert prompt.index(CONTROL_PREAMBLE) < prompt.index("10.20.4.51")
    assert wrap_untrusted_source("user_query", query) in prompt
    # Only snapshot capabilities are offered as vocabulary.
    assert "mcp:splunk_soc:splunk_run_query" in prompt
    assert "mcp:agilius:agilius_list_patches" not in prompt
    # An off-snapshot capability request stays advisory and is dropped by DET.
    validated = validate_investigation_plan(
        baseline,
        result.proposal,
        llm_attempted=True,
        capability_snapshot=SNAPSHOT,
    )
    assert all(
        binding.capability_id != "mcp:not_in_snapshot:evil_tool"
        for binding in validated.capability_bindings
    )
    assert "dropped_unknown_capability:mcp:not_in_snapshot:evil_tool" in (
        validated.validation_warnings
    )

def test_planner_failure_degrades_to_deterministic_validated_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.chat.investigation_plan_runtime.propose_investigation_plan_llm",
        lambda **_kwargs: InvestigationPlanLlmResult(
            raw_llm=None,
            proposal=None,
            attempted=True,
            timed_out=True,
            provider_label="reasoning-test",
            dropped_reasons=["llm_timed_out"],
            latency_ms=120000,
            circuit_state="closed",
        ),
    )
    state = maybe_attach_validated_investigation_plan(
        {
            "request": type("Request", (), {"message": RQC["normalized_goal"]})(),
            "resolved_query_contract": RQC,
            "capability_snapshot": SNAPSHOT,
            "canonical_planning_outcome": {"status": "awaiting_investigation_plan"},
        }
    )
    plan = state["validated_investigation_plan"]
    assert plan["validation_status"] == "validated"
    assert plan["plan_source"] == "llm_failed_baseline_only"
    assert state["investigation_planning_trace"]["timed_out"] is True
    assert "resource_plan" not in state
    assert "evidence_plan" not in state
    assert "execution" not in state


def test_t4_flag_does_not_enable_investigation_planner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_investigation_planner_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)
    state = maybe_attach_validated_investigation_plan(
        {"resolved_query_contract": RQC, "capability_snapshot": SNAPSHOT}
    )
    assert "validated_investigation_plan" not in state


def test_langgraph_state_declares_p3_channels() -> None:
    annotations = ChatPipelineState.__annotations__
    assert "investigation_plan_proposal" in annotations
    assert "validated_investigation_plan" in annotations
    assert "investigation_planning_trace" in annotations


def test_shared_canonical_wait_state_attaches_validated_plan_without_resource_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_all_handoffs_for_tests()
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_investigation_plan_before_resource_plan_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_capability_snapshot_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_guided_composable_planning_enabled", True)
    monkeypatch.setattr(
        "app.chat.investigation_plan_runtime.propose_investigation_plan_llm",
        lambda **_kwargs: InvestigationPlanLlmResult(
            raw_llm=None,
            proposal=None,
            attempted=False,
            timed_out=False,
            provider_label=None,
            dropped_reasons=["llm_not_configured"],
            circuit_state="closed",
        ),
    )
    query = (
        "Investigate failed login spike for user:alice host:APP-01 "
        "from 10.0.0.8 in the last 24 hours"
    )
    qu = understand_query(query)
    route, provenance = select_route_from_understanding(qu, query)
    state = graph_node_lane_and_canonical_planning(
        {
            "request": SimpleNamespace(message=query),
            "effective_query": query,
            "query_understanding": qu,
            "routed": {**route, "routing_provenance": provenance},
            "trace_id": "p3-trace",
            "session_id": "p3-session",
            "route_plan_shadow": {},
        }
    )
    assert state["canonical_planning_outcome"]["status"] == "awaiting_investigation_plan"
    assert state["validated_investigation_plan"]["validation_status"] == "validated"
    # The planner is grounded on the Final RQC + deterministic baseline inside the
    # labelled trust boundary (see the prompt test above); no evidence rows,
    # credentials or raw SPL cross it.
    assert state["investigation_planning_trace"]["case_data_sent_to_model"] is True
    assert state.get("evidence_plan") is None
    assert state.get("execution") is None
    assert state.get("mcp_evidence") in (None, [], {})


def test_langgraph_response_surfaces_validated_plan_without_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_all_handoffs_for_tests()
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_investigation_plan_before_resource_plan_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_capability_snapshot_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_guided_composable_planning_enabled", True)
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", True)
    monkeypatch.setattr(
        "app.chat.investigation_plan_runtime.propose_investigation_plan_llm",
        lambda **_kwargs: InvestigationPlanLlmResult(
            raw_llm=None,
            proposal=None,
            attempted=False,
            timed_out=False,
            provider_label=None,
            dropped_reasons=["llm_not_configured"],
            circuit_state="closed",
        ),
    )
    response = run_chat_via_resource_planner_graph(
        ChatRequest(
            message=(
                "Investigate failed login spike for user:alice host:APP-01 "
                "from 10.0.0.8 in the last 24 hours"
            )
        )
    )
    assert response.planning_outcome is not None
    assert response.planning_outcome.status == "awaiting_investigation_plan"
    assert response.validated_investigation_plan is not None
    assert response.validated_investigation_plan["validation_status"] == "validated"
    assert response.evidence_plan is None
    assert response.execution is not None
    assert response.execution.status == "skipped"
    assert response.execution.execution_intent == "none"
    assert response.execution.selected_mcp_server is None
    assert response.execution.selected_mcp_tool is None
    assert response.planning_outcome.user_message == "Investigation plan is ready for analyst review."
