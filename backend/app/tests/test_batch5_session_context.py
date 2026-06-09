"""Batch 5 — lightweight investigation session context."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.api.routes_chat import chat
from app.chat.session_context import resolve_session_context
from app.chat.session_store import (
    SessionPins,
    clear_all_session_pins_for_tests,
    get_session_pins,
    save_session_pins,
)
from app.config import settings
from app.schemas.requests import ChatRequest

ALT_QUERY = (
    "For alert ALT-2024-0891 (failed logins followed by a successful login from the same user "
    "in the last hour), what's the severity, MITRE mapping with status, and a governed SPL "
    "I can review—but not execute"
)


@pytest.fixture(autouse=True)
def _enable_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.control_plane_enabled", True)
    monkeypatch.setattr("app.config.settings.ai_soc_session_context_enabled", True)
    monkeypatch.setattr("app.config.settings.ai_soc_live_chat_ec_parity_enabled", False)
    monkeypatch.setattr("app.config.settings.langgraph_orchestration_enabled", False)
    monkeypatch.setattr("app.config.settings.telemetry_mode", "none")
    monkeypatch.setattr("app.config.settings.ai_soc_telemetry_sink", "none")
    monkeypatch.setattr(
        "app.config.settings.database_url",
        "postgresql://ai_soc:change-me@postgres:5432/ai_soc_assistant",
    )
    monkeypatch.setattr("app.config.settings.mcp_global_execution_enabled", False)
    clear_all_session_pins_for_tests()


def test_chat_request_accepts_optional_session_id() -> None:
    request = ChatRequest(message="hello", session_id="sess-123")
    assert request.session_id == "sess-123"


def test_first_request_returns_session_context_status() -> None:
    response = chat(ChatRequest(message=ALT_QUERY))
    assert response.session_context_status is not None
    assert response.session_context_status.session_id
    assert response.session_context_status.staleness in {"missing", "fresh"}
    pins = get_session_pins(response.session_context_status.session_id)
    assert pins is not None
    assert pins.last_alert_id == "ALT-2024-0891"
    assert pins.last_use_case_id == "auth_success_after_failure"
    assert "message" not in pins.model_dump()


def test_follow_up_mitre_uses_fresh_session_context() -> None:
    first = chat(ChatRequest(message=ALT_QUERY))
    session_id = first.session_context_status.session_id if first.session_context_status else None
    assert session_id
    follow_up = chat(ChatRequest(message="now map it to MITRE", session_id=session_id))
    assert follow_up.session_context_status is not None
    assert follow_up.session_context_status.used_previous_context is True
    assert follow_up.session_context_status.staleness == "fresh"
    assert "last_alert_id" in follow_up.session_context_status.used_fields
    assert follow_up.mitre_evidence_status is not None
    # MCP off → no source-grounded evidence → tier gate caps to requires_validation.
    assert follow_up.mitre_evidence_status.get("T1110.001") == "requires_validation"
    assert follow_up.mitre_evidence_status.get("T1078") == "candidate"
    names = {item.get("node_name") for item in (follow_up.node_trace or [])}
    assert "session_context" in names


def test_follow_up_spl_refine_revalidates_previous_spl() -> None:
    first = chat(ChatRequest(message=ALT_QUERY))
    session_id = first.session_context_status.session_id if first.session_context_status else None
    assert session_id and first.spl_validation is not None and first.spl_validation.approved
    follow_up = chat(ChatRequest(message="refine that SPL", session_id=session_id))
    assert follow_up.spl_validation is not None
    assert follow_up.candidate_spl is not None
    assert follow_up.candidate_spl.generation_mode == "session_refine"
    assert follow_up.spl_validation.approved is True
    assert follow_up.execution.execution_status_label in {"not_executed", "review_required", None}


def test_stale_session_context_triggers_clarification() -> None:
    session_id = "stale-session-1"
    save_session_pins(
        SessionPins(
            session_id=session_id,
            last_trace_id="trace-old",
            last_alert_id="ALT-2024-0891",
            last_use_case_id="auth_success_after_failure",
            updated_at=datetime.now(UTC) - timedelta(hours=2),
            expires_at=datetime.now(UTC) - timedelta(minutes=5),
        ),
        refresh_ttl=False,
    )
    resolution = resolve_session_context(ChatRequest(message="now map it to MITRE", session_id=session_id))
    assert resolution.status.staleness == "stale"
    assert resolution.status.clarification_required is True

    response = chat(ChatRequest(message="now map it to MITRE", session_id=session_id))
    assert response.session_context_status is not None
    assert response.session_context_status.clarification_required is True
    assert response.human_review is not None
    assert response.human_review.required is True


def test_session_memory_does_not_bypass_hil_on_mock_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.mcp_global_execution_enabled", True)
    monkeypatch.setattr("app.config.settings.mcp_server_mock_execution_enabled", True)
    first = chat(ChatRequest(message=ALT_QUERY))
    session_id = first.session_context_status.session_id if first.session_context_status else None
    follow_up = chat(ChatRequest(message="same alert — show severity", session_id=session_id))
    if follow_up.execution is not None:
        assert follow_up.execution.execution_status_label != "live_executed"


def test_session_memory_cannot_promote_t1078_without_evidence() -> None:
    first = chat(ChatRequest(message=ALT_QUERY))
    session_id = first.session_context_status.session_id if first.session_context_status else None
    follow_up = chat(ChatRequest(message="now map it to MITRE", session_id=session_id))
    assert (follow_up.mitre_evidence_status or {}).get("T1078") in {"candidate", "not_claimed"}
    analyst = (follow_up.analyst_response.model_dump_json() if follow_up.analyst_response else "").lower()
    assert "account compromised" not in analyst


def test_session_store_has_no_transcript_field() -> None:
    response = chat(ChatRequest(message=ALT_QUERY))
    session_id = response.session_context_status.session_id if response.session_context_status else None
    pins = get_session_pins(session_id)
    assert pins is not None
    dumped = pins.model_dump()
    for forbidden in ("transcript", "conversation", "full_message", "raw_chat"):
        assert forbidden not in dumped
