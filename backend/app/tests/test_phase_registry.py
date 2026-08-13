"""Plan 5 C0 — the closed lifecycle-phase catalog and the surfaces it unifies.

Written failing-first against the measured disagreement recorded in
`docs/evals/plan5/c0_phase_surface_disagreement.md`: three surfaces, twelve
phases, no two agreeing, with `mitre_finalize`/`cve_adapter` scheduled by a
surface that cannot run them and executed inline where no schedule can see them.

These tests introspect the live objects rather than restating them, so a surface
that drifts breaks here instead of at a phase-ordering bug in production.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from app.chat.contracts.pipeline_dispatch import PipelineStage
from app.planner.phase_registry import (
    PHASE_NAMES,
    PHASE_REGISTRY,
    PhaseOrderViolation,
    UnknownPhaseError,
    mandatory_phases,
    ordering_constraints,
    phase_for_hook,
    phase_for_stage,
    phase_spec,
    phases_without_hook_owner,
    validate_schedule_order,
)

APP = Path(__file__).resolve().parents[1]


def _hook_by_name_keys() -> set[str]:
    tree = ast.parse((APP / "planner" / "executor.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            getattr(target, "id", "") == "_HOOK_BY_NAME" for target in node.targets
        ):
            return {key.value for key in node.value.keys}
    raise AssertionError("_HOOK_BY_NAME not found in planner/executor.py")


def _fallback_hook_node_keys() -> set[str]:
    source = (APP / "chat" / "pipeline.py").read_text(encoding="utf-8")
    match = re.search(r"hook_nodes = \{(.*?)\}", source, re.S)
    assert match, "fallback hook_nodes literal not found in chat/pipeline.py"
    return set(re.findall(r'"([a-z_]+)":', match.group(1)))


# --- the catalog is closed ----------------------------------------------------


def test_unknown_phase_name_is_rejected() -> None:
    with pytest.raises(UnknownPhaseError):
        phase_spec("summarize_everything")
    with pytest.raises(UnknownPhaseError):
        phase_for_hook("summarize_everything")


def test_every_spec_is_self_consistent() -> None:
    for name, spec in PHASE_REGISTRY.items():
        assert spec.name == name
        assert spec.executed_by, f"{name}: no execution anchor"
        assert spec.applicability_input, f"{name}: no applicability input named"
        for earlier in spec.after:
            assert earlier in PHASE_NAMES, f"{name}: unknown predecessor {earlier}"


def test_no_governed_phase_is_planner_removable() -> None:
    """PhasePolicy owns lifecycle; the planner proposes work, never lifecycle."""
    removable = {name for name, spec in PHASE_REGISTRY.items() if spec.planner_removable}
    assert removable == set()


# --- the three surfaces resolve identically -----------------------------------


def test_every_hook_name_in_both_loops_resolves_to_one_phase() -> None:
    for hook in _hook_by_name_keys() | _fallback_hook_node_keys():
        assert phase_for_hook(hook).hook_name == hook


def test_every_pipeline_stage_resolves_to_one_phase() -> None:
    for stage in PipelineStage:
        assert phase_for_stage(stage).stage is stage


def test_the_execution_naming_collision_resolves_to_a_single_phase() -> None:
    """`mcp_execution` (stage vocabulary) and `execution` (hook vocabulary) are one phase."""
    assert phase_for_stage(PipelineStage.mcp_execution) is phase_for_hook("execution")
    assert phase_for_hook("execution").terminal is True


def test_registry_covers_the_union_of_all_three_surfaces() -> None:
    surfaces = (
        {stage.value for stage in PipelineStage}
        | _hook_by_name_keys()
        | _fallback_hook_node_keys()
    )
    # `mcp_execution` is the stage alias of `execution`; every other name is canonical.
    canonical = {name for name in surfaces if name != "mcp_execution"}
    assert canonical <= PHASE_NAMES, sorted(canonical - PHASE_NAMES)


def test_the_measured_surface_gaps_are_declared_not_accidental() -> None:
    """The disagreement is recorded as data, so closing or widening it is visible."""
    hook_loop = _hook_by_name_keys()
    fallback = _fallback_hook_node_keys()

    # mitre_finalize / cve_adapter are scheduled as stages but run by neither loop.
    assert phases_without_hook_owner() == {
        "mitre_finalize",
        "cve_adapter",
        "pre_spl_mcp_discovery",
    }
    for orphan in ("mitre_finalize", "cve_adapter", "pre_spl_mcp_discovery"):
        assert orphan not in hook_loop and orphan not in fallback
        assert phase_spec(orphan).owner in {"pipeline_inline", "dispatch_v2_inline"}

    # ensure_workflow_plan exists in the executor loop only — the fallback cannot
    # supply the workflow-plan stub. Recorded, not silently fixed.
    assert "ensure_workflow_plan" in hook_loop
    assert "ensure_workflow_plan" not in fallback


# --- ordering is declarative and asserted at runtime --------------------------


def test_spl_chain_order_is_expressed_as_registry_constraints() -> None:
    """`_SPL_CHAIN` list order becomes a checkable constraint, not a coincidence."""
    pairs = set(ordering_constraints())
    assert ("workflow_spl", "spl_postprocessor") in pairs
    assert ("workflow_spl", "spl_source_resolve") in pairs


def test_spl_validation_must_precede_the_execution_gate() -> None:
    pairs = set(ordering_constraints())
    assert ("spl_postprocessor", "execution") in pairs
    assert ("spl_source_resolve", "execution") in pairs


def test_valid_schedule_passes_and_reversed_schedule_raises() -> None:
    validate_schedule_order(
        ["workflow_spl", "rag_early", "spl_postprocessor", "spl_source_resolve", "execution"]
    )
    with pytest.raises(PhaseOrderViolation):
        validate_schedule_order(["execution", "workflow_spl", "spl_postprocessor"])
    with pytest.raises(PhaseOrderViolation):
        validate_schedule_order(["spl_postprocessor", "workflow_spl"])


def test_a_schedule_omitting_a_nonapplicable_phase_is_not_an_order_violation() -> None:
    """Lifecycle phases are mandatory *when applicable*, never universally inserted."""
    validate_schedule_order(["prepare_rag_only", "rag_early"])


def test_live_schedule_producers_satisfy_the_registry_order() -> None:
    """The schedules production actually emits must obey the declared constraints."""
    from app.planner.resource_plan_execution_scheduler import _compile_hooks

    for has_rag in (True, False):
        for has_spl in (True, False):
            for has_mcp in (True, False):
                hooks = _compile_hooks(
                    has_rag=has_rag,
                    has_spl=has_spl,
                    has_mcp=has_mcp,
                    spl_blocked=False,
                    has_workflow_plan=False,
                )
                validate_schedule_order(hooks)


def test_mandatory_set_is_every_phase_except_bounded_discovery() -> None:
    assert mandatory_phases() == PHASE_NAMES - {"pre_spl_mcp_discovery"}


def test_registry_holds_no_run_state() -> None:
    """Catalog only: no settings read, no state read, no I/O — asserted on code, not prose."""
    tree = ast.parse((APP / "planner" / "phase_registry.py").read_text(encoding="utf-8"))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert not {m for m in imported if m.startswith(("app.config", "httpx", "requests"))}

    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "open" not in called
    assert not any(
        isinstance(node, ast.Name) and node.id == "settings" for node in ast.walk(tree)
    )
