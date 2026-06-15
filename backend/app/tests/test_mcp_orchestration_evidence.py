"""Step 2 — per-call MCP evidence + cross-turn broaden envelope.

A broaden turn is two logical searches. These tests prove the finalized
envelope records both calls and that source-evidence emits a distinct honest
negative item for the empty primary alongside the broadened result.
"""

from __future__ import annotations

import pytest

from app.evidence.source_evidence import build_source_evidence
from app.orchestration.broaden_orchestration import (
    finalize_broaden_orchestration,
    is_broaden_pending,
)


def _pending(primary="index=auth sourcetype=pgcil:auth action=failure | stats count",
             broadened="index=auth sourcetype=pgcil:auth action=failure earliest=-7d | stats count"):
    return {
        "normalized_spl": broadened,
        "primary_normalized_spl": primary,
        "selected_mcp_server": "splunk_soc",
        "selected_mcp_tool": "splunk_run_query",
        "trace_id": "t1",
        "source": "broaden_scope_on_empty",
    }


def _executed(spl, count):
    return {
        "status": "executed",
        "result_count": count,
        "executed_spl": spl,
        "selected_mcp_server": "splunk_soc",
        "selected_mcp_tool": "splunk_run_query",
    }


# --- envelope finalize --------------------------------------------------------


def test_is_broaden_pending() -> None:
    assert is_broaden_pending(_pending()) is True
    assert is_broaden_pending({"source": "spl_execution_confirmation"}) is False
    assert is_broaden_pending(None) is False


def test_finalize_records_both_calls_broadened_ok() -> None:
    pending = _pending()
    env = finalize_broaden_orchestration(
        trace_id="t1",
        pending=pending,
        broadened_execution=_executed(pending["normalized_spl"], 12),
    )
    assert env["recipe_id"] == "broaden_scope_on_empty"
    assert env["status"] == "complete"
    assert [c["call_id"] for c in env["calls"]] == ["c1_primary_search", "c2_broadened_search"]
    assert env["calls"][0]["outcome"] == "empty"
    assert env["calls"][1]["outcome"] == "ok"
    assert env["calls"][1]["result_count"] == 12
    assert env["call_budget"]["calls_completed"] == 2
    assert env["next_call"] is None
    assert env["unresolved_evidence_keys"] == []


def test_finalize_broadened_still_empty_is_terminal_negative() -> None:
    pending = _pending()
    env = finalize_broaden_orchestration(
        trace_id="t1",
        pending=pending,
        broadened_execution=_executed(pending["normalized_spl"], 0),
    )
    assert env["status"] == "complete"
    assert env["calls"][1]["outcome"] == "empty"
    assert env["stop_reason"] == "broadened_empty_terminal"


def test_finalize_broadened_blocked_is_partial() -> None:
    pending = _pending()
    blocked = {"status": "blocked", "result_count": 0, "executed_spl": None,
               "selected_mcp_server": "splunk_soc", "selected_mcp_tool": "splunk_run_query"}
    env = finalize_broaden_orchestration(trace_id="t1", pending=pending, broadened_execution=blocked)
    assert env["status"] == "partial"
    assert env["calls"][1]["outcome"] == "blocked"


# --- per-call evidence --------------------------------------------------------


def test_source_evidence_emits_separate_primary_empty_item() -> None:
    pending = _pending()
    execution = _executed(pending["normalized_spl"], 5)
    execution["mcp_orchestration"] = finalize_broaden_orchestration(
        trace_id="t1", pending=pending, broadened_execution=execution
    )
    evidence = build_source_evidence(
        trace_id="t1",
        query="failed logins?",
        selected_skill="spl_generation",
        spl_validation={"approved": True, "normalized_spl": pending["normalized_spl"]},
        execution=execution,
    )
    mcp_items = [e for e in evidence if e["source_type"] == "splunk_mcp"]
    # Two distinct splunk_mcp items: broadened (c2) + empty primary (c1).
    assert len(mcp_items) == 2
    ids = {e["evidence_id"] for e in mcp_items}
    assert len(ids) == 2  # no id collision
    primary = next(e for e in mcp_items if e.get("plan_step_ref") == "c1_primary_search")
    assert primary["result_count"] == 0
    assert primary["execution_outcome"] == "negative_result"
    assert "broaden_primary_call" in primary["warnings"]


def test_source_evidence_unchanged_without_broaden_envelope() -> None:
    execution = _executed("index=auth | stats count", 3)
    evidence = build_source_evidence(
        trace_id="t1",
        query="q",
        selected_skill="spl_generation",
        spl_validation={"approved": True, "normalized_spl": "index=auth | stats count"},
        execution=execution,
    )
    mcp_items = [e for e in evidence if e["source_type"] == "splunk_mcp"]
    assert len(mcp_items) == 1  # single-call path is byte-identical
