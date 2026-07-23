"""DecisionRecord emission helper and state-channel retention."""

from __future__ import annotations

import pytest

from app.chat.decision_record import emit_decision_record
from app.chat.pipeline import ChatPipelineState
from app.planner.planner_hierarchy import DecisionRecord, new_decision_record_id


def test_emit_decision_record_appends_to_log() -> None:
    state: dict = {}
    updated = emit_decision_record(
        state,
        DecisionRecord(
            record_id=new_decision_record_id(),
            node="resource_planner.merge",
            authority="resource_planner",
            decision_reason="fan_in_complete",
            inputs_ref=["specialist_reports"],
            outputs_ref=["work_bundle"],
        ),
    )
    assert len(updated["decision_log"]) == 1
    assert updated["decision_log"][0]["decision_reason"] == "fan_in_complete"


def test_emit_decision_record_requires_audit_fields() -> None:
    with pytest.raises(ValueError, match="missing required field"):
        emit_decision_record({}, {"node": "x", "authority": "y"})


def test_emit_decision_record_redacts_secret_refs() -> None:
    updated = emit_decision_record(
        {},
        DecisionRecord(
            record_id=new_decision_record_id(),
            node="mcp.specialist",
            authority="specialist:mcp",
            decision_reason="tool_pref",
            inputs_ref=["state.api_key"],
            outputs_ref=["mcp_tool_plan", "bearer_token"],
        ),
    )
    record = updated["decision_log"][0]
    assert record["inputs_ref"] == ["[redacted]"]
    assert record["outputs_ref"] == ["mcp_tool_plan", "[redacted]"]


def test_emit_decision_record_preserves_prior_entries() -> None:
    first = emit_decision_record(
        {},
        DecisionRecord(
            record_id="dr:1",
            node="bootstrap",
            authority="deterministic",
            decision_reason="init",
            inputs_ref=["request"],
            outputs_ref=["query_understanding"],
        ),
    )
    second = emit_decision_record(
        first,
        DecisionRecord(
            record_id="dr:2",
            node="resource_planner.delegate",
            authority="resource_planner",
            decision_reason="fan_out",
            inputs_ref=["evidence_plan"],
            outputs_ref=["specialist_delegations"],
        ),
    )
    assert len(second["decision_log"]) == 2
    assert second["decision_log"][0]["record_id"] == "dr:1"
    assert second["decision_log"][1]["record_id"] == "dr:2"


def test_decision_log_declared_on_chat_pipeline_state() -> None:
    assert "decision_log" in ChatPipelineState.__annotations__
