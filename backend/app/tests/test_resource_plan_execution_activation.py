"""Plan 2 C1-E4 — activation posture for ResourcePlan-driven execution order.

C0 approved `DEDICATED_DEFAULT_FALSE_FLAG` with the exact name
`AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED`. This pins the name, the default, and
that flag-off reaches no execution-contract code at all.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.config import Settings, settings
from app.planner import executor
from app.planner.executor import DispatchHooks, build_step_walk_dispatch_schedule, walk_plan_steps


def _hooks(*, rag_only: bool = False, pre_mcp: bool = False) -> DispatchHooks:
    def node(_name: str):
        def run(state: dict[str, Any]) -> dict[str, Any]:
            return state

        return run

    return DispatchHooks(
        uses_rag_only_path=lambda _s: rag_only,
        uses_pre_mcp_rag=lambda _s: pre_mcp,
        prepare_rag_only=node("prepare_rag_only"),
        rag_early=node("rag_early"),
        spl_source_resolve=node("spl_source_resolve"),
        workflow_spl=node("workflow_spl"),
        spl_postprocessor=node("spl_postprocessor"),
        ensure_workflow_plan=node("ensure_workflow_plan"),
        reference_finalize=node("reference_finalize"),
        execution=node("execution"),
    )


def _state() -> dict[str, Any]:
    return {
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


def test_flag_name_and_default() -> None:
    assert Settings().ai_soc_resource_plan_execution_enabled is False
    assert "ai_soc_resource_plan_execution_enabled" in Settings.model_fields


def test_env_var_name_is_the_c0_approved_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED", "true")
    assert Settings().ai_soc_resource_plan_execution_enabled is True


def test_env_example_declares_the_flag_default_false() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    text = (root / ".env.example").read_text(encoding="utf-8")
    assert "AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED=false" in text


def test_flag_off_reaches_no_execution_contract_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flag-off parity is structural: the compiler is never called."""
    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", False)
    calls: list[Any] = []

    def _boom(*args: Any, **kwargs: Any):  # pragma: no cover - must not run
        calls.append(args)
        raise AssertionError("compiler reached while the flag is off")

    monkeypatch.setattr(
        "app.planner.resource_plan_execution_scheduler.compile_execution_schedule", _boom
    )
    state = _state()
    walk = walk_plan_steps(state)
    build_step_walk_dispatch_schedule(state, walk, _hooks())
    assert calls == []


def test_flag_off_reports_no_downgrade_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", False)
    state = _state()
    assert executor._execution_driven_schedule(state, walk_plan_steps(state)) == (None, None)


def test_flag_on_activates_the_compiled_schedule(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", True)
    state = _state()
    compiled, reason = executor._execution_driven_schedule(state, walk_plan_steps(state))
    assert reason is None
    assert compiled == ["workflow_spl", "spl_source_resolve", "execution"]
