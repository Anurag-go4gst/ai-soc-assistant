"""Plan 5 C0.1 — deterministic lifecycle applicability.

Table-driven over turn archetypes. The point of every case is the same: a phase
is mandatory **when it applies**, and never universally inserted into a turn
that has no use for it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.planner.phase_policy import (
    PhasePolicyInputs,
    resolve_phase_policy,
)
from app.planner.phase_registry import PHASE_REGISTRY
from app.planner.resource_plan import PlanStep, ResourcePlan

APP = Path(__file__).resolve().parents[1]


def _contract(**overrides) -> ResolvedQueryContract:
    payload = {
        "normalized_goal": "test goal",
        "intent_family": "live_investigation",
        "answer_goal": "live_results",
        "ambiguity_state": "unambiguous",
        "qualification_tier": "T1",
        "qualification_source": "exact_105",
    }
    payload.update(overrides)
    return ResolvedQueryContract(**payload)


def _plan(*purposes: str, blocked: tuple[str, ...] = ()) -> ResourcePlan:
    steps = [
        PlanStep(step_id=f"s{index}", resource_id=f"r{index}", purpose=purpose)
        for index, purpose in enumerate(purposes)
    ]
    steps.extend(
        PlanStep(
            step_id=f"b{index}",
            resource_id=f"rb{index}",
            purpose=purpose,
            status="blocked_policy",
        )
        for index, purpose in enumerate(blocked)
    )
    return ResourcePlan(steps=steps)


# --- turn archetypes ----------------------------------------------------------


def test_knowledge_only_turn_carries_no_spl_chain() -> None:
    resolution = resolve_phase_policy(
        _contract(intent_family="knowledge_only", answer_goal="policy_citation"),
        _plan("knowledge_retrieval"),
    )
    assert resolution.applicable == {"prepare_rag_only", "rag_early"}
    assert "workflow_spl" not in resolution.applicable
    assert "spl_postprocessor" not in resolution.applicable
    assert "execution" not in resolution.applicable


def test_spl_and_mcp_turn_carries_the_full_governed_chain() -> None:
    resolution = resolve_phase_policy(
        _contract(required_capabilities={"spl", "mcp"}),
        _plan("spl_artifact", "mcp_execution"),
    )
    assert {
        "workflow_spl",
        "spl_postprocessor",
        "spl_source_resolve",
        "execution",
    } <= resolution.applicable
    assert ("spl_postprocessor", "execution") in resolution.ordering
    assert ("workflow_spl", "spl_postprocessor") in resolution.ordering


def test_reference_id_turn_carries_reference_finalize_and_nothing_spl() -> None:
    resolution = resolve_phase_policy(
        _contract(
            intent_family="reference_knowledge",
            answer_goal="reference_lookup",
            qualification_tier="T0",
            qualification_source="reference_ids",
        ),
    )
    assert resolution.applicable == {"reference_finalize"}


def test_mitre_mapping_turn_carries_mitre_finalize() -> None:
    resolution = resolve_phase_policy(
        _contract(intent_family="mitre_knowledge", answer_goal="mitre_mapping"),
    )
    assert "mitre_finalize" in resolution.applicable
    assert "cve_adapter" not in resolution.applicable


def test_cve_turn_carries_the_cve_adapter_only_when_planned() -> None:
    without = resolve_phase_policy(_contract(), _plan("knowledge_retrieval"))
    assert "cve_adapter" not in without.applicable

    with_cve = resolve_phase_policy(_contract(), _plan("knowledge_retrieval", "cve_lookup"))
    assert "cve_adapter" in with_cve.applicable


def test_clarification_turn_carries_no_lifecycle_at_all() -> None:
    resolution = resolve_phase_policy(
        _contract(
            ambiguity_state="clarification_required",
            clarification_required=True,
            clarification_reason="missing alert context",
            answer_goal="clarification",
        ),
        _plan("spl_artifact", "mcp_execution"),
    )
    assert resolution.applicable == frozenset()
    assert resolution.mandatory == frozenset()
    assert resolution.ordering == ()


def test_pre_spl_discovery_is_applicable_only_when_the_caller_says_so() -> None:
    contract = _contract(required_capabilities={"spl"})
    off = resolve_phase_policy(contract, _plan("spl_artifact"))
    on = resolve_phase_policy(
        contract, _plan("spl_artifact"), PhasePolicyInputs(pre_spl_discovery_enabled=True)
    )
    assert "pre_spl_mcp_discovery" not in off.applicable
    assert "pre_spl_mcp_discovery" in on.applicable
    # Applicable, but the one phase that is not mandatory when applicable.
    assert "pre_spl_mcp_discovery" not in on.mandatory


def test_blocked_spl_without_workflow_plan_gets_the_stub_phase() -> None:
    resolution = resolve_phase_policy(
        _contract(), _plan("knowledge_retrieval", blocked=("spl_artifact",))
    )
    assert "ensure_workflow_plan" in resolution.applicable
    assert "workflow_spl" not in resolution.applicable

    with_plan = resolve_phase_policy(
        _contract(),
        _plan("knowledge_retrieval", blocked=("spl_artifact",)),
        PhasePolicyInputs(has_workflow_plan=True),
    )
    assert "ensure_workflow_plan" not in with_plan.applicable


def test_prohibited_capability_denies_the_phase_it_would_have_required() -> None:
    """A contract may deny a capability; denial removes the phase, not the safety."""
    resolution = resolve_phase_policy(
        _contract(prohibited_capabilities={"spl"}), _plan("spl_artifact")
    )
    assert "workflow_spl" not in resolution.applicable
    assert "spl_postprocessor" not in resolution.applicable


# --- properties ---------------------------------------------------------------


def test_every_applicable_mandatory_phase_is_marked_non_removable() -> None:
    resolution = resolve_phase_policy(
        _contract(required_capabilities={"spl", "mcp"}),
        _plan("spl_artifact", "mcp_execution", "knowledge_retrieval"),
    )
    for name in resolution.mandatory:
        assert PHASE_REGISTRY[name].planner_removable is False


def test_resolver_is_pure_and_repeatable() -> None:
    contract = _contract(required_capabilities={"spl"})
    plan = _plan("spl_artifact", "knowledge_retrieval")
    first = resolve_phase_policy(contract, plan)
    second = resolve_phase_policy(contract, plan)
    assert first == second


def test_resolver_reads_no_settings_and_performs_no_io() -> None:
    tree = ast.parse((APP / "planner" / "phase_policy.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert not {m for m in imported if m.startswith(("app.config", "httpx", "requests"))}
    assert not any(
        isinstance(node, ast.Name) and node.id in {"settings", "open"}
        for node in ast.walk(tree)
    )


def test_plan_content_can_only_add_a_phase_never_remove_one() -> None:
    """No ResourcePlan or advisory input can talk PhasePolicy out of a phase."""
    contract = _contract(required_capabilities={"spl"})
    bare = resolve_phase_policy(contract, None)
    with_plan = resolve_phase_policy(contract, _plan("knowledge_retrieval", "cve_lookup"))
    assert bare.applicable <= with_plan.applicable

    # Even a plan that blocks every SPL step cannot drop the SPL chain the
    # contract requires.
    blocked_everything = resolve_phase_policy(contract, _plan(blocked=("spl_artifact",)))
    assert {"workflow_spl", "spl_postprocessor"} <= blocked_everything.applicable


def test_unknown_phase_name_cannot_enter_a_resolution() -> None:
    resolution = resolve_phase_policy(_contract(), _plan("spl_artifact"))
    assert resolution.applicable <= set(PHASE_REGISTRY)


@pytest.mark.parametrize(
    "goal",
    ["live_results", "spl_artifact", "analyst_action_guidance", "severity_assessment"],
)
def test_no_answer_goal_universally_inserts_every_phase(goal: str) -> None:
    resolution = resolve_phase_policy(_contract(answer_goal=goal), None)
    assert resolution.applicable != set(PHASE_REGISTRY)
