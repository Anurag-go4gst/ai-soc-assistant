"""North-star item 3 — live catalogue router probes (novel / out-of-set)."""

from __future__ import annotations

from typing import Any

import pytest

from app.catalogue.match_tiers import match_catalogue_tier
from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.evals.sentinel_eval import sentinel_runtime
from app.schemas.requests import ChatRequest

TYPO_FAILED_LOGIN = "failed lgon spike top users last hour"
SUCCESS_AFTER_FAILURE = (
    "For alert ALT-2024-0891 (failed logins followed by a successful login from the same user "
    "in the last hour), what's the severity, MITRE mapping with status, and a governed SPL "
    "I can review—but not execute"
)
SOP_QUERY = "Show SOP for brute-force investigation"
MITRE_NO_ALERT = "Map this alert to MITRE"
HR_POLICY = "Show me vacation policy accrual rules for new hires"
GUIDED_OT = "How should I investigate unusual outbound traffic from an OT host overnight?"


def _enable_cp_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "soc_kb_retrieval_enabled", True)
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", False)
    monkeypatch.setattr(settings, "mcp_server_mock_execution_enabled", False)
    monkeypatch.setattr(
        "app.chat.pipeline.retrieve_soc_kb",
        lambda **kwargs: {
            "retrieval_status": "collected",
            "chunks": [{"doc_id": "probe-doc", "title": "Probe"}],
            "required_sources": kwargs.get("required_sources") or [],
        },
    )


def _execution_status(response: Any) -> str:
    execution = response.execution
    if hasattr(execution, "model_dump"):
        execution = execution.model_dump()
    return str(execution.get("status") or "")


def _no_live_rows(response: Any) -> None:
    evidence = response.source_evidence or []
    for item in evidence:
        if isinstance(item, dict):
            assert item.get("evidence_source") != "live"


@pytest.mark.parametrize(
    ("message", "expected_skill", "expect_spl", "catalogue_tier"),
    [
        (TYPO_FAILED_LOGIN, "spl_generation", True, "T3"),
        (SUCCESS_AFTER_FAILURE, "attack_discovery", True, None),
        (SOP_QUERY, "knowledge_recall", False, None),
        (MITRE_NO_ALERT, "knowledge_recall", False, None),
        (HR_POLICY, "knowledge_recall", False, None),
        (GUIDED_OT, "guided_investigation", False, None),
    ],
    ids=[
        "typo_failed_login",
        "success_after_failure",
        "sop_playbook",
        "mitre_without_alert",
        "hr_policy_non_soc",
        "guided_out_of_registry",
    ],
)
def test_live_catalogue_router_probes(
    monkeypatch: pytest.MonkeyPatch,
    message: str,
    expected_skill: str,
    expect_spl: bool,
    catalogue_tier: str | None,
) -> None:
    _enable_cp_stack(monkeypatch)
    with sentinel_runtime():
        response = build_live_chat_response(ChatRequest(message=message))

    assert response.selected_skill == expected_skill
    if expect_spl:
        assert response.candidate_spl is not None
    else:
        assert response.candidate_spl is None
        assert response.spl_validation is None

    _no_live_rows(response)
    assert _execution_status(response) in {
        "skipped",
        "blocked",
        "requires_human_review",
    }

    if catalogue_tier is not None:
        tier = match_catalogue_tier(message)
        assert tier.tier == catalogue_tier
        assert tier.alias_applied is True

    if message == TYPO_FAILED_LOGIN:
        assert (response.evidence_plan or {}).get("use_case_id") == "auth_failed_login_spike"

    if message == SUCCESS_AFTER_FAILURE:
        assert response.selected_use_case is not None
        assert response.selected_use_case.use_case_id == "auth_success_after_failure"

    if message == MITRE_NO_ALERT:
        assert response.human_review is not None
        assert response.human_review.review_type == "intent_clarification"

    if message == HR_POLICY:
        intent = (response.query_to_intent or {}).get("intent_classification") or {}
        assert intent.get("intent_family") == "clarification_required"

    if message == GUIDED_OT:
        evidence = response.evidence_plan or {}
        assert evidence.get("needs_mcp") is False
        assert evidence.get("mcp_allowed") is False
