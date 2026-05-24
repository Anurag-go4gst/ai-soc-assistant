from __future__ import annotations

from typing import Any

from app.api.routes_chat import _context_stage
from app.evidence.context_structurer import structure_context
from app.evidence.context_sufficiency import check_context_sufficiency
from app.evidence.source_evidence import build_source_evidence


APPROVED_VALIDATION = {
    "approved": True,
    "normalized_spl": "search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | stats count by user | head 100",
    "reject_reasons": [],
    "warnings": [],
    "enforced_limits": {"max_result_limit": 100},
    "policy_version": "spl-policy-v1",
}


EXECUTED = {
    "status": "executed",
    "execution_intent": "spl_search",
    "selected_mcp_server": "splunk_soc",
    "selected_mcp_tool": "run_splunk_query",
    "tool_selection_status": "selected",
    "tool_selection_reason": "allowlisted_spl_search_tool_selected",
    "executed_spl": APPROVED_VALIDATION["normalized_spl"],
    "result_count": 10,
    "results_preview": [
        {"user": "svc_app", "fail_count": 184},
        {"user": "admin", "fail_count": 22},
        {"user": "ops", "fail_count": 19},
        {"user": "backup", "fail_count": 11},
        {"user": "vpn", "fail_count": 8},
        {"user": "extra", "fail_count": 1},
    ],
    "block_reason": None,
    "duration_ms": 3,
}


BLOCKED = {
    "status": "requires_human_review",
    "execution_intent": "spl_search",
    "selected_mcp_server": "splunk_soc",
    "selected_mcp_tool": "run_splunk_query",
    "tool_selection_status": "selected",
    "tool_selection_reason": "allowlisted_spl_search_tool_selected",
    "executed_spl": None,
    "result_count": 0,
    "results_preview": [],
    "block_reason": "mcp_global_execution_disabled",
    "duration_ms": 0,
}


WORKFLOW = {
    "trace_id": "trace-evidence",
    "skill": "attack_discovery",
    "tool_plan": ["route_only", "attack_discovery"],
    "status": "not_started",
    "execution_enabled": False,
    "steps": [],
    "required_connectors": ["mcp"],
    "safety_gates": ["validated_spl_only_to_mcp"],
    "required_sources": ["mcp:splunk"],
    "available_sources": [],
    "missing_sources": ["mcp:splunk"],
    "message": "Workflow plan created.",
}


def test_mcp_executed_response_creates_source_evidence() -> None:
    evidence = build_source_evidence(
        trace_id="trace-executed",
        query="failed logins",
        selected_skill="attack_discovery",
        spl_validation=APPROVED_VALIDATION,
        execution=EXECUTED,
    )

    item = evidence[0]
    assert item["source_type"] == "splunk_mcp"
    assert item["source_name"] == "splunk_soc"
    assert item["tool_name"] == "run_splunk_query"
    assert item["collection_status"] == "collected"
    assert item["executed_spl"] == APPROVED_VALIDATION["normalized_spl"]
    assert item["result_count"] == 10
    assert item["fields_returned"] == ["user", "fail_count"]
    assert len(item["preview_rows"]) == 5
    assert item["raw_result_hash"]
    assert item["raw_result_stored"] is False


def test_blocked_execution_creates_blocked_source_evidence() -> None:
    evidence = build_source_evidence(
        trace_id="trace-blocked",
        query="failed logins",
        selected_skill="attack_discovery",
        spl_validation=APPROVED_VALIDATION,
        execution=BLOCKED,
    )

    assert evidence[0]["collection_status"] == "blocked"
    assert evidence[0]["executed_spl"] is None
    assert evidence[0]["result_count"] == 0
    assert evidence[0]["warnings"] == ["mcp_global_execution_disabled"]


def test_structured_facts_include_source_refs() -> None:
    evidence = build_source_evidence(
        trace_id="trace-context",
        query="failed logins",
        selected_skill="attack_discovery",
        spl_validation=APPROVED_VALIDATION,
        execution=EXECUTED,
    )
    context = structure_context(
        query="failed logins",
        trace_id="trace-context",
        selected_skill="attack_discovery",
        workflow_plan=WORKFLOW,
        spl_validation=APPROVED_VALIDATION,
        execution=EXECUTED,
        source_evidence=evidence,
    )

    assert context["synthesis_allowed"] is False
    assert context["structured_facts"]
    assert all(fact["source_refs"] for fact in context["structured_facts"])
    assert context["metrics"]["total_result_count"] == 10


def test_facts_without_source_refs_fail_sufficiency() -> None:
    context = {
        "context_quality": "partial",
        "missing_evidence": [],
        "structured_facts": [{"fact_id": "fact_bad", "statement": "bad", "source_refs": []}],
    }

    result = check_context_sufficiency(context, [{"collection_status": "collected", "sensitivity_flags": []}])

    assert result["status"] == "fail"
    assert result["synthesis_allowed"] is False
    assert "structured_fact_missing_source_refs" in result["reasons"]


def test_context_quality_blocked_when_execution_blocked() -> None:
    evidence = build_source_evidence(
        trace_id="trace-blocked-context",
        query="failed logins",
        selected_skill="attack_discovery",
        spl_validation=APPROVED_VALIDATION,
        execution=BLOCKED,
    )
    context = structure_context(
        query="failed logins",
        trace_id="trace-blocked-context",
        selected_skill="attack_discovery",
        workflow_plan=WORKFLOW,
        spl_validation=APPROVED_VALIDATION,
        execution=BLOCKED,
        source_evidence=evidence,
    )
    sufficiency = check_context_sufficiency(context, evidence)

    assert context["context_quality"] == "blocked"
    assert context["synthesis_allowed"] is False
    assert sufficiency["status"] == "requires_human_review"
    assert sufficiency["synthesis_allowed"] is False


def test_context_stage_records_telemetry_without_llm_rag_or_splunk_write(monkeypatch) -> None:
    telemetry = FakeTelemetry()
    monkeypatch.setattr("app.api.routes_chat.get_telemetry_connector", lambda: telemetry)

    evidence, context, sufficiency = _context_stage(
        trace_id="trace-stage",
        query="failed logins",
        selected_skill="attack_discovery",
        workflow_plan=WORKFLOW,
        spl_validation=APPROVED_VALIDATION,
        execution=EXECUTED,
    )

    assert evidence[0]["collection_status"] == "collected"
    assert context["synthesis_allowed"] is False
    assert sufficiency["synthesis_allowed"] is False
    assert [step["step_name"] for step in telemetry.steps] == [
        "source_evidence_created",
        "context_structured",
        "context_sufficiency_checked",
    ]
    assert not hasattr(telemetry, "record_llm_call_called")
    assert not hasattr(telemetry, "record_rag_retrieval_called")
    assert not hasattr(telemetry, "splunk_write")


class FakeTelemetry:
    def __init__(self) -> None:
        self.steps: list[dict[str, Any]] = []

    def record_step(self, trace_id: str, step_name: str, status: str, **fields: Any) -> None:
        self.steps.append({"trace_id": trace_id, "step_name": step_name, "status": status, **fields})
