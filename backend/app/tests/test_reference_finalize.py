from __future__ import annotations

from typing import Any

import pytest

from app.chat.pipeline import _resolve_reference_knowledge, build_live_chat_response
from app.config import settings
from app.graph.resource_planner_graph import run_chat_via_resource_planner_graph
from app.schemas.requests import ChatRequest


P1_ATLAS = "What MITRE ATLAS techniques apply to prompt injection against our LLM agent using MCP tools?"
P4_CVE = "Explain CVE-2024-3400. Are we affected?"


@pytest.fixture(autouse=True)
def _offline_reference_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEMETRY_MODE", "none")
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_answer_guard_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_utility_spl_draft_enabled", False)


def _payload(response: Any) -> dict[str, Any]:
    return response.model_dump(mode="json")


def _reference_ids(payload: dict[str, Any]) -> list[str]:
    facts = ((payload.get("analyst_response") or {}).get("reference_facts") or [])
    return [str(item.get("reference_id") or "") for item in facts if isinstance(item, dict)]


def test_reference_resolver_returns_grounded_atlas_facts() -> None:
    resolution = _resolve_reference_knowledge(P1_ATLAS)
    facts = resolution["facts"]
    assert facts
    assert all(str(fact["reference_id"]).startswith("AML.T") for fact in facts)
    assert all(fact.get("name") for fact in facts[:3])
    assert all(fact.get("citation") for fact in facts[:3])


def test_reference_finalize_adds_source_context_and_visible_atlas_answer() -> None:
    payload = _payload(build_live_chat_response(ChatRequest(message=P1_ATLAS)))
    summary = str((payload.get("analyst_response") or {}).get("direct_answer_summary") or "")
    source_evidence = payload.get("source_evidence") or []
    structured = payload.get("structured_context") or {}

    assert "reference_finalize" in ((payload.get("control_plane_trace") or {}).get("plan_dispatch") or {}).get(
        "dispatch_schedule", []
    )
    assert any(item.get("source_type") == "reference_dataset" for item in source_evidence)
    assert any(str(item.get("reference_id") or "").startswith("AML.T") for item in structured.get("reference_facts") or [])
    assert any(reference_id.startswith("AML.T") for reference_id in _reference_ids(payload))
    assert "LLM Prompt Crafting" in summary
    assert "MITRE ATLAS reference bundle" in summary or "ATLAS.yaml" in summary
    assert "alert context before mapping" not in summary.lower()
    assert (payload.get("candidate_spl") or {}).get("candidate_spl") in {None, ""}
    assert (payload.get("execution") or {}).get("status") != "executed"


def test_reference_finalize_reports_cve_snapshot_gap_without_exposure_claim() -> None:
    payload = _payload(build_live_chat_response(ChatRequest(message=P4_CVE)))
    summary = str((payload.get("analyst_response") or {}).get("direct_answer_summary") or "").lower()

    assert _reference_ids(payload) == ["CVE-2024-3400"]
    assert "not found in the local cve snapshot" in summary
    assert "reference taxonomy only" in summary or "not confirmed activity" in summary
    assert (payload.get("human_review") or {}).get("required") is False


def test_resource_planner_reference_finalize_uses_reference_path() -> None:
    payload = _payload(run_chat_via_resource_planner_graph(ChatRequest(message=P1_ATLAS)))
    trace = ((payload.get("control_plane_trace") or {}).get("plan_dispatch") or {})

    assert trace.get("dispatch_schedule") == ["prepare_rag_only", "rag_early", "reference_finalize"]
    assert any(reference_id.startswith("AML.T") for reference_id in _reference_ids(payload))
    assert "LLM Prompt Crafting" in str(
        (payload.get("analyst_response") or {}).get("direct_answer_summary") or ""
    )
