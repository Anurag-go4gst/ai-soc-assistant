"""Phase 0.5 — final analyst-visible output in the debug trace."""

from __future__ import annotations

from app.chat.final_output_trace import (
    build_final_output_trace,
    final_output_answer_preview,
)


def _payload() -> dict:
    return {
        "message": "  Outbound spike from   web01 reviewed.\nNo confirmed breach.  ",
        "analyst_summary": "Investigate the outbound spike on web01.",
        "selected_skill": "spl_generation",
        "evidence_plan": {"answer_mode": "live_investigation"},
        "severity_decision": {"severity_label": "P3"},
        "answer_guard_status": "passed",
        "human_review": {"reason": "execution_requires_confirmation"},
        "mitre_decision": {"status": "requires_validation"},
        "execution": {"status": "blocked"},
    }


def test_build_final_output_trace_extracts_redacted_fields() -> None:
    out = build_final_output_trace(_payload())
    assert out["message"] == "Outbound spike from web01 reviewed. No confirmed breach."
    assert out["analyst_summary"] == "Investigate the outbound spike on web01."
    assert out["selected_skill"] == "spl_generation"
    assert out["answer_mode"] == "live_investigation"
    assert out["severity_label"] == "P3"
    assert out["mitre_status"] == "requires_validation"
    assert out["hil_required"] is True
    assert out["hil_reason"] == "execution_requires_confirmation"
    assert out["guard_status"] == "passed"
    assert out["execution_status"] == "blocked"


def test_build_final_output_trace_tolerates_empty() -> None:
    assert build_final_output_trace(None) == {}
    out = build_final_output_trace({})
    assert out["message"] is None
    assert out["hil_required"] is False


def test_answer_preview_prefers_real_message() -> None:
    preview = final_output_answer_preview(_payload())
    assert preview == "Outbound spike from web01 reviewed. No confirmed breach."


def test_answer_preview_falls_back_to_summary_then_none() -> None:
    assert final_output_answer_preview({"analyst_summary": "Summary only."}) == "Summary only."
    assert final_output_answer_preview({}) is None


def test_message_is_length_bounded() -> None:
    long = "x" * 1000
    out = build_final_output_trace({"message": long})
    assert out["message"].endswith("…")
    assert len(out["message"]) <= 600
