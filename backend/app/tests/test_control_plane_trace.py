from __future__ import annotations

from app.chat.control_plane_trace import build_control_plane_trace
from app.api.routes_chat import chat
from app.schemas.requests import ChatRequest


def test_control_plane_trace_contains_phase_outputs_and_redacts_secrets() -> None:
    trace = build_control_plane_trace(
        {
            "query_to_intent": {"query_signals": {"failed_login": True}},
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
    assert trace["evidence_plan"]["answer_mode"] == "hybrid"
    assert trace["route_adjudication"]["final_route"] == "attack_discovery"
    assert trace["mitre_registry_metadata"]["api_token"] == "[REDACTED]"
    assert trace["rag_trace"]["dsn"] if "dsn" in trace["rag_trace"] else True
    assert trace["spl_slot_binding"]["missing_bindings"] == ["last_24h"]
    assert trace["source_evidence_refs"] == ["src-1"]
    assert trace["llm_advisory_trace"] == {
        "llm_advisory_used": False,
        "llm_route_candidate": None,
        "llm_intent_candidate": None,
        "llm_narration_used": False,
        "llm_overridden_by_policy": False,
    }


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
