"""Plan 6 E0 — inline MITRE/CVE provenance matches what actually ran.

pipeline_inline ownership stays on graph_node_context_finalize. These tests
fail if provenance claims mitre_finalize/cve_adapter when those functions did
not run, or omits them when they did. They also fail if the phases are added
to a hook loop.
"""

from __future__ import annotations

from app.chat.debug_summary import build_debug_summary
from app.planner.inline_execution_provenance import (
    INLINE_CVE,
    INLINE_MITRE,
    inline_executed_names,
    mitre_inline_ran,
)
from app.planner.phase_registry import phase_spec, phases_without_hook_owner
from app.tests.test_debug_summary import _scada_like_payload
from app.tests.test_phase_registry import _fallback_hook_node_keys, _hook_by_name_keys


def test_inline_executed_names_lists_only_what_ran() -> None:
    assert inline_executed_names(mitre_ran=True, cve_ran=False) == [INLINE_MITRE]
    assert inline_executed_names(mitre_ran=False, cve_ran=True) == [INLINE_CVE]
    assert inline_executed_names(mitre_ran=True, cve_ran=True) == [INLINE_MITRE, INLINE_CVE]
    assert inline_executed_names(mitre_ran=False, cve_ran=False) == []


def test_mitre_inline_ran_false_when_planner_suppressed() -> None:
    assert mitre_inline_ran(branch_ran=True, suppressed_not_applicable=True) is True
    assert mitre_inline_ran(branch_ran=False, suppressed_not_applicable=True) is False
    assert mitre_inline_ran(branch_ran=False, suppressed_not_applicable=False) is True


def test_debug_summary_lists_inline_executed_when_functions_ran() -> None:
    payload = _scada_like_payload()
    payload["plan_dispatch_trace"] = {
        "dispatch_schedule": ["workflow_spl", "execution"],
        "inline_executed": [INLINE_MITRE, INLINE_CVE],
        "execution_order": {
            "phase_merge": {
                "phase_contract": {
                    "inline_mandatory": [INLINE_MITRE],
                    "phases": [{"name": "workflow_spl", "removable": False}],
                }
            }
        },
    }
    schedule = build_debug_summary(payload=payload)["schedule"]
    assert INLINE_MITRE in schedule["inline_executed"]
    assert INLINE_CVE in schedule["inline_executed"]
    assert INLINE_MITRE in schedule["inline_mandatory"]


def test_debug_summary_omits_inline_names_when_functions_did_not_run() -> None:
    payload = _scada_like_payload()
    payload["plan_dispatch_trace"] = {
        "dispatch_schedule": ["prepare_rag_only"],
        "inline_executed": [],
    }
    schedule = build_debug_summary(payload=payload)["schedule"]
    assert schedule["inline_executed"] == []
    assert INLINE_MITRE not in schedule["inline_executed"]
    assert INLINE_CVE not in schedule["inline_executed"]


def test_inline_phases_are_not_added_to_hook_loops() -> None:
    hook_loop = _hook_by_name_keys()
    fallback = _fallback_hook_node_keys()
    for name in (INLINE_MITRE, INLINE_CVE):
        assert name not in hook_loop
        assert name not in fallback
        assert phase_spec(name).owner == "pipeline_inline"
    assert INLINE_MITRE in phases_without_hook_owner()
    assert INLINE_CVE in phases_without_hook_owner()


def test_rp_graph_invoke_survives_inline_executed_on_debug_summary(monkeypatch) -> None:
    monkeypatch.setattr("app.config.settings.mcp_global_execution_enabled", False)
    monkeypatch.setattr("app.config.settings.langgraph_orchestration_enabled", True)
    monkeypatch.setattr("app.config.settings.telemetry_mode", "none")
    monkeypatch.setattr("app.config.settings.ai_soc_telemetry_sink", "none")
    from app.graph.resource_planner_graph import run_chat_via_resource_planner_graph
    from app.schemas.requests import ChatRequest

    response = run_chat_via_resource_planner_graph(
        ChatRequest(message="What is the playbook for ransomware response?")
    )
    payload = response.model_dump(mode="json")
    summary = build_debug_summary(payload=payload)
    executed = summary["schedule"]["inline_executed"]
    assert isinstance(executed, list)
    # Default planner MITRE branch is off, so _mitre_outputs_for_finalize runs.
    assert INLINE_MITRE in executed
    assert INLINE_CVE not in executed
    assert "selected_skill" not in str(summary["schedule"])
    assert "execution_eligible" not in str(summary["schedule"])
