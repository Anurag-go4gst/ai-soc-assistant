from __future__ import annotations

from app.chat.control_plane_trace import build_control_plane_trace
from app.api.routes_chat import chat
from app.schemas.requests import ChatRequest


def test_control_plane_trace_contains_phase_outputs_and_redacts_secrets() -> None:
    trace = build_control_plane_trace(
        {
            "query_to_intent": {"query_signals": {"failed_login": True}},
            "routed": {
                "routing_provenance": {
                    "rescue_mode": True,
                    "authority_source": "guided_investigation_rescue",
                    "why_not_knowledge_recall": "Investigation process requested.",
                }
            },
            "evidence_plan": {"answer_mode": "hybrid"},
            "route_adjudication": {"final_route": "attack_discovery"},
            "llm_plan_validation": {"status": "accepted"},
            "workflow_plan": {"skill": "attack_discovery", "tool_plan": ["validate_spl"], "execution_enabled": False},
            "mitre_decision": {
                "answer_visible": True,
                "registry_metadata": {"mitre_permitted": ["T1110.001"], "api_token": "secret"},
            },
            "soc_kb_retrieval": {"match_status": "no_match", "dsn": "postgres://secret"},
            "spl_validation": {
                "approved": False,
                "reject_reasons": ["missing_binding:last_24h"],
                "warnings": [],
                "policy_version": "v1",
            },
            "execution": {"status": "blocked", "block_reason": "mcp_global_execution_disabled"},
        },
        source_evidence=[{"evidence_id": "src-1"}],
        context_sufficiency={"status": "insufficient_evidence"},
        synthesis_mode="deterministic_no_final_llm",
        answer_guard={"enabled": False},
    )
    assert trace["query_to_intent"]["query_signals"]["failed_login"] is True
    assert trace["routing_provenance"]["rescue_mode"] is True
    assert trace["routing_provenance"]["authority_source"] == "guided_investigation_rescue"
    assert trace["evidence_plan"]["answer_mode"] == "hybrid"
    assert trace["route_adjudication"]["final_route"] == "attack_discovery"
    assert trace["mitre_registry_metadata"]["api_token"] == "[REDACTED]"
    assert trace["rag_trace"]["dsn"] if "dsn" in trace["rag_trace"] else True
    assert trace["spl_slot_binding"]["missing_bindings"] == ["last_24h"]
    assert trace["source_evidence_refs"] == ["src-1"]
    advisory = trace["llm_advisory_trace"]
    assert advisory["authority_tier"] == "ADVISORY"
    assert advisory["llm_advisory_attempted"] is False
    assert advisory["llm_dropped_reasons"] == []
    assert trace["trace_authority_index"]["route_adjudication"]["authority_tier"] == "AUTHORITATIVE"
    assert trace["route_plan_shadow_authority"]["authority_tier"] == "DIAGNOSTIC"


def test_llm_advisory_trace_records_policy_override_without_new_calls() -> None:
    trace = build_control_plane_trace(
        {
            "routed": {
                "selected_by": "out_of_registry_investigation_rescue",
                "llm_semantic_advisory": {"skill": "knowledge_recall"},
            },
            "query_to_intent": {"llm_intent_assist_status": "rejected"},
        }
    )
    advisory = trace["llm_advisory_trace"]
    assert advisory["llm_candidate_present"] is True
    assert advisory["llm_advisory_used"] is True
    assert advisory["llm_route_candidate"] == "knowledge_recall"
    assert advisory["llm_overridden_by_policy"] is True


def test_chat_control_plane_trace_attaches_when_flag_on(monkeypatch) -> None:
    monkeypatch.setattr("app.config.settings.control_plane_enabled", True)
    response = chat(ChatRequest(message="What is the escalation policy for repeated failed login alerts?"))
    assert response.control_plane_trace is not None
    assert response.control_plane_trace["query_to_intent"] is not None
    assert response.control_plane_trace["evidence_plan"]["answer_mode"] == "rag_only"
    assert response.control_plane_trace["mitre_decision"] is not None


def test_trace_authority_tiers_on_run_contract() -> None:
    trace = build_control_plane_trace(
        {
            "run_contract": {"execution_authorized": False},
            "final_evidence_gate": {"effective_hil_required": True},
            "route_adjudication": {"final_route": "spl_generation"},
        }
    )
    assert trace["run_contract"]["authority_tier"] == "AUTHORITATIVE"
    assert trace["final_evidence_gate"]["authority_tier"] == "AUTHORITATIVE"
    assert trace["trace_authority_index"]["evidence_plan"]["authority_tier"] == "PLANNING"

def test_control_plane_trace_reflects_post_handoff_evidence_plan() -> None:
    """Trace evidence_plan must match the post-annotate handoff state."""
    from app.planner.executor import annotate_step_statuses

    evidence_plan = {
        "answer_mode": "live_investigation",
        "resource_plan": {
            "steps": [
                {
                    "step_id": "mcp",
                    "purpose": "mcp_execution",
                    "status": "blocked_policy",
                    "status_reason": "skill_contract",
                    "policy_checks": ["blocked_by_skill_contract"],
                }
            ]
        },
        "handoff_drift_from_final_spl": True,
        "handoff_drift_details": ["normalized_slots.index"],
    }
    state = annotate_step_statuses(
        {
            "evidence_plan": evidence_plan,
            "execution": {"status": "blocked", "block_reason": "mcp_global_execution_disabled"},
        }
    )
    trace = build_control_plane_trace(state)
    traced_plan = trace["evidence_plan"]
    assert traced_plan["handoff_drift_from_final_spl"] is True
    mcp = next(s for s in traced_plan["resource_plan"]["steps"] if s["step_id"] == "mcp")
    assert mcp["status_reason"] == "skill_contract"



def test_control_plane_trace_includes_dispatch_projection() -> None:
    trace = build_control_plane_trace(
        {
            "intent_dispatch": {
                "call_2c_llm": False,
                "prompt_mode": "skip",
                "skip_reasons": ["deterministic_exact_match_t0"],
            },
            "pipeline_dispatch": {
                "decision": {
                    "request_mode": "spl_authoring",
                    "stage_schedule": ["workflow_spl", "spl_postprocessor", "spl_source_resolve"],
                    "llm_hops": ["spl_plan_compiler"],
                },
                "runtime_context": {"dispatch_cursor": None},
            },
        }
    )
    assert trace["intent_dispatch"]["prompt_mode"] == "skip"
    assert trace["pipeline_dispatch"]["decision"]["request_mode"] == "spl_authoring"


def test_mcp_calls_trace_empty_when_no_recipe_active() -> None:
    # The vast majority of turns today — no recipe means an empty list, never None.
    trace = build_control_plane_trace({})
    assert trace["mcp_calls"] == []
    assert trace["mcp_loop"] is None


def test_mcp_calls_trace_populated_for_recipe_driven_turn() -> None:
    trace = build_control_plane_trace(
        {
            "mcp_recipe_id": "hunt_baseline",
            "mcp_call_records": [
                {"call_id": "c1_discovery", "sequence": 0, "outcome": "ok", "result_count": 1},
                {"call_id": "c2_bounded_search", "sequence": 1, "outcome": "empty", "result_count": 0},
            ],
            "mcp_loop": {"route": "human_review", "reason": "test verdict"},
        }
    )
    calls = trace["mcp_calls"]
    assert len(calls) == 2
    assert calls[0] == {
        "call_id": "c1_discovery",
        "call_class": "metadata_discovery",
        "outcome": "ok",
        "evidence_keys_resolved": ["discovery_context"],
        "result_count": 1,
        "block_reason": None,
    }
    assert calls[1]["call_class"] == "evidence_search"
    assert calls[1]["evidence_keys_resolved"] == ["hunt_search_rows"]
    assert trace["mcp_loop"]["route"] == "human_review"


def test_mcp_calls_trace_failed_call_resolves_no_evidence_keys() -> None:
    trace = build_control_plane_trace(
        {
            "mcp_recipe_id": "hunt_baseline",
            "mcp_call_records": [
                {"call_id": "c1_discovery", "sequence": 0, "outcome": "blocked", "result_count": 0, "error_type": "mcp_discovery_disabled"},
            ],
        }
    )
    call = trace["mcp_calls"][0]
    assert call["outcome"] == "blocked"
    assert call["evidence_keys_resolved"] == []
    assert call["block_reason"] == "mcp_discovery_disabled"


def test_grounding_block_absent_when_no_canonical_facts() -> None:
    trace = build_control_plane_trace({})
    assert trace["grounding_block"] is None


def test_grounding_block_surfaced_from_state() -> None:
    trace = build_control_plane_trace(
        {
            "grounding_block": {
                "question": "x",
                "evidence_citations": [{"evidence_id": "ev_1", "source_type": "mcp_search", "row_count": 2}],
                "limitations": [],
            }
        }
    )
    assert trace["grounding_block"]["evidence_citations"][0]["evidence_id"] == "ev_1"


def test_grounding_block_wired_end_to_end_on_live_chat(monkeypatch) -> None:
    """Item 5.4: the assembler actually runs on the imperative live path and its
    output reaches the control-plane trace — proves it isn't dead-ended on
    internal pipeline state."""
    monkeypatch.setattr("app.config.settings.control_plane_enabled", True)
    response = chat(ChatRequest(message="Find failed-login users in the last 24 hours"))
    assert response.control_plane_trace is not None
    grounding = response.control_plane_trace.get("grounding_block")
    assert grounding is not None
    assert "evidence_citations" in grounding
    assert "limitations" in grounding


def test_control_plane_trace_includes_decision_log() -> None:
    trace = build_control_plane_trace(
        {
            "decision_log": [
                {
                    "record_id": "dr:1",
                    "node": "resource_planner.merge",
                    "authority": "resource_planner",
                    "decision_reason": "fan_in_complete",
                    "inputs_ref": ["specialist_reports"],
                    "outputs_ref": ["work_bundle"],
                }
            ]
        }
    )
    records = trace.get("decision_log")
    assert isinstance(records, list) and len(records) == 1
    assert records[0]["decision_reason"] == "fan_in_complete"


def test_langgraph_wrap_emits_decision_log_to_control_plane_trace(monkeypatch) -> None:
    monkeypatch.setattr("app.config.settings.control_plane_enabled", True)
    from app.graph.chat_workflow import run_chat_via_langgraph

    response = run_chat_via_langgraph(ChatRequest(message="What is AML.T0043?"))
    trace = response.control_plane_trace
    assert trace is not None
    records = trace.get("decision_log")
    assert isinstance(records, list) and records
    assert any(item.get("node") == "init_routing" for item in records if isinstance(item, dict))


    """Same behavior on the LangGraph dispatch path — required separately because
    LangGraph silently drops any state channel not declared in the TypedDict
    (grounding_block was declared in ChatPipelineState for exactly this reason)."""
    monkeypatch.setattr("app.config.settings.control_plane_enabled", True)
    from app.graph.chat_workflow import _compiled_chat_graph_cp

    final_state = _compiled_chat_graph_cp().invoke(
        {"request": ChatRequest(message="Find failed-login users in the last 24 hours"), "session_role": None},
        {"recursion_limit": 60},
    )
    assert isinstance(final_state.get("grounding_block"), dict)
    assert "evidence_citations" in final_state["grounding_block"]
