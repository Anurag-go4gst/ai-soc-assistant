"""Admitted SourceEvidence reaches reasoning hops; untrusted claims do not."""

from __future__ import annotations

import json

from app.chat.investigation_plan_delta_reasoner import (
    build_plan_delta_reasoner_prompt,
    propose_plan_delta,
)
from app.chat.remediation_plan_reasoner import _build_prompt as build_remediation_reasoner_prompt
from app.evidence.governed_reasoning_context import project_source_evidence_for_reasoning
from app.evidence.source_evidence import admit_execution_source_evidence
from app.llm.governed_context_package import build_governed_context_package_for_contract
from app.tests.test_evidence_context import APPROVED_VALIDATION
from app.tests.test_p7_bounded_plan_delta import _envelope
from app.tests.test_p10_remediation_planning import _snapshot
from app.chat.remediation_plan_builder import build_deterministic_remediation_plan
from app.chat.contracts.answer_contract import AnswerContract


def _process_item() -> dict:
    return {
        "evidence_id": "ev_process_1",
        "source_type": "splunk_mcp",
        "collection_status": "collected",
        "result_count": 1,
        "fields_returned": ["host", "process", "user"],
        "query_or_request_summary": "endpoint process execution",
        "preview_rows": [{"host": "WS-14", "process": "powershell.exe", "user": "jdoe"}],
        "executed_spl": "search index=pgcil_soc sourcetype=pgcil:edr",
        "token": "should-never-leak",
    }


def _network_item() -> dict:
    return {
        "evidence_id": "ev_net_1",
        "source_type": "splunk_mcp",
        "collection_status": "collected",
        "result_count": 1,
        "fields_returned": ["src", "dest", "bytes"],
        "query_or_request_summary": "outbound network after process",
        "preview_rows": [{"src": "10.4.2.11", "dest": "198.51.100.88", "bytes": 4096}],
    }


def _rag_item() -> dict:
    return {
        "evidence_id": "ev_rag_1",
        "source_type": "rag",
        "plan_step_ref": "rag",
        "collection_status": "collected",
        "result_count": 1,
        "fields_returned": ["title"],
        "query_or_request_summary": "SOP excerpt",
        "preview_rows": [{"title": "containment playbook"}],
    }


def _user_claim() -> dict:
    return {
        "evidence_id": "ev_user_1",
        "source_type": "manual",
        "collection_status": "skipped",
        "result_count": 0,
        "query_or_request_summary": "analyst said the host is compromised",
        "preview_rows": [],
    }


def _failed_tool() -> dict:
    return {
        "evidence_id": "ev_fail_1",
        "source_type": "splunk_mcp",
        "tool_name": "splunk_run_query",
        "collection_status": "failed",
        "result_count": 0,
        "query_or_request_summary": "timeout",
        "preview_rows": [],
    }


def test_two_environment_families_reach_reasoning() -> None:
    projected = project_source_evidence_for_reasoning([_process_item(), _network_item()])
    joined = " ".join(projected["admitted_environment_evidence"])
    assert "ev_process_1" in joined
    assert "powershell.exe" in joined
    assert "ev_net_1" in joined
    assert "198.51.100.88" in joined
    assert projected["excluded_user_claim_count"] == 0


def test_user_claims_do_not_enter_as_source_evidence() -> None:
    projected = project_source_evidence_for_reasoning([_process_item(), _user_claim()])
    joined = " ".join(projected["admitted_environment_evidence"])
    assert "compromised" not in joined
    assert projected["excluded_user_claim_count"] == 1


def test_failed_tool_calls_are_not_negative_evidence() -> None:
    projected = project_source_evidence_for_reasoning([_failed_tool(), _process_item()])
    assert projected["admitted_environment_evidence"]
    assert "powershell.exe" in projected["admitted_environment_evidence"][0]
    assert projected["failed_tool_observations"]
    assert "not_negative_evidence=true" in projected["failed_tool_observations"][0]
    assert "compromised" not in " ".join(projected["failed_tool_observations"])


def test_rag_is_distinguishable_from_environment_evidence() -> None:
    projected = project_source_evidence_for_reasoning([_process_item(), _rag_item()])
    env = " ".join(projected["admitted_environment_evidence"])
    rag = " ".join(projected["rag_guidance"])
    assert "powershell.exe" in env
    assert "containment playbook" in rag
    assert "containment playbook" not in env
    assert "trust_class=rag_guidance" in rag


def test_sensitive_and_raw_spl_stay_bounded() -> None:
    projected = project_source_evidence_for_reasoning([_process_item()])
    blob = json.dumps(projected)
    assert "should-never-leak" not in blob
    assert "executed_spl" not in blob
    assert "search index=" not in blob


def test_plandelta_prompt_includes_admitted_environment_evidence() -> None:
    prompt = build_plan_delta_reasoner_prompt(
        envelope=_envelope(),
        missing_evidence=["persistence", "external_network"],
        source_evidence=[_process_item(), _rag_item(), _user_claim(), _failed_tool()],
    )
    payload = json.loads(prompt)
    assert payload["admitted_environment_evidence"]
    assert "powershell.exe" in payload["admitted_environment_evidence"][0]
    assert payload["entities"]["user"] == "alice"
    assert payload["rag_guidance"]
    assert "containment playbook" in payload["rag_guidance"][0]
    assert "compromised" not in prompt
    assert payload["failed_tool_observations"]
    result = propose_plan_delta(
        envelope=_envelope(),
        missing_evidence=["persistence"],
        source_evidence=[_process_item()],
        raw_output_provider=lambda: (
            '{"evidence_need":"persistence","capability_id":"mcp:splunk:splunk_run_query",'
            '"access_mode":"read_only","tool_arguments":{"query":'
            '"search index=pgcil_soc sourcetype=pgcil:edr earliest=-24h latest=now | head 100"}}'
        ),
    )
    assert result.trace["admitted_environment_evidence_count"] == 1
    assert result.trace["raw_rows_sent"] is False


def test_remediation_reasoner_receives_governed_rationale() -> None:
    baseline = build_deterministic_remediation_plan(
        investigation_outcome={
            "disposition": "suspicious",
            "investigation_status": "completed",
            "findings": ["Process spawn correlated with outbound connection"],
            "evidence_refs": ["ev_process_1", "ev_net_1"],
            "missing_evidence": [],
            "severity_label": "P2",
            "recommended_actions": ["email_send"],
        },
        capability_snapshot=_snapshot(email_send="available"),
    )
    prompt = build_remediation_reasoner_prompt(
        baseline,
        investigation_outcome={
            "findings": ["Process spawn correlated with outbound connection"],
            "evidence_refs": ["ev_process_1"],
            "missing_evidence": [],
        },
        source_evidence=[_process_item(), _network_item(), _rag_item()],
    )
    payload = json.loads(prompt)
    assert "Process spawn correlated" in payload["governed_findings"][0]
    assert payload["admitted_environment_evidence"]
    assert payload["rag_guidance"]
    assert "token" not in prompt.lower() or "[redacted]" in prompt.lower()


def test_admit_execution_source_evidence_before_plandelta_projection() -> None:
    state = admit_execution_source_evidence(
        {
            "trace_id": "trace-admit-1",
            "effective_query": "investigate powershell on WS-14",
            "routed": {"skill": "guided_investigation"},
            "spl_validation": APPROVED_VALIDATION,
            "execution": {
                "status": "executed",
                "selected_mcp_server": "splunk_soc",
                "selected_mcp_tool": "splunk_run_query",
                "result_count": 1,
                "results_preview": [
                    {"host": "WS-14", "process": "powershell.exe", "parent_process": "WINWORD.EXE"}
                ],
            },
            "source_evidence": [],
        }
    )
    projected = project_source_evidence_for_reasoning(state["source_evidence"])
    assert projected["admitted_environment_evidence"]
    joined = " ".join(projected["admitted_environment_evidence"])
    assert "powershell.exe" in joined or "WS-14" in joined
    assert projected["excluded_user_claim_count"] == 0


def test_admit_execution_preserves_prior_read_when_execution_object_is_replaced() -> None:
    first = admit_execution_source_evidence(
        {
            "trace_id": "trace-admit-2",
            "effective_query": "investigate WS-14",
            "routed": {"skill": "guided_investigation"},
            "spl_validation": APPROVED_VALIDATION,
            "execution": {
                "status": "executed",
                "result_count": 1,
                "results_preview": [{"host": "WS-14", "process": "powershell.exe"}],
            },
        }
    )
    second = admit_execution_source_evidence(
        {
            **first,
            "execution": {
                "status": "executed",
                "result_count": 1,
                "results_preview": [{"host": "WS-14", "dest": "198.51.100.88"}],
            },
        }
    )
    collected = [
        item
        for item in second["source_evidence"]
        if item.get("source_type") == "splunk_mcp" and item.get("collection_status") == "collected"
    ]
    blob = json.dumps(collected)
    assert "powershell.exe" in blob
    assert "198.51.100.88" in blob


def test_governed_package_still_does_not_read_source_evidence_payloads() -> None:
    contract = AnswerContract(
        intent_family="live_investigation",
        answer_mode="live_investigation",
        missing_evidence=["persistence"],
        hil_status="not_required",
    )
    projected = project_source_evidence_for_reasoning([_process_item()])
    pkg = build_governed_context_package_for_contract(
        query="q",
        contract=contract,
        admitted_environment_evidence=projected["admitted_environment_evidence"],
    )
    block = pkg.to_prompt_block()
    assert "powershell.exe" in block
    assert "admitted_environment_evidence" in block
    assert not hasattr(pkg, "source_evidence")
    assert "preview_rows" not in block
