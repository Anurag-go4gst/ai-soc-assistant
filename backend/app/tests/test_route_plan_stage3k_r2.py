from __future__ import annotations

from typing import Any

from app.api.routes_chat import chat
from app.api.routes_scenarios import run_demo_scenario_fixture
from app.schemas.requests import ChatRequest


def test_chat_behavior_unchanged_with_route_plan_shadow(monkeypatch) -> None:
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")

    response = chat(ChatRequest(message="Top source IPs by failed login count in the last hour."))

    assert response.selected_skill == "attack_discovery"
    assert response.message == "SPL validation complete. MCP execution is disabled."
    assert response.note.startswith("Candidate SPL generated and approved by deterministic validation.")
    assert response.candidate_spl is not None
    assert response.spl_validation is not None
    assert response.spl_validation.approved is True
    assert response.execution is not None
    assert response.execution.executed_spl is None
    assert response.route_plan_shadow is not None
    assert response.route_plan_shadow.enabled is True
    assert response.route_plan_shadow.candidate_available is False
    assert response.route_plan_shadow.candidate_reason == "live_llm_routing_disabled"
    assert response.route_plan_shadow.execution_authorized is False
    assert response.route_plan_shadow.llm_called is False
    assert response.route_plan_shadow.reasoning_model_used is False


def test_route_plan_shadow_does_not_call_live_llm_by_default(monkeypatch) -> None:
    calls = {"candidate": 0}

    def no_candidate(query: str) -> None:
        calls["candidate"] += 1
        return None

    _patch_common_chat_dependencies(monkeypatch, skill="knowledge_recall")
    monkeypatch.setattr("app.api.routes_chat._route_plan_shadow_candidate", no_candidate)

    response = chat(ChatRequest(message="Which SOP covers brute force authentication?"))

    assert calls["candidate"] == 1
    assert response.candidate_spl is None
    assert response.route_plan_shadow is not None
    assert response.route_plan_shadow.llm_called is False
    assert response.route_plan_shadow.model_role == "instruct_candidate_only"
    assert response.route_plan_shadow.candidate_reason == "live_llm_routing_disabled"


def test_route_plan_shadow_does_not_authorize_spl_or_mcp(monkeypatch) -> None:
    _patch_common_chat_dependencies(monkeypatch, skill="knowledge_recall")

    response = chat(ChatRequest(message="Which SOP covers brute force authentication?"))

    assert response.candidate_spl is None
    assert response.execution is not None
    assert response.execution.status == "skipped"
    assert response.route_plan_shadow is not None
    assert response.route_plan_shadow.execution_authorized is False
    assert response.route_plan_shadow.mcp_called is False
    assert response.route_plan_shadow.spl_generated is False
    assert response.route_plan_shadow.spl_executed is False


def test_missing_notable_preflight_visible_in_route_plan_shadow(monkeypatch) -> None:
    _patch_common_chat_dependencies(monkeypatch, skill="knowledge_recall")

    response = chat(ChatRequest(message="What happened for this notable?"))

    assert response.route_plan_shadow is not None
    assert response.route_plan_shadow.preflight_status == "clarification_required"
    assert response.route_plan_shadow.route_status == "clarification_required"
    assert "notable_id" in response.route_plan_shadow.missing_slots
    assert response.route_plan_shadow.candidate_available is False
    assert response.route_plan_shadow.execution_authorized is False


def test_missing_ioc_lookup_visible_in_route_plan_shadow(monkeypatch) -> None:
    _patch_common_chat_dependencies(monkeypatch, skill="knowledge_recall")

    response = chat(ChatRequest(message="Which hosts contacted known malicious IPs today?"))

    assert response.route_plan_shadow is not None
    assert response.route_plan_shadow.preflight_status == "cannot_route_missing_lookup"
    assert response.route_plan_shadow.route_status == "cannot_route_missing_lookup"
    assert "lookup_ref" in response.route_plan_shadow.missing_slots
    assert response.route_plan_shadow.mcp_called is False
    assert response.route_plan_shadow.spl_executed is False


def test_mock_candidate_validation_path_is_observational(monkeypatch) -> None:
    _patch_common_chat_dependencies(monkeypatch, skill="knowledge_recall")
    monkeypatch.setattr("app.api.routes_chat._route_plan_shadow_candidate", lambda query: _valid_route_plan_candidate())

    response = chat(ChatRequest(message="Find the top 10 users with failed Okta login attempts in the last 24 hours."))

    assert response.candidate_spl is None
    assert response.route_plan_shadow is not None
    assert response.route_plan_shadow.candidate_available is True
    assert response.route_plan_shadow.validation_result == {"is_valid": True}
    assert response.route_plan_shadow.route_status == "route_ready"
    assert response.route_plan_shadow.primary_skill == "aggregate_and_rank"
    assert response.route_plan_shadow.pattern_id == "top_failed_okta_login_users"
    assert response.route_plan_shadow.normalized_plan_available is True
    assert response.route_plan_shadow.execution_authorized is False
    assert response.route_plan_shadow.mcp_called is False
    assert response.route_plan_shadow.spl_generated is False


def test_mock_candidate_confidence_does_not_make_invalid_plan_valid(monkeypatch) -> None:
    invalid = _valid_route_plan_candidate()
    invalid["parameters"].pop("group_by")
    invalid["model_advisory_metadata"] = {"model_self_reported_confidence": "high"}
    _patch_common_chat_dependencies(monkeypatch, skill="knowledge_recall")
    monkeypatch.setattr("app.api.routes_chat._route_plan_shadow_candidate", lambda query: invalid)

    response = chat(ChatRequest(message="Find the top 10 users with failed Okta login attempts in the last 24 hours."))

    assert response.route_plan_shadow is not None
    assert response.route_plan_shadow.validation_result == {"is_valid": False}
    assert response.route_plan_shadow.route_status == "blocked_invalid_parameters"
    assert "missing_required_slot:group_by" in response.route_plan_shadow.blocking_findings
    assert "model_self_reported_confidence_ignored_for_validation" in response.route_plan_shadow.validation_findings
    assert response.route_plan_shadow.execution_authorized is False


def test_experience_center_route_plan_shadow_unchanged() -> None:
    response = run_demo_scenario_fixture("failed_login_spike_app01")

    assert response.route_plan_shadow is None
    assert response.demo_mode is True
    assert response.evidence_origin == "coe_synthetic_fixture"


def _patch_common_chat_dependencies(monkeypatch, *, skill: str) -> None:
    telemetry = FakeTelemetry()
    monkeypatch.setattr("app.api.routes_chat.route_skill", lambda query, trace_id: _routed(skill))
    monkeypatch.setattr("app.api.routes_chat.plan_workflow", fake_plan_workflow)
    monkeypatch.setattr("app.api.routes_chat.get_telemetry_connector", lambda: telemetry)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: telemetry)


def _routed(skill: str) -> dict[str, Any]:
    return {
        "skill": skill,
        "tool_plan": ["route_only", skill],
        "confidence": 0.91,
        "comparison": {"match": True, "skill_match": True, "tool_plan_match": True},
    }


def _valid_route_plan_candidate() -> dict[str, Any]:
    return {
        "route_plan_id": "rp_stage3k_r2_test",
        "route_status": "route_ready",
        "primary_skill": "aggregate_and_rank",
        "pattern_id": "top_failed_okta_login_users",
        "operation_type": "top_n",
        "domain": "soc",
        "source_class": "okta_authentication_logs",
        "entities": ["user"],
        "time_window": "last 24 hours",
        "parameters": {
            "event_filter": {"event_type": "failed_login"},
            "group_by": {"field": "user", "source_class": "okta_authentication_logs"},
            "metric": {"type": "count", "field": "failed_login_count"},
            "sort": {"field": "metric_value", "direction": "desc"},
            "limit": 10,
            "time_window": "last 24 hours",
            "exclude_entities": "service_accounts",
        },
        "missing_slots": [],
        "hard_preconditions": [],
        "model_advisory_metadata": {},
        "deterministic_validation": {"validator": "stage3k_r1"},
        "post_enrichment": ["notable_risk_lookup"],
    }


class FakeTelemetry:
    def __init__(self) -> None:
        self.steps: list[dict[str, Any]] = []
        self.spl_validations: list[dict[str, Any]] = []
        self.mcp_executions: list[dict[str, Any]] = []

    def record_step(self, trace_id: str, step_name: str, status: str, **fields: Any) -> None:
        self.steps.append({"trace_id": trace_id, "step_name": step_name, "status": status, **fields})

    def record_spl_validation(self, trace_id: str, **fields: Any) -> None:
        self.spl_validations.append({"trace_id": trace_id, **fields})

    def record_mcp_execution(self, trace_id: str, **fields: Any) -> None:
        self.mcp_executions.append({"trace_id": trace_id, **fields})

    def record_routing_decision(self, trace_id: str, **fields: Any) -> None:
        pass

    def record_routing_disagreement(self, trace_id: str, **fields: Any) -> None:
        pass


def fake_plan_workflow(selected_skill: str, tool_plan: list[str], query: str, trace_id: str) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "skill": selected_skill,
        "tool_plan": tool_plan,
        "status": "not_started",
        "execution_enabled": False,
        "steps": [
            {
                "order": 1,
                "name": "test workflow plan",
                "status": "not_started",
                "required_connectors": [],
                "safety_gates": ["no_execution"],
            }
        ],
        "required_connectors": [],
        "safety_gates": ["no_execution"],
        "message": "Workflow plan created. No SPL/MCP/RAG execution has started.",
    }
