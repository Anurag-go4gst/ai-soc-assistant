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

