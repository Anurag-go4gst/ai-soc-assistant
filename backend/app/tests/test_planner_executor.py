"""T0.4 — plan execution loop: dispatch parity, degrade chains, step statuses."""

from __future__ import annotations

import json
from typing import Any

from app.evals.sentinel_eval import BASELINE_PATH, capture_row
from app.planner.executor import (
    DispatchHooks,
    annotate_step_statuses,
    execute_plan_dispatch,
    has_composed_plan,
)


def _state_with_plan(steps: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {
        "evidence_plan": {
            "answer_mode": "live_investigation",
            "resource_plan": {"plan_source": "deterministic", "steps": steps, "provenance": {}},
        },
        **extra,
    }


def _hooks(calls: list[str], *, rag_only: bool = False, pre_mcp: bool = False) -> DispatchHooks:
    def node(name: str):
        def run(state: dict[str, Any]) -> dict[str, Any]:
            calls.append(name)
            if name == "workflow_spl":
                return {**state, "workflow_plan": {"skill": "spl_generation"}}
            if name == "ensure_workflow_plan":
                return {**state, "workflow_plan": {"skill": "alert_summary"}}
            return state

        return run

    return DispatchHooks(
        uses_rag_only_path=lambda state: rag_only,
        uses_pre_mcp_rag=lambda state: pre_mcp,
        prepare_rag_only=node("prepare_rag_only"),
        rag_early=node("rag_early"),
        spl_source_resolve=node("spl_source_resolve"),
        workflow_spl=node("workflow_spl"),
        ensure_workflow_plan=node("ensure_workflow_plan"),
        execution=node("execution"),
    )


def test_dispatch_matches_legacy_live_branch_order() -> None:
    calls: list[str] = []
    state = _state_with_plan(
        [
            {"step_id": "spl", "resource_id": "skill:spl_generation", "purpose": "spl_artifact"},
            {"step_id": "mcp", "resource_id": "mcp_tool:splunk_run_query", "purpose": "mcp_execution"},
        ]
    )
    execute_plan_dispatch(state, _hooks(calls, pre_mcp=True))
    assert calls == ["workflow_spl", "rag_early", "spl_source_resolve", "execution"]


def test_dispatch_matches_legacy_rag_only_branch() -> None:
    calls: list[str] = []
    state = _state_with_plan(
        [{"step_id": "rag", "resource_id": "rag_corpus:soc_kb", "purpose": "knowledge_retrieval"}]
    )
    execute_plan_dispatch(state, _hooks(calls, rag_only=True))
    assert calls == ["prepare_rag_only", "rag_early"]


def test_blocked_registry_resource_step_is_never_dispatched() -> None:
    calls: list[str] = []
    state = _state_with_plan(
        [
            {
                "step_id": "rag",
                "resource_id": "mcp_tool:create_kvstore_collection",
                "purpose": "knowledge_retrieval",
            }
        ]
    )
    result = execute_plan_dispatch(state, _hooks(calls, rag_only=True))
    assert "rag_early" not in calls
    steps = result["evidence_plan"]["resource_plan"]["steps"]
    assert steps[0]["status"] == "blocked_policy"
    assert steps[0]["status_reason"] == "registry_resource_blocked"


def test_execution_stage_always_runs_on_live_branch() -> None:
    """The execution node owns the MCP gate/HIL — it must run even when the
    plan carries no MCP step (legacy behavior)."""
    calls: list[str] = []
    state = _state_with_plan(
        [{"step_id": "spl", "resource_id": "skill:spl_generation", "purpose": "spl_artifact"}]
    )
    execute_plan_dispatch(state, _hooks(calls))
    assert calls == ["workflow_spl", "spl_source_resolve", "execution"]


def test_annotate_statuses_executed_fallback_blocked() -> None:
    state = _state_with_plan(
        [
            {"step_id": "rag", "resource_id": "rag_corpus:soc_kb", "purpose": "knowledge_retrieval"},
            {
                "step_id": "spl",
                "resource_id": "spl_template_family:auth_failed_login_spike",
                "purpose": "spl_artifact",
                "on_unavailable": "spl_lab_draft_family:auth_failed_login_threshold",
            },
            {"step_id": "mcp", "resource_id": "mcp_tool:splunk_run_query", "purpose": "mcp_execution"},
            {"step_id": "mitre", "resource_id": "skill:mitre_mapping", "purpose": "mitre_mapping"},
        ],
        soc_kb_retrieval={"retrieval_status": "ok"},
        spl_validation={"candidate_provider_reason": "spl_template_missing"},
        execution={"status": "blocked", "block_reason": "mcp_execution_disabled"},
        mitre_decision={"answer_visible": False},
    )
    result = annotate_step_statuses(state)
    statuses = {
        step["step_id"]: (step["status"], step.get("status_reason"))
        for step in result["evidence_plan"]["resource_plan"]["steps"]
    }
    assert statuses["rag"] == ("executed", None)
    assert statuses["spl"][0] == "fallback_taken"
    assert "spl_lab_draft_family:auth_failed_login_threshold" in statuses["spl"][1]
    assert statuses["mcp"] == ("blocked_policy", "mcp_execution_disabled")
    assert statuses["mitre"] == ("executed", None)


def test_has_composed_plan_false_for_legacy_state() -> None:
    assert not has_composed_plan({"evidence_plan": {"answer_mode": "rag_only"}})
    assert not has_composed_plan({})


def test_full_pipeline_sentinel_row_matches_frozen_baseline() -> None:
    """q0.q010 through the executor-dispatched pipeline == frozen contract."""
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))["rows"]["q0.q010"]
    capture = capture_row("Which hosts are generating the most SMB traffic?")
    assert capture == baseline


def test_preblocked_policy_mcp_step_still_runs_execution_gate() -> None:
    calls: list[str] = []
    state = _state_with_plan(
        [
            {
                "step_id": "mcp",
                "resource_id": "mcp_tool:splunk_run_query",
                "purpose": "mcp_execution",
                "status": "blocked_policy",
                "status_reason": "skill_contract",
                "policy_checks": ["blocked_by_skill_contract"],
            }
        ]
    )
    result = execute_plan_dispatch(state, _hooks(calls))
    assert "execution" in calls
    mcp = next(s for s in result["evidence_plan"]["resource_plan"]["steps"] if s["step_id"] == "mcp")
    assert mcp["status"] == "blocked_policy"


def test_mcp_step_metadata_attached_on_annotate() -> None:
    state = _state_with_plan(
        [{"step_id": "mcp", "resource_id": "mcp_tool:splunk_run_query", "purpose": "mcp_execution"}],
        execution={"status": "blocked", "block_reason": "mcp_global_execution_disabled", "selected_mcp_tool": "splunk_run_query"},
    )
    result = annotate_step_statuses(state)
    mcp = next(s for s in result["evidence_plan"]["resource_plan"]["steps"] if s["step_id"] == "mcp")
    meta = mcp.get("mcp_step_metadata") or {}
    assert meta.get("primary_reason") == "mcp_global_execution_disabled"
    assert meta.get("selected_tool") == "splunk_run_query"
    assert meta.get("execution_authorized") is False


def test_preblocked_mcp_preserves_skill_contract_reason_and_metadata() -> None:
    calls: list[str] = []
    state = _state_with_plan(
        [
            {
                "step_id": "mcp",
                "resource_id": "mcp_tool:splunk_run_query",
                "purpose": "mcp_execution",
                "status": "blocked_policy",
                "status_reason": "skill_contract",
                "policy_checks": ["blocked_by_skill_contract"],
            }
        ]
    )
    result = execute_plan_dispatch(state, _hooks(calls))
    mcp = next(s for s in result["evidence_plan"]["resource_plan"]["steps"] if s["step_id"] == "mcp")
    assert mcp["status_reason"] == "skill_contract"
    meta = mcp.get("mcp_step_metadata") or {}
    assert meta.get("status") == "blocked_policy"
    assert meta.get("primary_reason") == "skill_contract"
    assert "skill_contract" in meta.get("secondary_reasons", [])


def test_mcp_step_metadata_normalizes_requires_human_review() -> None:
    state = _state_with_plan(
        [{"step_id": "mcp", "resource_id": "mcp_tool:splunk_run_query", "purpose": "mcp_execution"}],
        execution={"status": "requires_human_review", "block_reason": "spl_validation_failed"},
    )
    result = annotate_step_statuses(state)
    mcp = next(s for s in result["evidence_plan"]["resource_plan"]["steps"] if s["step_id"] == "mcp")
    meta = mcp.get("mcp_step_metadata") or {}
    assert meta.get("status") == "blocked_policy"
    assert meta.get("primary_reason") == "spl_validation_failed"

def test_finalize_annotate_preserves_skill_contract_over_execution_gate() -> None:
    state = _state_with_plan(
        [
            {
                "step_id": "mcp",
                "resource_id": "mcp_tool:splunk_run_query",
                "purpose": "mcp_execution",
                "status": "blocked_policy",
                "status_reason": "skill_contract",
                "policy_checks": ["blocked_by_skill_contract"],
            }
        ],
        execution={
            "status": "blocked",
            "block_reason": "mcp_global_execution_disabled",
            "selected_mcp_tool": "splunk_run_query",
        },
    )
    result = annotate_step_statuses(state)
    mcp = next(s for s in result["evidence_plan"]["resource_plan"]["steps"] if s["step_id"] == "mcp")
    assert mcp["status"] == "blocked_policy"
    assert mcp["status_reason"] == "skill_contract"
    meta = mcp.get("mcp_step_metadata") or {}
    assert meta.get("primary_reason") == "skill_contract"
    assert "mcp_global_execution_disabled" in meta.get("secondary_reasons", [])


def test_dispatch_then_finalize_annotate_preserves_skill_contract() -> None:
    calls: list[str] = []
    state = _state_with_plan(
        [
            {
                "step_id": "mcp",
                "resource_id": "mcp_tool:splunk_run_query",
                "purpose": "mcp_execution",
                "status": "blocked_policy",
                "status_reason": "skill_contract",
                "policy_checks": ["blocked_by_skill_contract"],
            }
        ],
        execution={
            "status": "blocked",
            "block_reason": "mcp_global_execution_disabled",
        },
    )
    dispatched = execute_plan_dispatch(state, _hooks(calls))
    finalized = annotate_step_statuses(dispatched)
    mcp = next(
        s for s in finalized["evidence_plan"]["resource_plan"]["steps"] if s["step_id"] == "mcp"
    )
    assert mcp["status_reason"] == "skill_contract"
    meta = mcp.get("mcp_step_metadata") or {}
    assert meta.get("primary_reason") == "skill_contract"



from app.planner.executor import (
    build_step_walk_dispatch_schedule,
    derive_dispatch_booleans_from_plan,
    walk_plan_steps,
    _legacy_predicate_dispatch_schedule,
)


def test_walk_plan_steps_and_predicate_parity_on_live_plan() -> None:
    calls: list[str] = []
    state = _state_with_plan(
        [
            {"step_id": "spl", "resource_id": "skill:spl_generation", "purpose": "spl_artifact"},
            {"step_id": "mcp", "resource_id": "mcp_tool:splunk_run_query", "purpose": "mcp_execution"},
        ]
    )
    walk = walk_plan_steps(state)
    assert walk is not None
    hooks = _hooks(calls, pre_mcp=True)
    legacy = _legacy_predicate_dispatch_schedule(state, hooks, walk.blocked_step_ids)
    walked = build_step_walk_dispatch_schedule(state, walk, hooks)
    assert walked == legacy
    execute_plan_dispatch(state, hooks)
    assert calls == walked
