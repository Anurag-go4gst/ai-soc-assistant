"""Plan 5 C0.2 — the per-run lifecycle contract is immutable and fails closed."""

from __future__ import annotations

import dataclasses

import pytest

from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.planner.phase_contract import (
    PhaseContractViolation,
    build_phase_contract,
    resolve_and_freeze,
)
from app.planner.phase_policy import PhasePolicyInputs, resolve_phase_policy
from app.planner.resource_plan import PlanStep, ResourcePlan


def _contract(**overrides) -> ResolvedQueryContract:
    payload = {
        "normalized_goal": "test goal",
        "intent_family": "live_investigation",
        "answer_goal": "live_results",
        "ambiguity_state": "unambiguous",
        "qualification_tier": "T1",
        "qualification_source": "exact_105",
        "required_capabilities": {"spl", "mcp"},
    }
    payload.update(overrides)
    return ResolvedQueryContract(**payload)


def _plan(*purposes: str) -> ResourcePlan:
    return ResourcePlan(
        steps=[
            PlanStep(step_id=f"s{i}", resource_id=f"r{i}", purpose=p)
            for i, p in enumerate(purposes)
        ]
    )


def _spl_mcp_contract():
    return resolve_and_freeze(_contract(), _plan("spl_artifact", "mcp_execution"))


# --- immutability -------------------------------------------------------------


def test_contract_is_frozen() -> None:
    contract = _spl_mcp_contract()
    with pytest.raises(dataclasses.FrozenInstanceError):
        contract.phases = ()  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        contract.phases[0].mandatory = False  # type: ignore[misc]


def test_contract_exposes_no_mutation_api() -> None:
    """The planner and the specialists have no method to edit the lifecycle."""
    contract = _spl_mcp_contract()
    for forbidden in ("add_phase", "remove_phase", "reorder", "downgrade", "pop", "extend"):
        assert not hasattr(contract, forbidden)


def test_specialist_work_bundle_merge_cannot_reach_the_contract() -> None:
    """A WorkBundle merge enriches step arguments; it holds no lifecycle handle."""
    from pathlib import Path

    from app.planner import planner_hierarchy

    source = Path(planner_hierarchy.__file__).read_text(encoding="utf-8")
    assert "WorkBundle" in source, "anchor moved — re-point this pin"
    assert "phase_contract" not in source
    assert "PhaseContract" not in source


# --- fail-closed enforcement --------------------------------------------------


def test_schedule_missing_a_mandatory_phase_is_rejected() -> None:
    contract = _spl_mcp_contract()
    with pytest.raises(PhaseContractViolation) as excinfo:
        contract.validate_schedule(["workflow_spl", "spl_source_resolve", "execution"])
    assert "spl_postprocessor" in str(excinfo.value)


def test_schedule_reordering_a_contracted_phase_raises_rather_than_reorders() -> None:
    contract = _spl_mcp_contract()
    with pytest.raises(PhaseContractViolation):
        contract.validate_schedule(
            ["workflow_spl", "spl_source_resolve", "execution", "spl_postprocessor"]
        )


def test_valid_schedule_passes() -> None:
    contract = _spl_mcp_contract()
    contract.validate_schedule(
        ["workflow_spl", "spl_postprocessor", "spl_source_resolve", "execution"]
    )


def test_phase_policy_found_inapplicable_is_absent_not_a_no_op() -> None:
    """A knowledge-only turn must not carry an SPL chain, even as empty stages."""
    contract = resolve_and_freeze(
        _contract(
            required_capabilities=set(),
            intent_family="knowledge_only",
            answer_goal="policy_citation",
        ),
        _plan("knowledge_retrieval"),
    )
    assert "workflow_spl" not in contract.names
    with pytest.raises(PhaseContractViolation):
        contract.validate_schedule(["prepare_rag_only", "rag_early", "workflow_spl"])


def test_inline_mandatory_phases_are_named_not_silently_dropped() -> None:
    """`mitre_finalize` has no hook, so absence from a schedule must not read as absence from the run."""
    contract = resolve_and_freeze(
        _contract(required_capabilities=set(), answer_goal="mitre_mapping"),
        None,
    )
    assert "mitre_finalize" in contract.mandatory_names
    assert "mitre_finalize" in contract.inline_mandatory
    assert "mitre_finalize" not in contract.hook_bound_mandatory


# --- shape and observability ---------------------------------------------------


def test_contract_is_deterministic_and_registry_ordered() -> None:
    first = _spl_mcp_contract()
    second = _spl_mcp_contract()
    assert first == second
    assert [p.name for p in first.phases] == [
        name
        for name in __import__(
            "app.planner.phase_registry", fromlist=["PHASE_REGISTRY"]
        ).PHASE_REGISTRY
        if name in first.names
    ]


def test_trace_payload_is_redacted_and_carries_no_authority() -> None:
    payload = _spl_mcp_contract().trace_payload()
    assert payload["schema_version"] == "phase_contract_v1"
    assert {"name", "mandatory", "removable", "hook", "reason"} == set(payload["phases"][0])
    flat = repr(payload)
    for leak in ("execution_eligible", "token", "spl", "index="):
        if leak == "spl":
            continue  # phase names legitimately contain "spl"
        assert leak not in flat
    assert all(phase["removable"] is False for phase in payload["phases"])


def test_no_phase_in_any_contract_is_planner_removable() -> None:
    for inputs in (PhasePolicyInputs(), PhasePolicyInputs(pre_spl_discovery_enabled=True)):
        contract = build_phase_contract(
            resolve_phase_policy(_contract(), _plan("spl_artifact", "mcp_execution"), inputs)
        )
        assert all(phase.removable is False for phase in contract.phases)
