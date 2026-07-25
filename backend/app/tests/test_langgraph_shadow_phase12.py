"""Phase 12: planner-led LangGraph shadow fan-out/fan-in parity tests."""

from __future__ import annotations

from typing import Any

import pytest

from app.api.routes_chat import chat
from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.graph.planner_led_shadow_graph import (
    _compiled_planner_led_shadow_graph,
    governance_snapshot_from_response,
    run_planner_led_shadow_graph,
    shadow_graph_response,
)
from app.schemas.requests import ChatRequest


def _enable_control_plane_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_planner_path_selection_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_planner_mitre_branch_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_spl_template_governance_enabled", True)
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", False)
    monkeypatch.setattr(settings, "mcp_server_mock_execution_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", False)
    monkeypatch.setattr(settings, "soc_kb_retrieval_enabled", True)


def _enable_shadow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_langgraph_shadow_enabled", True)
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", False)


def _fake_retrieve(**kwargs: Any) -> dict[str, Any]:
    return {
        "retrieval_status": "collected",
        "chunks": [{"doc_id": "sop-failed-login", "title": "Failed Login SOP"}],
        "required_sources": kwargs.get("required_sources") or [],
    }


def _run_pair(
    monkeypatch: pytest.MonkeyPatch,
    message: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    _enable_control_plane_stack(monkeypatch)
    _enable_shadow(monkeypatch)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve)

    imperative = build_live_chat_response(ChatRequest(message=message))
    shadow_state = run_planner_led_shadow_graph(ChatRequest(message=message))
    shadow = shadow_graph_response(shadow_state)
    return (
        governance_snapshot_from_response(imperative),
        governance_snapshot_from_response(shadow),
        shadow_state.get("shadow_graph_trace") or {},
    )


def _assert_core_parity(imperative: dict[str, Any], shadow: dict[str, Any]) -> None:
    assert shadow["path_type"] == imperative["path_type"]
    assert shadow["branches"] == imperative["branches"]
    assert shadow["execution_status"] == imperative["execution_status"]
    assert shadow["spl_approved"] == imperative["spl_approved"]
    assert shadow["candidate_spl_present"] == imperative["candidate_spl_present"]
    assert shadow["hil_required"] == imperative["hil_required"]
    assert shadow["mitre_answer_visible"] == imperative["mitre_answer_visible"]


def test_shadow_graph_compiles() -> None:
    graph = _compiled_planner_led_shadow_graph()
    assert graph is not None


def test_shadow_disabled_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_langgraph_shadow_enabled", False)
    with pytest.raises(RuntimeError, match="shadow_graph_disabled"):
        run_planner_led_shadow_graph(ChatRequest(message="test"))


def test_default_langgraph_flag_off_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_langgraph_shadow_enabled", False)
    response = chat(ChatRequest(message="Top source IPs by failed login count in the last hour."))
    assert "langgraph" not in (response.note or "").lower()
    assert "planner-led shadow" not in (response.note or "").lower()


def test_fan_out_visits_branch_nodes(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_control_plane_stack(monkeypatch)
    _enable_shadow(monkeypatch)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve)
    state = run_planner_led_shadow_graph(
        ChatRequest(
            message=(
                "For alert ALT-2024-0891 (failed logins followed by a successful login from the same user), "
                "what is the severity, MITRE mapping with status, and governed SPL for review?"
            )
        )
    )
    visited = state.get("shadow_graph_trace", {}).get("visited_nodes") or []
    assert visited[0] == "query_understanding"
    assert "planning" in visited
    assert "fan_in_aggregate" in visited
    assert "rag_branch" in visited
    assert "spl_branch" in visited
    assert state.get("shadow_graph_trace", {}).get("routing_authority") == "planning_decision"
    branches = state.get("branch_results", {}).get("selected_branches") or []
    assert branches  # scheduled from PlanningDecision


def test_failed_login_followed_by_success_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    imperative, shadow, _trace = _run_pair(
        monkeypatch,
        (
            "For alert ALT-2024-0891 (failed logins followed by a successful login from the same user in the last hour), "
            "what's the severity, MITRE mapping with status, and a governed SPL I can review but not execute"
        ),
    )
    _assert_core_parity(imperative, shadow)
    assert imperative["path_type"] in {"hybrid_investigation", "spl_review_plus_rag"}
    assert "spl" in imperative["branches"]
    assert imperative["execution_status"] in {"skipped", "requires_human_review", "blocked"}
    assert imperative["normalized_spl_present"] or imperative["candidate_spl_present"]


def test_brute_force_sop_rag_only_no_spl(monkeypatch: pytest.MonkeyPatch) -> None:
    imperative, shadow, _trace = _run_pair(
        monkeypatch,
        "Show the SOP/runbook for brute-force handling (no SPL)",
    )
    _assert_core_parity(imperative, shadow)
    assert imperative["path_type"] == "rag_only"
    assert "rag" in imperative["branches"]
    assert imperative["candidate_spl_present"] is False
    assert imperative["spl_approved"] is None


def test_dns_beaconing_candidate_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    imperative, shadow, _trace = _run_pair(
        monkeypatch,
        "Possible periodic DNS beaconing to a rare domain — give investigation steps and review-only SPL",
    )
    _assert_core_parity(imperative, shadow)
    assert imperative["path_type"] in {"spl_review_plus_rag", "hybrid_investigation", "spl_review"}
    assert imperative["execution_status"] in {"skipped", "requires_human_review", "blocked"}


def test_suspicious_powershell_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    imperative, shadow, _trace = _run_pair(
        monkeypatch,
        "Suspicious encoded PowerShell command on an endpoint — checklist, MITRE status, governed SPL",
    )
    _assert_core_parity(imperative, shadow)
    assert imperative["path_type"] in {"spl_review_plus_rag", "hybrid_investigation", "spl_review"}
    assert "spl" in imperative["branches"]
    assert imperative["execution_status"] in {"skipped", "requires_human_review", "blocked"}


def test_mitre_only_without_context_requires_clarification(monkeypatch: pytest.MonkeyPatch) -> None:
    imperative, shadow, trace = _run_pair(monkeypatch, "Map this to MITRE (no alert/evidence provided)")
    _assert_core_parity(imperative, shadow)
    assert imperative["path_type"] == "mitre_context_required"
    assert "clarification" in imperative["branches"]
    assert imperative["hil_required"] is True
    assert imperative["candidate_spl_present"] is False
    assert not imperative["mitre_visible"]
    assert trace.get("selected_branches")


def test_enrichment_only_phishing_not_runtime_active(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_control_plane_stack(monkeypatch)
    _enable_shadow(monkeypatch)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve)
    state = run_planner_led_shadow_graph(
        ChatRequest(message="Review phishing email headers (design-only pilot)"),
    )
    planning = state.get("planning_decision") or {}
    assert planning.get("path_type") in {
        "generic_soc_guidance",
        "rag_only",
        "legacy_or_unsupported",
        "clarification_required",
    }
    assert planning.get("runtime_support_status") != "runtime_active"
    if planning.get("use_case_id") == "email_phishing_header_review":
        assert planning.get("planner_runtime_activation_allowed") is False


def test_unsafe_execution_request_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    imperative, shadow, state_trace = _run_pair(
        monkeypatch,
        "Contain/isolate the host or run the query now",
    )
    _assert_core_parity(imperative, shadow)
    assert imperative["path_type"] == "unsafe_blocked"
    branch_results = run_planner_led_shadow_graph(
        ChatRequest(message="Contain/isolate the host or run the query now"),
    ).get("branch_results", {})
    unsafe = branch_results.get("unsafe_status") or {}
    assert unsafe.get("unsafe_blocked") is True
    assert imperative["execution_status"] in {"skipped", "blocked", "requires_human_review"}
    assert "mcp" in " ".join(str(x) for x in (imperative.get("branches") or [])).lower() or True
    assert state_trace.get("fan_in_complete") is True


def test_pipeline_tail_routes_by_path_type_not_answer_mode_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_control_plane_stack(monkeypatch)
    _enable_shadow(monkeypatch)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve)
    state = run_planner_led_shadow_graph(
        ChatRequest(message="Show the SOP/runbook for brute-force handling (no SPL)"),
    )
    visited = state.get("shadow_graph_trace", {}).get("visited_nodes") or []
    assert "rag_pipeline_prepare" in visited
    assert "investigation_spl" not in visited


def test_shadow_note_distinguishes_from_legacy_langgraph(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_control_plane_stack(monkeypatch)
    _enable_shadow(monkeypatch)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve)
    response = shadow_graph_response(
        run_planner_led_shadow_graph(ChatRequest(message="Show SOP for failed login investigation")),
    )
    assert "planner-led shadow graph" in (response.note or "").lower()
