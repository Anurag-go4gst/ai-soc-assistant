"""Regression: investigation-plan HIL boundary + guided LLM failure classification."""

from __future__ import annotations

import pytest

from app.actions.capability_policy import action_capability_for
from app.chat.awaiting_investigation_plan_gate import (
    classify_guided_llm_failure,
    is_awaiting_investigation_approval,
    should_treat_guided_skip_as_degraded,
)
from app.chat.guided_investigation_synthesizer import (
    build_guided_llm_degraded_message,
    build_guided_llm_trace,
)
from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.query_understanding.parser import _event_types
from app.schemas.requests import ChatRequest
from app.synthesis.lab_runner import run_governed_synthesis_lab


_SSH_COMPROMISE_QUERY = (
    "We saw 25 failed SSH logins from 198.51.100.42 followed by one successful "
    "login for the same user. Investigate whether this is likely a compromise and "
    "tell me what evidence you need to confirm it."
)


@pytest.fixture(autouse=True)
def _investigation_plan_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_investigation_plan_before_resource_plan_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_investigation_planner_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_investigation_outcome_v2_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_guided_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", True)
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", False)
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)


def test_event_types_preserve_failed_and_successful_ssh() -> None:
    types = _event_types(_SSH_COMPROMISE_QUERY)
    assert "authentication_failure" in types
    assert "authentication_success" in types


def test_synthesis_lab_already_narrated_is_orchestration_not_unavailable() -> None:
    assert classify_guided_llm_failure("synthesis_lab_already_narrated") == "ORCHESTRATION_SKIP"
    assert should_treat_guided_skip_as_degraded("synthesis_lab_already_narrated") is False
    trace = build_guided_llm_trace(
        path_type="guided_investigation",
        composer_trace={"llm_composer_skipped_reason": "synthesis_lab_already_narrated"},
    )
    assert trace.guided_llm_required is True
    assert trace.guided_llm_used is False
    assert trace.guided_llm_degraded_fallback is False
    assert trace.guided_llm_failure_class == "ORCHESTRATION_SKIP"


def test_degraded_message_never_leaks_internal_codes_or_env_vars() -> None:
    msg = build_guided_llm_degraded_message(
        failure_reason="synthesis_lab_already_narrated",
        checklist=["Collect auth logs"],
    )
    assert "synthesis_lab_already_narrated" not in msg
    assert "AI_SOC_GUIDED_LLM_TIMEOUT_SECONDS" not in msg
    assert "planner is unavailable" not in msg.lower()
    assert "No telemetry was queried" in msg

    timeout_msg = build_guided_llm_degraded_message(failure_reason="llm_timed_out")
    assert "timed out" in timeout_msg.lower()
    assert "AI_SOC_" not in timeout_msg

    unavailable_msg = build_guided_llm_degraded_message(failure_reason="provider_unavailable")
    assert "unavailable" in unavailable_msg.lower()
    assert "provider_unavailable" not in unavailable_msg


def test_is_awaiting_investigation_approval_statuses() -> None:
    assert is_awaiting_investigation_approval({"investigation_approval": {"status": "awaiting_approval"}})
    assert is_awaiting_investigation_approval(
        {"canonical_planning_outcome": {"status": "awaiting_investigation_plan"}}
    )
    assert not is_awaiting_investigation_approval({"investigation_approval": {"status": "approved"}})
    assert not is_awaiting_investigation_approval({})


def test_pre_approval_ssh_query_plan_only_no_outcome_or_rag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", True)
    response = build_live_chat_response(ChatRequest(message=_SSH_COMPROMISE_QUERY))

    approval = response.investigation_approval
    assert isinstance(approval, dict)
    assert approval.get("status") in {"awaiting_approval", "edited_awaiting_approval"}

    assert response.investigation_outcome is None
    evidence = list(response.source_evidence or [])
    collected = [
        item
        for item in evidence
        if isinstance(item, dict) and str(item.get("collection_status") or "") == "collected"
    ]
    assert collected == []

    # No analyst-facing conclusion / disposition packaging before approval.
    assert response.analyst_response is None

    message = str(response.message or "")
    assert "synthesis_lab_already_narrated" not in message
    assert "AI_SOC_GUIDED_LLM_TIMEOUT_SECONDS" not in message
    assert "SesameOp" not in message

    # Plan must preserve failed+success auth semantics when entities are present.
    plan = response.validated_investigation_plan
    assert isinstance(plan, dict)
    blob = str(plan).lower()
    assert "fail" in blob or "authentication_failure" in blob or "ssh" in blob

    for item in list(response.source_evidence or []):
        assert "SesameOp" not in str(item)


def test_atlas_casestudy_not_surfaced_for_ssh_auth_query(monkeypatch: pytest.MonkeyPatch) -> None:
    """FIX 8: generic 'compromise' keywords must not promote unrelated ATLAS cases."""
    monkeypatch.setattr(settings, "soc_kb_retrieval_enabled", True)
    from app.knowledge.soc_kb_retriever import retrieve_soc_kb

    result = retrieve_soc_kb(
        query=_SSH_COMPROMISE_QUERY,
        selected_skill="guided_investigation",
        workflow_stage="context",
        workflow_plan={},
        required_sources=[],
        execution_block_reason=None,
    )
    titles = " ".join(str(e.get("title") or "") for e in (result.get("retrieved_entries") or []))
    assert "SesameOp" not in titles
    assert "OpenAI Assistants" not in titles


def test_guided_owns_hop_skips_lab_live_narration(monkeypatch: pytest.MonkeyPatch) -> None:
    """When guided LLM owns the turn, synthesis lab must not set provider=local_model."""
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", True)

    result = run_governed_synthesis_lab(
        structured_context={"answer_mode": "partial_answer"},
        source_evidence=[],
        context_sufficiency={"answer_mode": "partial_answer", "synthesis_readiness": "ready"},
        mitre_mappings=[],
        action_capability=action_capability_for(None, None),
        severity_label=None,
        spl_validation=None,
        human_review=None,
        allow_live_narration=False,
    )
    assert result.status.provider != "local_model"
