"""Plan 5 C2 — the merge seam is wired at one place, behind the existing flag.

`AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` stays default false for all of Plan 5.
Flag-off must reach zero merge-seam code; flag-on must preserve the dispatch-v2
precedence and must stop dropping the lifecycle stage Plan 3 A0 measured.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.config import Settings, settings
from app.planner import executor
from app.planner.executor import DispatchHooks, build_step_walk_dispatch_schedule, walk_plan_steps


def _hooks() -> DispatchHooks:
    def node(_name: str):
        def run(state: dict[str, Any]) -> dict[str, Any]:
            return state

        return run

    return DispatchHooks(
        uses_rag_only_path=lambda _s: False,
        uses_pre_mcp_rag=lambda _s: False,
        prepare_rag_only=node("prepare_rag_only"),
        rag_early=node("rag_early"),
        spl_source_resolve=node("spl_source_resolve"),
        workflow_spl=node("workflow_spl"),
        spl_postprocessor=node("spl_postprocessor"),
        ensure_workflow_plan=node("ensure_workflow_plan"),
        reference_finalize=node("reference_finalize"),
        execution=node("execution"),
    )


def _contract_payload() -> dict[str, Any]:
    from app.chat.contracts.resolved_query import ResolvedQueryContract

    return ResolvedQueryContract(
        normalized_goal="spl and mcp turn",
        intent_family="live_investigation",
        answer_goal="live_results",
        ambiguity_state="unambiguous",
        qualification_tier="T1",
        qualification_source="exact_105",
        required_capabilities={"spl", "mcp"},
    ).model_dump(mode="json")


def _state(*, with_contract: bool = True) -> dict[str, Any]:
    state: dict[str, Any] = {
        "evidence_plan": {
            "resource_plan": {
                "steps": [
                    {
                        "step_id": "spl",
                        "resource_id": "spl_template:auth_failed_login_spike",
                        "purpose": "spl_artifact",
                    },
                    {
                        "step_id": "mcp",
                        "resource_id": "mcp_tool:splunk_run_query",
                        "purpose": "mcp_execution",
                    },
                ],
                "provenance": {"committed": True},
            }
        }
    }
    if with_contract:
        state["resolved_query_contract"] = _contract_payload()
    return state


# --- flag posture -------------------------------------------------------------


def test_flag_stays_default_false() -> None:
    assert Settings().ai_soc_resource_plan_execution_enabled is False


def test_flag_off_reaches_no_merge_seam_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", False)

    def _boom(*args: Any, **kwargs: Any):  # pragma: no cover - must not run
        raise AssertionError("merge seam reached while the flag is off")

    monkeypatch.setattr("app.planner.phase_schedule_merge.merge_schedule", _boom)
    monkeypatch.setattr("app.planner.phase_policy.resolve_phase_policy", _boom)

    state = _state()
    walk = walk_plan_steps(state)
    schedule = build_step_walk_dispatch_schedule(state, walk, _hooks())
    assert schedule  # the fixed predicate schedule still runs
    assert executor._execution_driven_schedule(state, walk) == (None, None)


def test_flag_off_trace_carries_no_phase_merge_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", False)
    state = _state()
    walk = walk_plan_steps(state)
    trace = executor.build_plan_dispatch_trace(
        state,
        walk=walk,
        schedule=["workflow_spl", "execution"],
        hooks=_hooks(),
        dispatch_source="test",
    )
    assert "execution_order" not in trace


# --- flag on ------------------------------------------------------------------


def test_flag_on_merge_restores_the_stage_the_compiler_drops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", True)
    state = _state()
    walk = walk_plan_steps(state)

    compiled, reason, merge_trace = executor._execution_driven_schedule_detailed(state, walk)
    assert reason is None
    assert compiled == ["workflow_spl", "spl_postprocessor", "spl_source_resolve", "execution"]
    assert merge_trace is not None
    assert merge_trace["inserted_phases"] == ["spl_postprocessor"]
    assert merge_trace["capability_satisfied"] is True
    assert merge_trace["capability_missing"] == []


def test_flag_on_without_a_contract_keeps_the_pre_c1_compiler_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", True)
    state = _state(with_contract=False)
    compiled, reason, merge_trace = executor._execution_driven_schedule_detailed(
        state, walk_plan_steps(state)
    )
    assert reason is None
    assert compiled == ["workflow_spl", "spl_source_resolve", "execution"]
    assert merge_trace is None


def test_dispatch_v2_projection_still_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ladder precedence is unchanged: a v2 projected schedule owns ordering."""
    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", True)
    monkeypatch.setattr(
        "app.planner.executor.imperative_hook_schedule_from_state",
        lambda _state: ["workflow_spl", "execution"],
    )
    state = _state()
    compiled, reason, merge_trace = executor._execution_driven_schedule_detailed(
        state, walk_plan_steps(state)
    )
    assert compiled is None
    assert reason == "dispatch_v2_projected_schedule"
    assert merge_trace is None


def test_flag_on_trace_records_the_phase_contract_without_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", True)
    state = _state()
    trace = executor.build_plan_dispatch_trace(
        state,
        walk=walk_plan_steps(state),
        schedule=["workflow_spl", "spl_postprocessor", "spl_source_resolve", "execution"],
        hooks=_hooks(),
        dispatch_source="test",
    )
    merge = trace["execution_order"]["phase_merge"]
    assert merge["phase_contract"]["schema_version"] == "phase_contract_v1"
    assert all(phase["removable"] is False for phase in merge["phase_contract"]["phases"])
    assert "execution_eligible" not in repr(merge)


def test_invalid_contract_payload_degrades_to_the_compiler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", True)
    state = _state()
    state["resolved_query_contract"] = {"normalized_goal": "missing everything else"}
    compiled, reason, merge_trace = executor._execution_driven_schedule_detailed(
        state, walk_plan_steps(state)
    )
    assert reason is None
    assert compiled == ["workflow_spl", "spl_source_resolve", "execution"]
    assert merge_trace is None


def test_merge_seam_has_exactly_one_wiring_site() -> None:
    """A second call site would be a second execution authority."""
    import ast
    from pathlib import Path

    source = Path(executor.__file__).read_text(encoding="utf-8")
    hits = [
        line
        for line in source.splitlines()
        if "merge_schedule(" in line and not line.strip().startswith(("#", "from ", "def "))
    ]
    assert len(hits) == 1, hits

    tree = ast.parse(source)
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "app.planner.phase_schedule_merge" in imports
