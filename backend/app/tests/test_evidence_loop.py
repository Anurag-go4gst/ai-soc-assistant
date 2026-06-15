from __future__ import annotations

from app.chat.evidence_loop import (
    MAX_MCP_HOPS,
    ROUTE_BROADEN,
    ROUTE_CAPABILITY_GAP,
    ROUTE_DISCOVERY_HOP,
    ROUTE_EXECUTE,
    ROUTE_EXHAUSTED,
    ROUTE_FINALIZE,
    ROUTE_HUMAN_REVIEW,
    assess_loop,
    declare_hop_requirements,
    initialize_loop,
    loop_initialized,
    record_execution_hop,
    record_hop,
)

CHRONOLOGY = [
    "splunk_get_info",
    "splunk_get_indexes",
    "splunk_get_metadata",
    "splunk_run_query",
]


def _init(required=None):
    return initialize_loop(CHRONOLOGY, required_produces=required)


def test_declare_hop_requirements_pulls_produces_from_playbook() -> None:
    reqs = declare_hop_requirements(["splunk_get_info"])
    assert "server_version" in reqs["splunk_get_info"]


def test_initialize_and_idempotency_guard() -> None:
    assert loop_initialized({}) is False
    state = _init()
    assert loop_initialized(state) is True
    assert state["mcp_cursor"] == 0
    assert state["mcp_hops_done"] == 0
    assert state["mcp_chronology"] == CHRONOLOGY


def test_discovery_phase_routes_next_hop() -> None:
    state = _init()
    decision = assess_loop(state)
    assert decision.route == ROUTE_DISCOVERY_HOP
    assert decision.next_tool == "splunk_get_info"


def test_record_hop_advances_cursor_and_counter() -> None:
    state = _init()
    state = {**state, **record_hop(state, tool="splunk_get_info", delivered=["readiness"])}
    assert state["mcp_cursor"] == 1
    assert state["mcp_hops_done"] == 1
    assert assess_loop(state).next_tool == "splunk_get_indexes"


def test_discovery_complete_routes_execute() -> None:
    state = _init()
    for tool in ["splunk_get_info", "splunk_get_indexes", "splunk_get_metadata"]:
        state = {**state, **record_hop(state, tool=tool, delivered=["x"])}
    decision = assess_loop(state)
    assert decision.route == ROUTE_EXECUTE
    assert decision.next_tool == "splunk_run_query"


def test_execution_rows_finalize() -> None:
    state = _init()
    decision = assess_loop(state, execution={"status": "executed", "result_count": 7})
    assert decision.route == ROUTE_FINALIZE
    assert decision.sufficiency == "sufficient"


def test_execution_empty_broaden_eligible_defers_to_broaden() -> None:
    state = _init()
    decision = assess_loop(
        state, execution={"status": "executed", "result_count": 0}, broaden_eligible=True
    )
    assert decision.route == ROUTE_BROADEN


def test_execution_empty_not_broaden_finalizes_negative() -> None:
    state = _init()
    decision = assess_loop(
        state, execution={"status": "executed", "result_count": 0}, broaden_eligible=False
    )
    assert decision.route == ROUTE_FINALIZE


def test_execution_blocked_goes_human_review() -> None:
    state = _init()
    decision = assess_loop(state, execution={"status": "denied", "result_count": 0})
    assert decision.route == ROUTE_HUMAN_REVIEW


def test_capability_gap_for_unservable_requirement() -> None:
    # Only discovery hops, no run_query, unservable requirement remains.
    state = initialize_loop(
        ["splunk_get_info", "splunk_get_metadata"],
        required_produces=["server_version", "fields", "vulnerability_source"],
    )
    for tool in ["splunk_get_info", "splunk_get_metadata"]:
        state = {**state, **record_hop(state, tool=tool, delivered=["server_version", "fields"])}
    decision = assess_loop(state)
    assert decision.route == ROUTE_CAPABILITY_GAP
    assert "vulnerability_source" in decision.capability_gaps


def test_bounded_termination_forces_exhausted() -> None:
    state = _init()
    state = {**state, "mcp_hops_done": MAX_MCP_HOPS}
    decision = assess_loop(state)
    assert decision.route == ROUTE_EXHAUSTED
    assert decision.proceed_with_available is True


def test_loop_always_terminates_within_bound() -> None:
    # Drive the loop with a never-satisfied plan and assert it stops at the bound.
    state = initialize_loop(["splunk_get_metadata"] * 50)
    hops = 0
    while True:
        decision = assess_loop(state)
        if decision.route in {ROUTE_EXHAUSTED, ROUTE_EXECUTE, ROUTE_FINALIZE, ROUTE_HUMAN_REVIEW, ROUTE_CAPABILITY_GAP}:
            break
        state = {**state, **record_hop(state, tool=decision.next_tool or "x", delivered=[])}
        hops += 1
        assert hops <= MAX_MCP_HOPS + 1
    assert state["mcp_hops_done"] <= MAX_MCP_HOPS


def test_record_execution_hop_increments_counter_once() -> None:
    state = _init()
    for tool in ["splunk_get_info", "splunk_get_indexes", "splunk_get_metadata"]:
        state = {**state, **record_hop(state, tool=tool, delivered=["x"])}
    before = int(state["mcp_hops_done"])
    patch = record_execution_hop(state, {"status": "executed", "result_count": 0})
    state = {**state, **patch}
    assert state["mcp_hops_done"] == before + 1
    assert record_execution_hop(state, {"status": "executed", "result_count": 0}) == {}
