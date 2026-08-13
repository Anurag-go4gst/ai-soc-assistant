"""Plan 5 C3 — what the second execution engine owes vs what it runs.

Proof only. `_run_legacy_dispatch_fallback` is **not** retired and no seam is
adopted; these pins keep the equivalence evidence in
`docs/evals/plan5/c3_fallback_equivalence.md` from rotting.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.planner.phase_contract import resolve_and_freeze
from app.planner.resource_plan import PlanStep, ResourcePlan

CHAT = Path(__file__).resolve().parents[1] / "chat"


def _fallback_source() -> str:
    from app.chat import pipeline

    return inspect.getsource(pipeline._run_legacy_dispatch_fallback)


def _legacy_branch_hooks() -> list[str]:
    """Hook names the fallback appends to its own trace, in source order."""
    tree = ast.parse(_fallback_source().lstrip())
    appended: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "append"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            appended.append(node.args[0].value)
    return appended


def test_fallback_still_has_exactly_one_call_site() -> None:
    source = (CHAT / "pipeline.py").read_text(encoding="utf-8")
    hits = [
        number
        for number, line in enumerate(source.splitlines(), start=1)
        if "_run_legacy_dispatch_fallback(" in line and not line.strip().startswith("def ")
    ]
    assert len(hits) == 1, hits


def test_fallback_legacy_branch_runs_no_spl_postprocessor() -> None:
    """The measured non-equivalence: it owes the phase and never runs it."""
    hooks = _legacy_branch_hooks()
    assert "workflow_spl" in hooks
    assert "spl_source_resolve" in hooks
    assert "execution" in hooks
    # `spl_postprocessor` appears only inside the v2 hook table, never as a
    # literal the legacy branch appends after `workflow_spl`.
    tail = hooks[hooks.index("workflow_spl") :]
    assert "spl_postprocessor" not in tail


def test_fallback_owes_the_phase_the_contract_marks_mandatory() -> None:
    contract = ResolvedQueryContract(
        normalized_goal="session spl refine",
        intent_family="spl_generation_only",
        answer_goal="spl_artifact",
        ambiguity_state="unambiguous",
        qualification_tier="T1",
        qualification_source="session_pins",
        required_capabilities={"spl"},
    )
    plan = ResourcePlan(steps=[PlanStep(step_id="s1", resource_id="r1", purpose="spl_artifact")])
    phase_contract = resolve_and_freeze(contract, plan)
    assert "spl_postprocessor" in phase_contract.hook_bound_mandatory


def test_mcp_gate_still_refuses_unvalidated_spl() -> None:
    """Why the gap fails closed today: the gate, not the schedule, is the guard."""
    from app.orchestration import mcp_execution_gate

    source = inspect.getsource(mcp_execution_gate)
    assert 'spl_validation.get("approved") is not True' in source
    assert 'spl_validation.get("normalized_spl") is None' in source


def test_no_seam_was_adopted_by_plan_5() -> None:
    from app.tests.test_execution_seam_coverage import SEAM_INVENTORY

    classifications = [classification for _reaches, classification in SEAM_INVENTORY.values()]
    assert classifications.count("SEAM") == 2
    assert classifications.count("DECISION_REQUIRED") == 4
    assert classifications.count("KEEP_SEPARATE") == 4
    assert "ADOPT_CANDIDATE" not in classifications
