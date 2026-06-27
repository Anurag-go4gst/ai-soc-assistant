"""Phase 7 — MCP seam hardening: off/mock share the same ResourcePlan MCP step."""

from __future__ import annotations

from typing import Any

import pytest

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.evidence_loop import ROUTE_BROADEN, ROUTE_FINALIZE, assess_loop, initialize_loop
from app.chat.pipeline import build_live_chat_response
from app.chat.run_contract_builder import (
    build_route_contract,
    build_run_contract,
    enrich_run_contract_payload,
    project_mcp_posture,
)
from app.config import settings
from app.evidence.source_evidence import build_source_evidence
from app.orchestration.mcp_execution_gate import evaluate_mcp_execution
from app.orchestration.mcp_tool_selector import select_mcp_tool
from app.planner.composer import compose_resource_plan
from app.planner.executor import annotate_step_statuses
from app.schemas.requests import ChatRequest

_LIVE_EVIDENCE_QUERY = "Show me privileged VPN sessions from last night"
_HYBRID_QUERY = (
    "Find accounts failing login in the last 24 hours, exclude service accounts, "
    "and tell me what analyst action I should take"
)

_APPROVED_SPL = {
    "approved": True,
    "normalized_spl": (
        "search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now "
        "| stats count by user | head 100"
    ),
    "reject_reasons": [],
    "warnings": [],
    "policy_version": "spl-policy-v1",
}

_FAILED_SPL = {**_APPROVED_SPL, "approved": False, "normalized_spl": None, "reject_reasons": ["missing_result_limit"]}


@pytest.fixture(autouse=True)
def _control_plane_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)


def _live_investigation_plan(*, mcp_allowed: bool = False) -> EvidencePlan:
    return EvidencePlan(
        answer_mode="live_investigation",
        rag_phase="post_mcp",
        needs_rag=False,
        needs_spl=True,
        needs_mcp=True,
        needs_mitre=False,
        spl_allowed=True,
        mcp_allowed=mcp_allowed,
        policy_context_required=False,
        policy_context_recommended=False,
    )


def _chat_payload(question: str) -> dict[str, Any]:
    return build_live_chat_response(ChatRequest(message=question)).model_dump(mode="json")


def _mcp_step_from_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    steps = ((payload.get("evidence_plan") or {}).get("resource_plan") or {}).get("steps") or []
    for step in steps:
        if isinstance(step, dict) and step.get("purpose") == "mcp_execution":
            return step
    return None


def _planned_mcp_identity() -> tuple[str, str, str]:
    composed = compose_resource_plan(
        _live_investigation_plan(mcp_allowed=True),
        intent_family="live_investigation",
        skill_id="attack_discovery",
    )
    mcp = composed.step_by_id("mcp")
    assert mcp is not None
    return (mcp.step_id, mcp.resource_id, mcp.purpose)


def _enable_mock_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", True)
    monkeypatch.setattr(settings, "mcp_server_mock_execution_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_demo_or_lab_execution_mode", True)
    monkeypatch.setattr(settings, "ai_soc_allow_mock_execution_without_hil_in_demo", True)
    monkeypatch.setattr(settings, "ai_soc_require_spl_execution_confirmation", False)


class _FakeTelemetry:
    def record_mcp_execution(self, trace_id: str, **fields: Any) -> None:
        return None


class _Connector:
    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        self.payload = payload or {
            "status": "ok",
            "row_count": 1,
            "rows": [{"user": "svc_app", "fail_count": 3}],
        }
        self.arguments: dict[str, Any] | None = None

    def call_tool(self, tool_name: str, arguments: dict[str, Any], server_name: str | None = None) -> dict[str, Any]:
        self.arguments = arguments
        return self.payload


def test_composer_emits_blocked_mcp_step_when_off_and_live_evidence_needed() -> None:
    composed = compose_resource_plan(
        _live_investigation_plan(mcp_allowed=False),
        intent_family="live_investigation",
        skill_id="attack_discovery",
    )
    mcp_steps = [step for step in composed.steps if step.purpose == "mcp_execution"]
    assert len(mcp_steps) == 1
    step = mcp_steps[0]
    assert step.step_id == "mcp"
    assert step.status == "blocked_policy"
    assert "mcp_not_allowed_by_evidence_plan" in step.policy_checks


def test_mcp_off_preserves_planned_resource_step_and_block_reason() -> None:
    payload = _chat_payload(_LIVE_EVIDENCE_QUERY)
    mcp = _mcp_step_from_payload(payload)
    assert mcp is not None
    assert mcp.get("step_id") == "mcp"
    assert mcp.get("status") in {"blocked_policy", "blocked", "skipped", "not_run"}

    normalized = (payload.get("evidence_plan") or {}).get("mcp_allowed_normalized") or {}
    assert normalized.get("allowed") is False
    assert normalized.get("reason") == "explicit_false"

    trace = payload.get("control_plane_trace") or {}
    mcp_trace = trace.get("mcp_execution") or {}
    assert mcp_trace.get("block_reason") == "mcp_not_allowed_by_evidence_plan"

    routing = (payload.get("run_contract") or {}).get("routing") or {}
    assert routing.get("canonical_skill") == "spl_generation"
    assert routing.get("live_data_request") is True


def test_mcp_allowed_null_normalizes_fail_closed_before_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    from app.chat.pipeline import _mcp_allowed_decision_from_plan

    decision = _mcp_allowed_decision_from_plan({"needs_mcp": True, "mcp_allowed": None})
    assert decision["allowed"] is False
    assert decision["reason"] == "mcp_allowed_null_fail_closed"


def test_mock_mcp_executes_same_resource_plan_step(monkeypatch: pytest.MonkeyPatch) -> None:
    planned_identity = _planned_mcp_identity()
    plan = _live_investigation_plan(mcp_allowed=True)
    composed = compose_resource_plan(plan, intent_family="live_investigation", skill_id="attack_discovery")

    _enable_mock_execution(monkeypatch)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: _Connector())

    execution, review = evaluate_mcp_execution(
        trace_id="phase7-mock",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=_APPROVED_SPL,
        precondition_evaluation={"evaluation_skipped": True},
    )
    assert execution["status"] == "executed"
    assert review["required"] is False

    state = annotate_step_statuses(
        {
            "evidence_plan": {**plan.model_dump(), "resource_plan": composed.model_dump()},
            "execution": execution,
            "spl_validation": _APPROVED_SPL,
        }
    )
    mcp = next(
        step
        for step in state["evidence_plan"]["resource_plan"]["steps"]
        if step["purpose"] == "mcp_execution"
    )
    assert (mcp["step_id"], mcp["resource_id"], mcp["purpose"]) == planned_identity
    assert mcp["status"] == "executed"
    posture = project_mcp_posture(state)
    assert posture is not None
    assert posture["execution_authorized"] is True
    assert posture["status"] == "executed"


def test_mcp_gate_rejects_without_approved_normalized_spl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    execution, review = evaluate_mcp_execution(
        trace_id="phase7-spl-fail",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=_FAILED_SPL,
    )
    assert execution["executed_spl"] is None
    assert execution["status"] == "requires_human_review"
    assert review["review_type"] == "spl_revision"


def test_mcp_gate_rejects_when_global_flag_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MCP_GLOBAL_EXECUTION_ENABLED", raising=False)
    monkeypatch.delenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", raising=False)
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", False)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())

    execution, review = evaluate_mcp_execution(
        trace_id="phase7-global-off",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=_APPROVED_SPL,
    )
    assert execution["block_reason"] == "mcp_global_execution_disabled"
    assert review["review_type"] == "execution_approval"


def test_mcp_gate_rejects_disallowed_tool_even_if_llm_suggests_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")

    selection = select_mcp_tool(
        trace_id="phase7-llm-tool",
        selected_skill="attack_discovery",
        workflow_plan={},
        execution_intent="spl_search",
        spl_validation=_APPROVED_SPL,
        user_requested_mcp_tool="saia_generate_spl",
        llm_tool_recommendation={"tool_name": "saia_generate_spl", "tool_category": "spl_search"},
    )
    assert selection["tool_selection_status"] == "requires_human_review"
    assert selection["blocked_reason"] == "requested_tool_intent_mismatch"


def test_mcp_result_enters_source_evidence_not_llm_context(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_mock_execution(monkeypatch)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: _Connector())

    execution, _review = evaluate_mcp_execution(
        trace_id="phase7-source-evidence",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=_APPROVED_SPL,
        precondition_evaluation={"evaluation_skipped": True},
    )
    evidence = build_source_evidence(
        trace_id="phase7-source-evidence",
        query=_HYBRID_QUERY,
        selected_skill="attack_discovery",
        spl_validation=_APPROVED_SPL,
        execution=execution,
        soc_kb_retrieval={"retrieval_status": "no_match", "chunks": []},
        include_skipped_mcp_placeholder=False,
    )
    collected = [item for item in evidence if item.get("collection_status") == "collected"]
    assert collected, "mock execution must surface collected SourceEvidence rows"
    assert all(item.get("source_type") != "llm_context" for item in collected)
    assert all(item.get("source_type") in {"splunk_mcp", "mcp_execution", "mock_mcp"} for item in collected)


def test_empty_mcp_result_triggers_bounded_broaden_or_honest_empty_state(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_mock_execution(monkeypatch)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: _Connector({"status": "ok", "row_count": 0, "rows": []}))

    execution, _review = evaluate_mcp_execution(
        trace_id="phase7-empty",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=_APPROVED_SPL,
        precondition_evaluation={"evaluation_skipped": True},
    )
    assert execution["status"] == "executed"
    assert execution.get("result_count") == 0

    state = initialize_loop(["splunk_run_query"])
    broaden = assess_loop(state, execution=execution, broaden_eligible=True)
    assert broaden.route == ROUTE_BROADEN

    finalize = assess_loop(state, execution=execution, broaden_eligible=False)
    assert finalize.route == ROUTE_FINALIZE


def test_chat_mcp_off_run_contract_and_gate_agree_on_blocked_posture() -> None:
    payload = _chat_payload(_LIVE_EVIDENCE_QUERY)
    contract = payload.get("run_contract") or {}
    gate = (payload.get("structured_context") or {}).get("final_evidence_gate") or {}
    posture = contract.get("mcp_posture") or {}

    assert contract.get("mcp_allowed") is False
    assert contract.get("execution_authorized") is False
    assert contract.get("collected_evidence_count") == 0
    assert contract.get("allow_live_result_language") is False
    assert gate.get("collected_evidence_count") == contract.get("collected_evidence_count")
    assert gate.get("allow_live_result_language") is contract.get("allow_live_result_language")
    assert posture.get("execution_authorized") is False


def test_chat_global_mcp_disabled_trace_records_global_flag_block(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", False)
    monkeypatch.setattr(settings, "mcp_server_mock_execution_enabled", False)
    payload = _chat_payload(_HYBRID_QUERY)
    trace = payload.get("control_plane_trace") or {}
    mcp_trace = trace.get("mcp_execution") or {}
    # Hybrid allows MCP at EvidencePlan level; global flag still blocks at gate.
    assert (payload.get("evidence_plan") or {}).get("mcp_allowed") is True
    assert mcp_trace.get("block_reason") in {
        "mcp_global_execution_disabled",
        "precondition_eval_failed",
        "mcp_not_allowed_by_evidence_plan",
    }
    contract = payload.get("run_contract") or {}
    assert contract.get("execution_authorized") is False


def test_mock_execution_run_contract_collected_count_from_source_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_mock_execution(monkeypatch)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: _Connector())

    plan = _live_investigation_plan(mcp_allowed=True)
    composed = compose_resource_plan(plan, intent_family="live_investigation", skill_id="attack_discovery")
    execution, _review = evaluate_mcp_execution(
        trace_id="phase7-contract",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation=_APPROVED_SPL,
        precondition_evaluation={"evaluation_skipped": True},
    )
    state = annotate_step_statuses(
        {
            "evidence_plan": {**plan.model_dump(), "resource_plan": composed.model_dump()},
            "execution": execution,
            "spl_validation": _APPROVED_SPL,
            "routed": {"selected_skill": "attack_discovery"},
            "intent_classification": {"intent_family": "live_investigation"},
        }
    )
    source_evidence = build_source_evidence(
        trace_id="phase7-contract",
        query=_HYBRID_QUERY,
        selected_skill="attack_discovery",
        spl_validation=_APPROVED_SPL,
        execution=execution,
        soc_kb_retrieval={"retrieval_status": "no_match", "chunks": []},
        include_skipped_mcp_placeholder=False,
    )
    state = {**state, "source_evidence": source_evidence}
    route = build_route_contract(state)
    contract = build_run_contract(state, route=route)
    payload = enrich_run_contract_payload(contract.model_dump(mode="json"), state)
    assert payload["collected_evidence_count"] >= 1
    assert payload["allow_live_result_language"] is True
    assert payload["mcp_posture"]["execution_authorized"] is True
