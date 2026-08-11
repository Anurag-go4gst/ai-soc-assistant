"""Plan 2 C1-E3 — typed step output→input handoffs and bounded gap re-planning.

Execution order only matters if downstream inputs are explicit, typed, and
validated. This pins the five real handoffs, their missing/empty outcomes, and
the C0-carried refinement requirement: a second guided round is valid only when
newly collected evidence actually changes the unresolved-gap state.

Nothing here is wired into dispatch. That is C1-E4.
"""

from __future__ import annotations

import pytest

from app.planner.resource_plan import PlanStep, ResourcePlan
from app.planner.resource_plan_execution import build_execution_contract
from app.planner.resource_plan_execution_handoffs import (
    HANDOFFS,
    HandoffOutcome,
    UndeclaredHandoffKey,
    evaluate_handoffs,
    evaluate_unresolved_gaps,
    handoff_by_name,
    read_handoff_value,
    refinement_decision,
)


def _step(step_id: str, purpose: str, **kwargs) -> PlanStep:
    return PlanStep(step_id=step_id, resource_id=f"resource:{purpose}", purpose=purpose, **kwargs)


# --- declaration discipline ---------------------------------------------------


def test_every_handoff_key_root_is_a_declared_state_channel() -> None:
    from app.graph.resource_planner_graph import ResourcePlannerGraphState

    channels = set(ResourcePlannerGraphState.__annotations__)
    for spec in HANDOFFS:
        assert spec.state_key.split(".")[0] in channels, spec.name


def test_the_five_real_handoffs_are_declared() -> None:
    assert {spec.name for spec in HANDOFFS} == {
        "rag_to_spl_slot_fill",
        "pre_spl_discovery_to_spl",
        "spl_candidate_to_source_resolve",
        "source_resolve_to_validation",
        "approved_spl_to_mcp_gate",
        "evidence_to_finalization",
    }


def test_reading_an_undeclared_key_is_refused() -> None:
    """No arbitrary state-key interpolation."""
    with pytest.raises(UndeclaredHandoffKey):
        read_handoff_value({"anything": 1}, "anything")


def test_declared_nested_key_reads_without_interpolation() -> None:
    state = {"spl_validation": {"normalized_spl": "index=main | head 10", "approved": True}}
    assert read_handoff_value(state, "spl_validation.normalized_spl") == "index=main | head 10"


# --- per-handoff outcomes -----------------------------------------------------


def test_missing_required_input_blocks_its_consumer() -> None:
    result = evaluate_handoffs({})["approved_spl_to_mcp_gate"]
    assert result.outcome == HandoffOutcome.BLOCKED
    assert result.reason == "missing_approved_normalized_spl"


def test_candidate_spl_alone_never_satisfies_the_mcp_gate_handoff() -> None:
    state = {
        "candidate_spl": {"spl": "index=main | head 10"},
        "spl_validation": {"approved": False, "normalized_spl": None},
    }
    result = evaluate_handoffs(state)["approved_spl_to_mcp_gate"]
    assert result.outcome == HandoffOutcome.BLOCKED
    assert result.value is None


def test_unapproved_validation_with_a_normalized_spl_still_blocks_the_gate() -> None:
    state = {"spl_validation": {"approved": False, "normalized_spl": "index=main | head 10"}}
    assert evaluate_handoffs(state)["approved_spl_to_mcp_gate"].outcome == HandoffOutcome.BLOCKED


def test_approved_normalized_spl_satisfies_the_gate_handoff() -> None:
    state = {"spl_validation": {"approved": True, "normalized_spl": "index=main | head 10"}}
    result = evaluate_handoffs(state)["approved_spl_to_mcp_gate"]
    assert result.outcome == HandoffOutcome.SATISFIED
    assert result.value == "index=main | head 10"


def test_empty_rag_is_an_optional_skip_not_a_block() -> None:
    result = evaluate_handoffs({"soc_kb_retrieval": {"documents": []}})["rag_to_spl_slot_fill"]
    assert result.outcome == HandoffOutcome.SKIPPED
    assert result.reason == "empty_soc_kb_retrieval"


def test_failed_pre_spl_discovery_is_an_optional_skip() -> None:
    state = {"pipeline_dispatch": {"runtime_context": {}}}
    result = evaluate_handoffs(state)["pre_spl_discovery_to_spl"]
    assert result.outcome == HandoffOutcome.SKIPPED


def test_present_pre_spl_discovery_is_satisfied_and_kept_distinct_from_legacy() -> None:
    state = {
        "pipeline_dispatch": {
            "runtime_context": {
                "mcp_discovery_context": {
                    "indexes": ["main"],
                    "populated_at_stage": "pre_spl_mcp_discovery",
                }
            }
        }
    }
    result = evaluate_handoffs(state)["pre_spl_discovery_to_spl"]
    assert result.outcome == HandoffOutcome.SATISFIED
    assert result.value["populated_at_stage"] == "pre_spl_mcp_discovery"
    assert handoff_by_name("pre_spl_discovery_to_spl").producer_stage == "pre_spl_mcp_discovery"


def test_missing_candidate_spl_falls_back_rather_than_blocking() -> None:
    result = evaluate_handoffs({})["spl_candidate_to_source_resolve"]
    assert result.outcome == HandoffOutcome.FALLBACK


def test_wrong_type_is_refused_rather_than_coerced() -> None:
    result = evaluate_handoffs({"spl_validation": "approved!"})["source_resolve_to_validation"]
    assert result.outcome == HandoffOutcome.BLOCKED
    assert result.reason == "wrong_type_spl_validation"


def test_evidence_to_finalization_is_satisfied_by_any_evidence() -> None:
    state = {"source_evidence": [{"source_id": "kb:1"}]}
    assert evaluate_handoffs(state)["evidence_to_finalization"].outcome == HandoffOutcome.SATISFIED


def test_empty_evidence_finalizes_with_a_declared_limitation() -> None:
    result = evaluate_handoffs({"source_evidence": []})["evidence_to_finalization"]
    assert result.outcome == HandoffOutcome.SKIPPED
    assert result.reason == "empty_source_evidence"


def test_no_handoff_ever_carries_a_prompt_or_credential_key() -> None:
    for spec in HANDOFFS:
        lowered = spec.state_key.lower()
        for forbidden in ("prompt", "completion", "token", "secret", "credential", "api_key"):
            assert forbidden not in lowered, spec.name


# --- unresolved evidence gaps (round-varying input) --------------------------


def _guided_plan() -> ResourcePlan:
    return ResourcePlan(
        steps=[
            _step("rag", "knowledge_retrieval"),
            _step("spl", "spl_artifact"),
            _step("mcp", "mcp_execution"),
        ]
    )


def test_unresolved_gaps_are_derived_from_produced_evidence_keys() -> None:
    contract = build_execution_contract(_guided_plan())
    assert evaluate_unresolved_gaps(contract, produced_keys=set()) == [
        "soc_kb_retrieval",
        "candidate_spl",
        "spl_validation",
        "execution",
    ]
    assert evaluate_unresolved_gaps(contract, produced_keys={"soc_kb_retrieval"}) == [
        "candidate_spl",
        "spl_validation",
        "execution",
    ]


def test_blocked_step_outputs_are_not_counted_as_reachable_gaps() -> None:
    plan = ResourcePlan(
        steps=[
            _step("rag", "knowledge_retrieval"),
            _step("mcp", "mcp_execution", status="blocked_policy", status_reason="skill_contract"),
        ]
    )
    contract = build_execution_contract(plan)
    assert evaluate_unresolved_gaps(contract, produced_keys=set()) == ["soc_kb_retrieval"]


# --- bounded refinement (C0 carried-in requirement) --------------------------


def test_idempotent_collection_does_not_authorize_another_round() -> None:
    """Round N+1 with identical inputs is a no-op; a heuristic must not fake one."""
    contract = build_execution_contract(_guided_plan())
    decision = refinement_decision(
        contract,
        previous_produced_keys={"soc_kb_retrieval"},
        current_produced_keys={"soc_kb_retrieval"},
        rounds_used=1,
        max_rounds=3,
    )
    assert decision.refine is False
    assert decision.reason == "no_new_evidence"


def test_new_evidence_that_leaves_a_reachable_gap_authorizes_one_more_round() -> None:
    contract = build_execution_contract(_guided_plan())
    decision = refinement_decision(
        contract,
        previous_produced_keys=set(),
        current_produced_keys={"soc_kb_retrieval"},
        rounds_used=1,
        max_rounds=3,
    )
    assert decision.refine is True
    assert decision.unresolved_gaps == ["candidate_spl", "spl_validation", "execution"]


def test_new_evidence_that_closes_every_gap_stops() -> None:
    contract = build_execution_contract(_guided_plan())
    decision = refinement_decision(
        contract,
        previous_produced_keys={"soc_kb_retrieval"},
        current_produced_keys={"soc_kb_retrieval", "candidate_spl", "spl_validation", "execution"},
        rounds_used=1,
        max_rounds=3,
    )
    assert decision.refine is False
    assert decision.reason == "evidence_satisfied"


def test_round_bound_is_hard() -> None:
    contract = build_execution_contract(_guided_plan())
    decision = refinement_decision(
        contract,
        previous_produced_keys=set(),
        current_produced_keys={"soc_kb_retrieval"},
        rounds_used=3,
        max_rounds=3,
    )
    assert decision.refine is False
    assert decision.reason == "round_bound_reached"


def test_refinement_never_consults_a_count_heuristic() -> None:
    import ast
    import inspect

    from app.planner import resource_plan_execution_handoffs

    source = inspect.getsource(resource_plan_execution_handoffs)
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    for forbidden in ("app.config", "app.connectors", "app.mcp", "app.llm", "httpx", "requests"):
        assert not any(name.startswith(forbidden) for name in imported), forbidden
    assert "collected_count" not in source
    # No retired planning-model rail may return through this door.
    for retired in ("propose_investigation_plan_llm", "run_resource_plan_shadow", "llm_plan_bridge"):
        assert retired not in source, retired
