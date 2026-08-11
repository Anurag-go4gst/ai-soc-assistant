"""Plan 3 B0 — bounded guided refinement driven by real evidence/gap state.

Plan 2 built the mechanism (`refinement_decision` over produced-evidence keys)
but nothing reached it: the live loop gated on `InvestigationPlan.refinement_recommended`,
hardcoded `False` since the LLM proposer was retired, so guided investigation was
permanently one-round.

B0 wires the existing mechanism to the guided rail's real `validated_resource_plan`
and adds the one thing Plan 2's mechanism lacked: a **plan-fingerprint stop**, so a
round that would re-plan identically does not run at all.

No retired proposer. No `collected_count` heuristic. The round-varying input is the
set of evidence keys the collection actually produced.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.chat.guided_hybrid_refinement import (
    MAX_GUIDED_INVESTIGATION_ROUNDS,
    GuidedRefinementOutcome,
    evaluate_guided_refinement,
    guided_plan_fingerprint,
    produced_evidence_keys_from_state,
)
from app.planner.resource_plan import PlanStep, ResourcePlan
from app.planner.resource_plan_execution import build_execution_contract


def _plan(*steps: PlanStep) -> ResourcePlan:
    return ResourcePlan(steps=list(steps))


def _step(step_id: str, purpose: str, **kw: Any) -> PlanStep:
    return PlanStep(step_id=step_id, resource_id=f"resource:{purpose}", purpose=purpose, **kw)


def _guided_plan() -> ResourcePlan:
    return _plan(
        _step("rag", "knowledge_retrieval"),
        _step("discovery", "mcp_discovery"),
        _step("catalog", "safe_catalog_query"),
    )


def _contract(plan: ResourcePlan | None = None):
    return build_execution_contract(plan or _guided_plan())


# --- produced-key extraction --------------------------------------------------


def test_produced_keys_are_empty_before_any_collection() -> None:
    assert produced_evidence_keys_from_state(_contract(), {}) == set()


def test_produced_keys_reflect_populated_state_channels() -> None:
    state = {"mcp_evidence": [{"outcome": "collected"}], "soc_kb_retrieval": {"documents": [1]}}
    keys = produced_evidence_keys_from_state(_contract(), state)
    assert "mcp_evidence" in keys
    assert "soc_kb_retrieval" in keys


def test_empty_channel_does_not_count_as_produced() -> None:
    """Empty evidence must never buy a refinement round."""
    state = {"mcp_evidence": [], "soc_kb_retrieval": {}}
    assert produced_evidence_keys_from_state(_contract(), state) == set()


# --- plan fingerprint ---------------------------------------------------------


def test_fingerprint_is_stable_for_the_same_plan() -> None:
    assert guided_plan_fingerprint(_guided_plan()) == guided_plan_fingerprint(_guided_plan())


def test_fingerprint_changes_when_a_step_is_added() -> None:
    extended = _plan(*_guided_plan().steps, _step("extra", "knowledge_retrieval"))
    assert guided_plan_fingerprint(extended) != guided_plan_fingerprint(_guided_plan())


def test_fingerprint_ignores_none() -> None:
    assert guided_plan_fingerprint(None) == ""


# --- the refinement decision --------------------------------------------------


def _evaluate(**over: Any) -> GuidedRefinementOutcome:
    kwargs: dict[str, Any] = {
        "contract": _contract(),
        "previous_produced_keys": set(),
        "current_produced_keys": {"mcp_evidence"},
        "rounds_used": 0,
        "previous_fingerprint": "plan-a",
        "current_fingerprint": "plan-b",
    }
    kwargs.update(over)
    return evaluate_guided_refinement(**kwargs)


def test_new_evidence_with_an_open_gap_authorizes_another_round() -> None:
    outcome = _evaluate()
    assert outcome.refine is True
    assert outcome.reason == "new_evidence_with_open_gap"
    assert outcome.unresolved_gaps


def test_no_new_evidence_stops() -> None:
    outcome = _evaluate(previous_produced_keys={"mcp_evidence"}, current_produced_keys={"mcp_evidence"})
    assert outcome.refine is False
    assert outcome.reason == "no_new_evidence"


def test_evidence_satisfied_stops() -> None:
    outcome = _evaluate(current_produced_keys={"mcp_evidence", "soc_kb_retrieval"})
    assert outcome.refine is False
    assert outcome.reason == "evidence_satisfied"


def test_identical_plan_fingerprint_stops_even_with_new_evidence() -> None:
    """The B0 addition: a round that would re-plan identically is a no-op."""
    outcome = _evaluate(previous_fingerprint="same", current_fingerprint="same")
    assert outcome.refine is False
    assert outcome.reason == "plan_unchanged"


def test_round_cap_is_hard() -> None:
    outcome = _evaluate(rounds_used=MAX_GUIDED_INVESTIGATION_ROUNDS)
    assert outcome.refine is False
    assert outcome.reason == "round_bound_reached"


def test_cap_wins_over_every_other_signal() -> None:
    outcome = _evaluate(
        rounds_used=MAX_GUIDED_INVESTIGATION_ROUNDS + 5,
        previous_produced_keys=set(),
        current_produced_keys={"mcp_evidence"},
        previous_fingerprint="a",
        current_fingerprint="b",
    )
    assert outcome.refine is False
    assert outcome.reason == "round_bound_reached"


def test_absent_contract_stops() -> None:
    outcome = _evaluate(contract=None)
    assert outcome.refine is False
    assert outcome.reason == "no_execution_contract"


@pytest.mark.parametrize(
    "reason",
    [
        "new_evidence_with_open_gap",
        "no_new_evidence",
        "evidence_satisfied",
        "plan_unchanged",
        "round_bound_reached",
        "no_execution_contract",
    ],
)
def test_every_reason_is_a_declared_outcome(reason: str) -> None:
    from app.chat.guided_hybrid_refinement import GUIDED_REFINEMENT_REASONS

    assert reason in GUIDED_REFINEMENT_REASONS


# --- governance ---------------------------------------------------------------


def test_refinement_module_has_no_llm_or_count_heuristic() -> None:
    import ast
    import inspect

    from app.chat import guided_hybrid_refinement

    source = inspect.getsource(guided_hybrid_refinement)
    for retired in (
        "propose_investigation_plan_llm",
        "run_resource_plan_shadow",
        "llm_plan_bridge",
        "collected_count",
    ):
        assert retired not in source, retired

    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
        elif isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
    for forbidden in ("app.llm", "app.connectors", "app.mcp", "httpx", "requests"):
        assert not any(name.startswith(forbidden) for name in imported), forbidden


def test_live_loop_gates_on_evidence_not_on_the_retired_flag() -> None:
    """Pin the wiring: the loop must consult the evidence-driven decision."""
    import inspect

    from app.chat import pipeline

    source = inspect.getsource(pipeline._run_guided_hybrid_dispatch)
    assert "evaluate_guided_refinement" in source
    assert "guided_plan_fingerprint" in source
    # The dead gate must be gone from the loop's control flow.
    assert "should_run_refinement_pass" not in source
