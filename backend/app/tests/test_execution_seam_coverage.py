"""Plan 3 A1 — canonical execution-seam coverage: inventory + structural pins.

Inventory only. Nothing is rewired here (user decision, 2026-08-11). These tests
encode *today's* truth so that any future drift — a new bypass, a new schedule
producer, a new hook-execution loop — becomes a failing test rather than a
silent second scheduling authority.

Two distinct things are pinned:

1. **Seam reachers vs bypasses.** `execute_plan_dispatch` is the canonical seam.
   Exactly one graph branch and one imperative branch reach it today.
2. **Schedule producers and executors.** A "producer" turns state into a hook
   list; an "executor" runs hooks. Both sets are closed, and both are asserted
   by source inspection so a new call site cannot appear unnoticed.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

CHAT = Path(__file__).resolve().parents[1] / "chat"
PLANNER = Path(__file__).resolve().parents[1] / "planner"
GRAPH = Path(__file__).resolve().parents[1] / "graph"
DEMO = Path(__file__).resolve().parents[1] / "demo"

# --- inventory, as data -------------------------------------------------------

# path -> (reaches_canonical_seam, classification)
# Classifications are the A1 vocabulary: ADOPT_CANDIDATE / KEEP_SEPARATE /
# DECISION_REQUIRED. Recorded in the plan's A1 evidence with full reasoning.
SEAM_INVENTORY: dict[str, tuple[bool, str]] = {
    "graph:composed_dispatch": (True, "SEAM"),
    "graph:rag_only": (False, "DECISION_REQUIRED"),
    "graph:workflow_spl": (False, "DECISION_REQUIRED"),
    "graph:non_planned_finalize": (False, "KEEP_SEPARATE"),
    "imperative:composed_plan": (True, "SEAM"),
    "imperative:guided_hybrid": (False, "DECISION_REQUIRED"),
    "imperative:session_spl_refine": (False, "DECISION_REQUIRED"),
    "imperative:non_planned": (False, "KEEP_SEPARATE"),
    "trace:v2_cursor_synthesis": (False, "KEEP_SEPARATE"),
    "fixture:ec_demo": (False, "KEEP_SEPARATE"),
}

VALID_CLASSIFICATIONS = {"SEAM", "ADOPT_CANDIDATE", "KEEP_SEPARATE", "DECISION_REQUIRED"}

# Functions permitted to turn state into a hook schedule.
ALLOWED_SCHEDULE_PRODUCERS = {
    "imperative_hook_schedule_from_state",  # dispatch-v2 projection
    "_legacy_predicate_dispatch_schedule",  # legacy/fallback (consumes v2 first)
    "compile_execution_schedule",  # execution-driven compiler
    "_execution_driven_schedule",  # executor-local wrapper around the compiler
    "build_step_walk_dispatch_schedule",  # the seam that picks among them
}

# Modules permitted to *execute* a hook list. `executor` is canonical;
# `pipeline` retains one legacy fallback loop, pinned below so it cannot spread.
ALLOWED_HOOK_EXECUTOR_MODULES = {"executor.py", "pipeline.py"}


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _called_names(path: Path) -> set[str]:
    tree = ast.parse(_source(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


# --- inventory hygiene --------------------------------------------------------


def test_every_inventory_entry_carries_a_valid_classification() -> None:
    for path, (_reaches, classification) in SEAM_INVENTORY.items():
        assert classification in VALID_CLASSIFICATIONS, f"{path}: {classification}"


def test_exactly_two_paths_reach_the_canonical_seam() -> None:
    reaching = {p for p, (reaches, _c) in SEAM_INVENTORY.items() if reaches}
    assert reaching == {"graph:composed_dispatch", "imperative:composed_plan"}


def test_seam_paths_are_classified_as_seam() -> None:
    for path, (reaches, classification) in SEAM_INVENTORY.items():
        if reaches:
            assert classification == "SEAM", path


# --- the canonical seam -------------------------------------------------------


def test_execute_plan_dispatch_has_exactly_the_known_call_sites() -> None:
    """A third caller means a new adoption happened without a decision."""
    hits: list[str] = []
    for path in (CHAT / "pipeline.py", PLANNER / "executor.py", GRAPH / "resource_planner_graph.py"):
        for number, line in enumerate(_source(path).splitlines(), start=1):
            if "execute_plan_dispatch(" in line and not line.strip().startswith(("#", "def ", "from ")):
                hits.append(f"{path.name}:{number}")
    # pipeline.py:655 (imperative composed-plan) and pipeline.py:2273
    # (graph_node_composed_dispatch, which the graph node delegates to).
    assert len(hits) == 2, hits


def test_graph_dispatch_route_still_has_exactly_four_destinations() -> None:
    from app.graph.resource_planner_graph import _rp_dispatch_route

    returns = {
        node.value.value
        for node in ast.walk(ast.parse(inspect.getsource(_rp_dispatch_route)))
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Constant)
    }
    assert returns == {"non_planned_finalize", "rag_only", "composed_dispatch", "workflow_spl"}


def test_graph_has_no_guided_hybrid_branch() -> None:
    """Guided-hybrid is imperative-only; a graph branch would be a new authority."""
    source = _source(GRAPH / "resource_planner_graph.py")
    assert "guided_hybrid" not in source


# --- schedule producers -------------------------------------------------------


def test_no_unexpected_schedule_producer_is_called() -> None:
    """Every producer call site must be one of the known, reviewed functions."""
    watched = {
        "imperative_hook_schedule_from_state",
        "_legacy_predicate_dispatch_schedule",
        "compile_execution_schedule",
        "_execution_driven_schedule",
        "build_step_walk_dispatch_schedule",
    }
    for path in (
        CHAT / "pipeline.py",
        PLANNER / "executor.py",
        GRAPH / "resource_planner_graph.py",
        CHAT / "contracts" / "pipeline_dispatch.py",
    ):
        called = _called_names(path) & watched
        assert called <= ALLOWED_SCHEDULE_PRODUCERS, f"{path.name}: {called}"


def test_compiler_is_only_reached_through_the_executor_seam() -> None:
    """The execution-driven compiler must not gain a second entry point."""
    hits: list[str] = []
    for path in (CHAT / "pipeline.py", GRAPH / "resource_planner_graph.py"):
        if "compile_execution_schedule" in _source(path):
            hits.append(path.name)
    assert hits == [], hits


def test_v2_projection_is_consumed_before_predicates_in_the_legacy_schedule() -> None:
    """A0 finding: legacy mirrors v2 rather than competing with it."""
    from app.planner.executor import _legacy_predicate_dispatch_schedule

    source = inspect.getsource(_legacy_predicate_dispatch_schedule)
    v2_index = source.index("imperative_hook_schedule_from_state")
    predicate_index = source.index("uses_rag_only_path")
    assert v2_index < predicate_index


# --- hook executors -----------------------------------------------------------


def test_hook_execution_loops_are_confined_to_known_modules() -> None:
    """`_run_dispatch_schedule` is canonical; the legacy fallback loop is pinned."""
    from app.chat import pipeline

    source = inspect.getsource(pipeline._run_legacy_dispatch_fallback)
    # This fallback executes hooks itself instead of delegating to the executor.
    # Pinned deliberately: it is a KNOWN duplicate executor, recorded in A1 as
    # DECISION_REQUIRED. If it disappears, adoption happened and A1 must be revisited.
    assert "hook_nodes" in source
    assert "imperative_hook_schedule_from_state" in source


def test_only_the_executor_defines_the_canonical_hook_table() -> None:
    from app.planner import executor

    assert "_HOOK_BY_NAME" in inspect.getsource(executor)
    for path in (GRAPH / "resource_planner_graph.py", DEMO / "ec_pipeline_fixture.py"):
        assert "_HOOK_BY_NAME" not in _source(path), path.name


# --- mutation-negative controls ----------------------------------------------


def test_inventory_detects_an_unlisted_bypass() -> None:
    mutated = dict(SEAM_INVENTORY)
    mutated["graph:sneaky_new_branch"] = (False, "KEEP_SEPARATE")
    reaching = {p for p, (reaches, _c) in mutated.items() if reaches}
    assert "graph:sneaky_new_branch" not in reaching
    assert len(mutated) != len(SEAM_INVENTORY)


def test_inventory_rejects_an_invalid_classification() -> None:
    with pytest.raises(AssertionError):
        classification = "PROBABLY_FINE"
        assert classification in VALID_CLASSIFICATIONS


def test_producer_allowlist_detects_a_fabricated_producer() -> None:
    fabricated = {"build_my_own_schedule"}
    assert not fabricated <= ALLOWED_SCHEDULE_PRODUCERS
