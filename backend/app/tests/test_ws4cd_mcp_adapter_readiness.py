"""WS4c/d — Splunk MCP contract, adapter readiness, and resource-plan linkage."""

from __future__ import annotations

from app.chat.intent_classifier import build_query_to_intent
from app.chat.planning_decision import plan_path_and_tools
from app.chat.query_signals import extract_query_signals
from app.config import settings
from app.query_understanding.parser import understand_query
from app.connectors.mcp.splunk_mcp import SplunkMcpConnector
from app.connectors.mcp.splunk_mcp_readiness import (
    ALLOWED_READ_TOOL,
    fixture_splunk_search_call,
    is_disallowed_tool,
    plan_splunk_search_call,
    validate_mcp_result_envelope,
)
from app.connectors.mcp.splunk_result_envelope import SplunkResultEnvelope
from app.orchestration.mcp_execution_gate import evaluate_mcp_execution
from app.planner.composer import compose_resource_plan
from app.planner.mcp_tool_intent import resolve_mcp_tool_intent
from app.planner.resource_registry import load_resource_registry
from app.threat.mitre_evidence_preconditions import cap_mitre_status_for_evidence_tier


APPROVED_SPL = {
    "approved": True,
    "normalized_spl": "search index=pgcil_soc sourcetype=pgcil:auth earliest=-24h latest=now | stats count by user",
}


class _RaisingConnector:
    def call_tool(self, tool_name: str, arguments: dict, server_name: str | None = None) -> dict:
        raise AssertionError("MCP must not be called when execution is disabled")


def test_oos_unsafe_04_run_spl_phrasing_blocked(monkeypatch) -> None:
    query = "Run this SPL now and give me live results: index=* | delete"
    signals = extract_query_signals(query)
    assert signals.get("explicit_run_spl") is True
    assert signals.get("requires_hil") is True

    monkeypatch.setattr(settings, "ai_soc_planner_path_selection_enabled", True)
    qu = understand_query(query)
    q2i = build_query_to_intent(query=query, query_understanding=qu, routed_skill="spl_generation")
    decision = plan_path_and_tools(
        intent_classification=q2i.intent_classification.model_dump(),
        evidence_plan={
            "answer_mode": "live_investigation",
            "needs_spl": True,
            "needs_mcp": True,
            "mcp_allowed": True,
        },
        routed={"skill": "spl_generation"},
        query_understanding=qu,
    )
    assert decision.path_type == "spl_review"
    assert decision.execution_enabled is False
    assert decision.hil_required is True


def test_validated_spl_planned_when_gate_closed(monkeypatch) -> None:
    monkeypatch.delenv("MCP_GLOBAL_EXECUTION_ENABLED", raising=False)
    record = plan_splunk_search_call(
        trace_id="t-plan",
        spl_validation=APPROVED_SPL,
        evidence_plan={"needs_mcp": True, "mcp_allowed": True},
        use_case_id="auth_failed_login_spike",
    )
    assert record.kind == "planned_tool_call"
    assert record.tool_name == ALLOWED_READ_TOOL
    assert record.arguments["search_query"] == APPROVED_SPL["normalized_spl"]
    assert record.failure_mode == "execution_disabled"


def test_mcp_disabled_returns_blocked_not_execution(monkeypatch) -> None:
    monkeypatch.delenv("MCP_GLOBAL_EXECUTION_ENABLED", raising=False)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: _RaisingConnector())
    execution, review = evaluate_mcp_execution(
        trace_id="t-blocked",
        selected_skill="attack_discovery",
        workflow_plan={"execution_enabled": False},
        spl_validation=APPROVED_SPL,
    )
    assert execution["status"] != "executed"
    assert execution.get("block_reason") or review.get("required")


def test_missing_source_profile_blocks_mcp_planning() -> None:
    record = plan_splunk_search_call(
        trace_id="t-profile",
        spl_validation=APPROVED_SPL,
        evidence_plan={
            "needs_mcp": True,
            "mcp_allowed": True,
            "required_evidence_keys": ["active_source_profile"],
        },
        source_profile_missing=True,
    )
    assert record.kind == "blocked_tool_call"
    assert record.failure_mode == "source_profile_missing"


def test_rag_only_skips_mcp() -> None:
    record = plan_splunk_search_call(
        trace_id="t-rag",
        spl_validation=APPROVED_SPL,
        evidence_plan={"answer_mode": "rag_only", "needs_mcp": False},
        path_type="rag_only",
        intent_family="sop_or_playbook",
    )
    assert record.kind == "blocked_tool_call"
    assert record.failure_mode == "rag_only_skip"


def test_unsafe_action_never_plans_mcp() -> None:
    record = plan_splunk_search_call(
        trace_id="t-unsafe",
        spl_validation=APPROVED_SPL,
        evidence_plan={"needs_mcp": True, "mcp_allowed": True},
        path_type="unsafe_blocked",
        signals={"block_or_contain": True},
    )
    assert record.kind == "blocked_tool_call"
    assert record.failure_mode == "unsafe_action_blocked"


def test_empty_mcp_result_honest_negative_not_overclaim() -> None:
    envelope = SplunkResultEnvelope(
        status="empty",
        origin="fixture",
        schema_confirmed=True,
        schema_confirmed_reason="fixture_adapter",
        row_count=0,
        total_row_count=0,
        truncated=False,
        truncation_reason=None,
        fields=(),
        rows=(),
        duration_ms=12,
        error_code=None,
        error_message=None,
        warnings=(),
        provenance="fixture",
    )
    verdict = validate_mcp_result_envelope(envelope)
    assert verdict["failure_mode"] == "empty_result"
    assert verdict.get("negative_result") is True
    assert "compromise" not in (verdict.get("honest_answer") or "").lower()


def test_partial_error_result_review_required() -> None:
    envelope = SplunkResultEnvelope(
        status="timeout",
        origin="mock_connector",
        schema_confirmed=False,
        schema_confirmed_reason="real_schema_unverified",
        row_count=0,
        total_row_count=None,
        truncated=True,
        truncation_reason="timeout",
        fields=("user",),
        rows=({"user": "alice"},),
        duration_ms=30000,
        error_code="timeout",
        error_message="search timed out",
        warnings=("truncated",),
        provenance="mock",
    )
    verdict = validate_mcp_result_envelope(envelope)
    assert verdict["review_required"] is True
    assert verdict["failure_mode"] == "timeout"


def test_schema_mismatch_blocks_evidence_supported_mitre() -> None:
    envelope = SplunkResultEnvelope(
        status="ok",
        origin="mock_connector",
        schema_confirmed=False,
        schema_confirmed_reason="real_schema_unverified",
        row_count=2,
        total_row_count=2,
        truncated=False,
        truncation_reason=None,
        fields=("user",),
        rows=({"user": "alice"}, {"user": "bob"}),
        duration_ms=50,
        error_code=None,
        error_message=None,
        warnings=(),
        provenance="mock",
    )
    verdict = validate_mcp_result_envelope(envelope)
    assert verdict["failure_mode"] == "schema_mismatch"
    assert verdict["evidence_tier"] == "metadata_only"
    assert cap_mitre_status_for_evidence_tier("evidence_supported", "metadata_only") != "evidence_supported"


def test_llm_cannot_choose_mcp_tool_authoritatively() -> None:
    record = plan_splunk_search_call(
        trace_id="t-llm",
        spl_validation=APPROVED_SPL,
        evidence_plan={"needs_mcp": False, "mcp_allowed": False},
        llm_tool_recommendation={"tool_name": "delete_kvstore_collection", "confidence": 0.99},
    )
    assert record.kind == "blocked_tool_call"


def test_resource_planner_maps_auth_investigation_to_splunk_search() -> None:
    from types import SimpleNamespace

    plan = SimpleNamespace(
        needs_mcp=True,
        mcp_allowed=True,
        needs_spl=True,
        needs_rag=False,
        needs_mitre=True,
        rag_phase="post_mcp",
        answer_mode="live_investigation",
        required_evidence_keys=[],
        policy_context_required=False,
    )
    resource_plan = compose_resource_plan(
        plan,
        use_case_id="auth_failed_login_spike",
        registry=load_resource_registry(),
    )
    mcp_steps = [step for step in resource_plan.steps if step.purpose == "mcp_execution"]
    assert mcp_steps
    record = resolve_mcp_tool_intent(
        trace_id="t-map",
        evidence_plan={
            "needs_mcp": True,
            "mcp_allowed": True,
            "answer_mode": "live_investigation",
        },
        resource_plan=resource_plan,
        use_case_id="auth_failed_login_spike",
        spl_validation=APPROVED_SPL,
    )
    assert record.tool_name == ALLOWED_READ_TOOL


def test_fixture_tool_call_produces_envelope_only(monkeypatch) -> None:
    monkeypatch.delenv("MCP_GLOBAL_EXECUTION_ENABLED", raising=False)
    record, envelope = fixture_splunk_search_call(
        trace_id="t-fix",
        normalized_spl=APPROVED_SPL["normalized_spl"],
        fixture_payload={"rows": [{"user": "svc"}], "row_count": 1},
    )
    assert record.kind == "fixture_tool_call"
    assert envelope.row_count == 1


def test_splunk_connector_plan_search_blocked_without_flags(monkeypatch) -> None:
    monkeypatch.delenv("MCP_GLOBAL_EXECUTION_ENABLED", raising=False)
    connector = SplunkMcpConnector()
    plan = connector.plan_search(trace_id="t1", spl_validation=APPROVED_SPL, evidence_plan={"needs_mcp": True})
    assert plan["kind"] == "planned_tool_call"
    blocked = connector.call_tool(ALLOWED_READ_TOOL, plan["arguments"])
    assert blocked["status"] == "blocked"


def test_disallowed_mutating_tools_rejected() -> None:
    assert is_disallowed_tool("create_kvstore_collection")
    assert is_disallowed_tool("splunk.admin.write")
