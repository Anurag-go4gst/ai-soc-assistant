from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi import HTTPException
from app.api.routes_chat import chat
from app.api.routes_quality import quality_chat_turn_detail, quality_chat_turns, submit_chat_feedback, update_quality_review
from app.config import settings
from app.quality import store as quality_store_module
from app.quality.store import clear_quality_store_for_tests, get_chat_turn
from app.schemas.requests import ChatRequest
from app.schemas.responses import PlaceholderResponse


@pytest.fixture(autouse=True)
def quality_store() -> None:
    original_ec_parity = settings.ai_soc_live_chat_ec_parity_enabled
    original_langgraph = settings.langgraph_orchestration_enabled
    original_quality_review_enabled = settings.quality_review_enabled
    original_database_url = settings.database_url
    settings.ai_soc_live_chat_ec_parity_enabled = False
    settings.langgraph_orchestration_enabled = False
    settings.quality_review_enabled = True
    settings.database_url = "postgresql://ai_soc:change-me@postgres:5432/ai_soc_assistant"
    clear_quality_store_for_tests()
    yield
    settings.ai_soc_live_chat_ec_parity_enabled = original_ec_parity
    settings.langgraph_orchestration_enabled = original_langgraph
    settings.quality_review_enabled = original_quality_review_enabled
    settings.database_url = original_database_url
    clear_quality_store_for_tests()


def test_chat_records_turn_and_returns_turn_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.routes_chat.build_live_chat_response", _fake_chat_response)

    response = chat(ChatRequest(message="Which users have excessive failed logins?"))

    assert response.turn_id
    detail = get_chat_turn(response.turn_id)
    assert detail is not None
    assert detail["user_query"] == "Which users have excessive failed logins?"
    assert detail["normalized_query"] == "which users have excessive failed logins?"
    assert detail["selected_skill"] == "attack_discovery"
    assert detail["selected_use_case_id"] == "auth_failed_login_spike"
    assert detail["final_message"] == "Governed answer"
    assert detail["candidate_spl"] == "index=pgcil_soc sourcetype=pgcil:auth | stats count by user"
    assert detail["spl_validation"]["approved"] is True
    assert detail["mitre_decision"]["status"] == "mapped"
    assert detail["execution_status"] == "requires_human_review"


def test_chat_succeeds_when_ledger_write_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_record_chat_turn(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("db down")

    monkeypatch.setattr(quality_store_module, "record_chat_turn", fail_record_chat_turn)
    monkeypatch.setattr("app.api.routes_chat.build_live_chat_response", _fake_chat_response)

    response = chat(ChatRequest(message="hello"))

    assert response.message == "Governed answer"
    assert response.turn_id


def test_ledger_redacts_and_minimizes_secret_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_response(request: ChatRequest) -> PlaceholderResponse:
        response = _fake_chat_response(request)
        response.control_plane_trace = {
            "api_token": "sk-12345678901234567890",
            "safe": "Bearer abcdefghijklmnopqrstuvwxyz123456",
            "nested": {"password": "do-not-store", "value": "ok"},
        }
        response.analyst_response = None
        return response

    monkeypatch.setattr("app.api.routes_chat.build_live_chat_response", fake_response)

    response = chat(ChatRequest(message="secret test"))
    detail = get_chat_turn(response.turn_id)
    assert detail is not None
    text = json.dumps(detail).lower()
    trace_text = json.dumps(detail["control_plane_trace"]).lower()

    assert "sk-123" not in text
    assert "do-not-store" not in text
    assert "api_token" not in trace_text
    assert "password" not in trace_text
    assert "bearer [redacted]" in trace_text


def test_feedback_and_review_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.routes_chat.build_live_chat_response", _fake_chat_response)
    response = chat(ChatRequest(message="feedback target"))
    user = {"username": "reviewer", "role": "quality_reviewer"}

    feedback = submit_chat_feedback(
        _feedback_payload(response.turn_id, rating="down", remark="Missing MITRE detail"),
        user=user,
    )
    assert feedback["feedback"]["rating"] == "down"

    queue = quality_chat_turns(status_filter="flagged", limit=50, user=user)
    assert queue["turns"][0]["turn_id"] == response.turn_id
    assert queue["turns"][0]["golden_candidate"] is True

    review = update_quality_review(
        response.turn_id,
        _review_payload(
            root_cause="answer_wording_wrong",
            review_notes="Needs clearer status.",
            recommended_action="Update deterministic wording.",
        ),
        user=user,
    )
    assert review["review"]["root_cause"] == "answer_wording_wrong"

    detail = quality_chat_turn_detail(response.turn_id, user=user)
    assert detail["turn"]["quality_status"] == "in_review"
    assert detail["turn"]["feedback"][0]["remark"] == "Missing MITRE detail"


def test_feedback_unknown_turn_rejected() -> None:
    with pytest.raises(HTTPException) as exc_info:
        submit_chat_feedback(_feedback_payload("missing", rating="up"), user={"username": "reviewer", "role": "quality_reviewer"})
    assert exc_info.value.status_code == 404


def test_review_root_cause_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.routes_chat.build_live_chat_response", _fake_chat_response)
    response = chat(ChatRequest(message="review target"))
    user = {"username": "reviewer", "role": "quality_reviewer"}

    with pytest.raises(HTTPException) as exc_info:
        update_quality_review(response.turn_id, _review_payload(root_cause="made_up"), user=user)
    assert exc_info.value.status_code == 400


def _feedback_payload(turn_id: str, *, rating: str, remark: str | None = None):
    from app.api.routes_quality import ChatFeedbackRequest

    return ChatFeedbackRequest(turn_id=turn_id, rating=rating, remark=remark)


def _review_payload(
    *,
    root_cause: str,
    review_notes: str = "",
    recommended_action: str = "",
):
    from app.api.routes_quality import QualityReviewRequest

    return QualityReviewRequest(
        root_cause=root_cause,
        review_notes=review_notes,
        recommended_action=recommended_action,
    )


def _fake_chat_response(request: ChatRequest, **_: Any) -> PlaceholderResponse:
    return PlaceholderResponse(
        trace_id="trace-quality",
        message="Governed answer",
        note="No execution.",
        user_query=request.message,
        selected_skill="attack_discovery",
        selected_use_case={
            "use_case_id": "auth_failed_login_spike",
            "display_name": "Failed login spike",
            "category": "auth",
            "primary_skill": "attack_discovery",
            "confidence": 0.95,
            "matched_patterns": [],
            "default_spl_template": None,
            "output_template": "auth",
            "required_sources": [],
            "optional_sources": [],
            "action_capability_tier": 1,
        },
        candidate_spl={
            "trace_id": "trace-quality",
            "skill": "attack_discovery",
            "user_query": request.message,
            "candidate_spl": "index=pgcil_soc sourcetype=pgcil:auth | stats count by user",
            "generation_mode": "stub",
            "confidence": 0.9,
            "assumptions": [],
            "warnings": [],
        },
        spl_validation={
            "approved": True,
            "normalized_spl": "index=pgcil_soc sourcetype=pgcil:auth | stats count by user",
            "reject_reasons": [],
            "warnings": [],
            "enforced_limits": {},
            "policy_version": "test",
        },
        execution={
            "status": "requires_human_review",
            "execution_intent": "spl_search",
            "selected_mcp_server": "splunk_soc",
            "selected_mcp_tool": "splunk_run_query",
            "tool_selection_status": "selected",
            "tool_selection_reason": "test",
            "executed_spl": None,
            "result_count": 0,
            "results_preview": [],
            "block_reason": "mcp_global_execution_disabled",
            "duration_ms": 0,
        },
        mitre_decision={"status": "mapped", "techniques": ["T1110.001"]},
        mitre_mappings=[
            {
                "technique_id": "T1110.001",
                "name": "Password Guessing",
                "tactic": "Credential Access",
                "status": "supported",
                "why": "Test mapping.",
            }
        ],
    )
