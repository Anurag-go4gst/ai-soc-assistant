from __future__ import annotations

import json

import pytest

from app.api.routes_chat import chat
from app.api.routes_knowledge import intake_contract, import_prompt_template
from app.evidence.context_structurer import structure_context
from app.evidence.source_evidence import build_source_evidence
from app.knowledge.rag_evidence_lineage import (
    EVIDENCE_ORIGIN_STUB_RAG,
    classify_rag_evidence_origin,
    resolve_response_evidence_origin,
)
from app.knowledge.soc_kb_intake_template import soc_kb_intake_contract
from app.knowledge.soc_kb_retriever import retrieve_soc_kb
from app.schemas.requests import ChatRequest
from app.tests.test_route_plan_stage3k_r2 import _patch_common_chat_dependencies

APPROVED_VALIDATION = {
    "approved": True,
    "normalized_spl": "index=okta | stats count by user",
    "reject_reasons": [],
    "warnings": [],
    "policy_version": "test",
}
EXECUTION = {
    "status": "skipped",
    "execution_intent": "spl_search",
    "selected_mcp_server": None,
    "selected_mcp_tool": None,
    "executed_spl": None,
    "result_count": 0,
    "results_preview": [],
    "block_reason": "mcp_global_execution_disabled",
    "duration_ms": 0,
}
WORKFLOW = {"required_sources": ["rag:sop"], "steps": []}


def _enable_soc_kb(monkeypatch: pytest.MonkeyPatch) -> None:
    for target in (
        "app.config.settings",
        "app.knowledge.soc_kb_retriever.settings",
        "app.knowledge.rag_evidence_lineage.settings",
    ):
        monkeypatch.setattr(f"{target}.soc_kb_retrieval_enabled", True)
        monkeypatch.setattr(f"{target}.rag_mode", "mock")
        monkeypatch.setattr(f"{target}.soc_kb_repository_backend", "json")


def test_p4_9_intake_contract_exposes_schema_and_approval_metadata() -> None:
    contract = soc_kb_intake_contract()
    assert contract["schema_version"] == "p4_soc_kb_intake_v1"
    assert contract["direct_rag_to_llm"] is False
    assert "coe_reviewed" in contract["runtime_approval_statuses"]
    assert "sop" in contract["supported_document_types"]


def test_intake_contract_route_matches_module() -> None:
    route_payload = intake_contract()
    assert route_payload["human_review_required"] is True
    assert "POST /api/knowledge/import/publish" in route_payload["api_surfaces"]


def test_import_prompt_template_returns_p4_bundle() -> None:
    payload = import_prompt_template(collection_id="soc_sop", document_type="sop")
    assert payload["schema_version"] == "p4_soc_kb_intake_v1"
    assert "prompt" in payload
    assert payload["runtime_use"] is False


def test_retrieval_marks_stub_rag_for_fixture_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_soc_kb(monkeypatch)
    retrieval = retrieve_soc_kb(
        query="brute force failed login spike",
        selected_skill="attack_discovery",
        allowed_use=["hil_guidance"],
    )
    assert retrieval["evidence_origin"] == EVIDENCE_ORIGIN_STUB_RAG
    assert retrieval["direct_to_llm"] is False
    summary = retrieval["rag_approval_summary"]
    assert summary["enabled"] is True
    assert summary["direct_to_llm"] is False
    if retrieval["retrieved_entries"]:
        assert "coe_reviewed" in summary["approval_statuses"]


def test_rag_flows_through_source_evidence_and_structured_context(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_soc_kb(monkeypatch)
    retrieval = retrieve_soc_kb(
        query="brute force failed login spike",
        selected_skill="attack_discovery",
        allowed_use=["hil_guidance"],
    )
    evidence = build_source_evidence(
        trace_id="trace-p4",
        query="brute force failed login spike",
        selected_skill="attack_discovery",
        spl_validation=APPROVED_VALIDATION,
        execution=EXECUTION,
        soc_kb_retrieval=retrieval,
    )
    rag = next(item for item in evidence if item["source_type"] == "rag")
    assert rag["evidence_origin"] == EVIDENCE_ORIGIN_STUB_RAG
    assert rag["direct_to_llm"] is False
    assert rag["rag_approval_summary"]["enabled"] is True

    context = structure_context(
        query="brute force failed login spike",
        trace_id="trace-p4",
        selected_skill="attack_discovery",
        workflow_plan=WORKFLOW,
        spl_validation=APPROVED_VALIDATION,
        execution=EXECUTION,
        source_evidence=evidence,
    )
    assert context["rag_approval_summary"] is not None
    assert EVIDENCE_ORIGIN_STUB_RAG in context["evidence_origin_labels"]
    assert context["synthesis_allowed"] is False


def test_live_chat_surfaces_stub_rag_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_soc_kb(monkeypatch)
    monkeypatch.setattr("app.chat.pipeline.settings.soc_kb_retrieval_enabled", True)
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")

    response = chat(ChatRequest(message="brute force failed login spike escalation SOP"))

    assert response.evidence_origin == EVIDENCE_ORIGIN_STUB_RAG
    assert response.answer_readiness in {"system_check_only", "insufficient", "blocked"}
    assert any(item.source_type == "rag" for item in response.source_evidence)
    assert response.structured_context is not None
    assert response.structured_context.rag_approval_summary is not None
    assert EVIDENCE_ORIGIN_STUB_RAG in (response.structured_context.evidence_origin_labels or [])


def test_disabled_retrieval_yields_none_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.soc_kb_retrieval_enabled", False)
    assert classify_rag_evidence_origin(retrieval={"retrieval_status": "disabled"}) == "none"


def test_resolve_response_evidence_origin_prefers_rag_envelope() -> None:
    origin = resolve_response_evidence_origin(
        source_evidence=[
            {
                "source_type": "rag",
                "collection_status": "collected",
                "evidence_origin": EVIDENCE_ORIGIN_STUB_RAG,
            }
        ],
        soc_kb_retrieval=None,
        execution={"status": "skipped"},
    )
    assert origin == EVIDENCE_ORIGIN_STUB_RAG
