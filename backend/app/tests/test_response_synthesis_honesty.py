from __future__ import annotations

from app.chat.pipeline import _chat_message, _response_mode, _synthesis_mode


def test_mock_execution_message_mentions_deterministic_lab_summary_when_present() -> None:
    message = _chat_message(
        {"approved": True},
        {"status": "executed"},
        "Deterministic summary",
    )
    assert "Live Foundation-Sec synthesis is disabled" in message
    assert "deterministic lab summary" in message


def test_response_mode_reports_clarification_required() -> None:
    assert (
        _response_mode(
            {"status": "insufficient_evidence", "synthesis_allowed": False},
            {"required": True, "review_type": "intent_clarification"},
            None,
        )
        == "clarification_required"
    )


def test_response_mode_reports_rejected_candidate_spl() -> None:
    assert (
        _response_mode(
            {"status": "insufficient_evidence", "synthesis_allowed": False, "synthesis_readiness": False},
            {"required": False},
            {"approved": False},
        )
        == "candidate_spl_rejected"
    )


def test_synthesis_mode_distinguishes_lab_summary_from_disabled_live_llm() -> None:
    assert (
        _synthesis_mode({"status": "completed", "enabled": True}, "summary")
        == "deterministic_lab_summary"
    )
    assert (
        _synthesis_mode({"status": "skipped", "enabled": False}, None)
        == "live_foundation_sec_disabled"
    )
