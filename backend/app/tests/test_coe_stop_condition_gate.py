from __future__ import annotations

from app.chat.pipeline import _apply_coe_stop_condition_gate
from app.schemas.responses import AnalystResponseEnvelope, PlaceholderResponse


def test_coe_stop_condition_gate_blocks_missing_run_contract() -> None:
    response = PlaceholderResponse(
        trace_id="trace-coe-stop",
        message="Review-only / no live execution.",
        note="test",
        analyst_response=AnalystResponseEnvelope(
            direct_answer_summary="Review-only SPL draft - no live query was executed."
        ),
    )

    blocked = _apply_coe_stop_condition_gate(response, query="show substation sessions")

    assert blocked.analyst_response is None
    assert blocked.human_review is not None
    assert blocked.human_review.required is True
    assert blocked.final_answer_validation is not None
    assert blocked.final_answer_validation["guard_status"] == "blocked"
    assert "run_contract_missing" in blocked.final_answer_validation["failed_checks"]
