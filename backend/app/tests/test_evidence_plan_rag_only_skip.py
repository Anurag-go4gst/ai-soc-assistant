from __future__ import annotations

from typing import Any

from app.api.routes_chat import chat
from app.chat.pipeline import _candidate_spl_stage, _execution_stage
from app.schemas.requests import ChatRequest


POLICY_QUERY = "What is the escalation policy for repeated failed login alerts?"


def test_control_plane_policy_rag_only_skips_spl_and_mcp(monkeypatch) -> None:
    monkeypatch.setattr("app.config.settings.control_plane_enabled", True)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve_collected)

    response = chat(ChatRequest(message=POLICY_QUERY))

    assert response.evidence_plan is not None
    assert response.evidence_plan["answer_mode"] == "rag_only"
    assert response.evidence_plan["spl_allowed"] is False
    assert response.evidence_plan["mcp_allowed"] is False
    assert response.candidate_spl is None
    assert response.spl_validation is None
    assert response.execution is not None
    assert response.execution.status == "skipped"
    assert response.context_sufficiency is not None
    assert response.context_sufficiency.status == "knowledge_only_answer"
    assert "policy_context_required" in response.context_sufficiency.reasons


def test_control_plane_rag_only_retrieves_soc_kb_once(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []

    def fake_retrieve(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return _fake_retrieve_collected(**kwargs)

    monkeypatch.setattr("app.config.settings.control_plane_enabled", True)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", fake_retrieve)

    response = chat(ChatRequest(message=POLICY_QUERY))

    assert response.evidence_plan is not None
    assert response.evidence_plan["answer_mode"] == "rag_only"
    assert len(calls) == 1
    assert calls[0]["selected_skill"] == "knowledge_recall"


def test_policy_rag_no_match_keeps_insufficient_evidence_with_policy_reasons(monkeypatch) -> None:
    monkeypatch.setattr("app.config.settings.control_plane_enabled", True)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve_no_match)

    response = chat(ChatRequest(message=POLICY_QUERY))

    assert response.context_sufficiency is not None
    assert response.context_sufficiency.status == "insufficient_evidence"
    assert "policy_context_required" in response.context_sufficiency.reasons
    assert "rag_no_match" in response.context_sufficiency.reasons
    assert response.execution is not None
    assert response.execution.status == "skipped"


def test_execution_stage_blocks_mcp_when_evidence_plan_disallows_it() -> None:
    execution, review = _execution_stage(
        trace_id="trace-test",
        selected_skill="attack_discovery",
        workflow_plan={"trace_id": "trace-test"},
        spl_validation={
            "approved": True,
            "normalized_spl": "search index=pgcil_soc sourcetype=pgcil:auth | head 10",
            "reject_reasons": [],
            "warnings": [],
            "enforced_limits": {},
            "policy_version": "test",
        },
        precondition_evaluation=None,
        requested_mcp_server=None,
        requested_mcp_tool=None,
        mcp_allowed=False,
    )

    assert execution["status"] == "skipped"
    assert execution["tool_selection_status"] == "blocked_by_evidence_plan"
    assert execution["block_reason"] == "mcp_not_allowed_by_evidence_plan"
    assert review["required"] is False


def test_candidate_spl_stage_returns_none_when_evidence_plan_disallows_spl() -> None:
    candidate_spl, spl_validation = _candidate_spl_stage(
        trace_id="trace-test",
        skill="attack_discovery",
        user_query="Show top users with failed login count",
        spl_allowed=False,
    )

    assert candidate_spl is None
    assert spl_validation is None


def _fake_retrieve_collected(**kwargs: Any) -> dict[str, Any]:
    return {
        "retrieval_status": "retrieved",
        "retrieved_entries": [
            {
                "entry_id": "kb-policy-auth-1",
                "doc_id": "coe-escalation-auth-v1",
                "document_type": "sop",
                "title": "Repeated failed login escalation",
                "source_excerpt": "Escalate repeated failed login alerts when volume or spread exceeds SOC thresholds.",
                "citation": "COE Sample Auth Escalation Matrix v1.0 ESC-AUTH-002",
                "approval_status": "coe_reviewed",
                "validation_status": "runtime_eligible",
                "recommended_actions": ["review_volume_and_privileged_account_scope"],
            }
        ],
    }


def _fake_retrieve_no_match(**kwargs: Any) -> dict[str, Any]:
    return {
        "retrieval_status": "no_match",
        "retrieved_entries": [],
    }
