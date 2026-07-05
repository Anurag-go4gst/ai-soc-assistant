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
    apply_observer_next_hop_hint,
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


def test_await_execution_when_only_execution_produces_missing() -> None:
    # Live chronology never contains run_query (spl_approved=False at compose):
    # after discovery drains, a missing "result_rows" is satisfied later by the
    # gated execution stage — the verdict must not read as an analyst gap.
    from app.chat.evidence_loop import ROUTE_AWAIT_EXECUTION

    state = initialize_loop(
        ["splunk_get_indexes", "splunk_get_metadata"],
        required_produces=["accessible_indexes", "result_rows"],
    )
    state = {**state, **record_hop(state, tool="splunk_get_indexes", delivered=["accessible_indexes"])}
    state = {**state, **record_hop(state, tool="splunk_get_metadata", delivered=["sourcetypes"])}
    decision = assess_loop(state)
    assert decision.route == ROUTE_AWAIT_EXECUTION
    assert decision.missing == ["result_rows"]


def test_discovery_only_lane_keeps_human_review_for_execution_produces() -> None:
    state = initialize_loop(
        ["splunk_get_indexes"],
        required_produces=["accessible_indexes", "result_rows"],
    )
    state = {**state, "mcp_discovery_only": True}
    state = {**state, **record_hop(state, tool="splunk_get_indexes", delivered=["accessible_indexes"])}
    decision = assess_loop(state)
    assert decision.route == ROUTE_HUMAN_REVIEW


def test_execution_hop_delivers_result_rows_key() -> None:
    # record_execution_hop must close the playbook "result_rows" requirement.
    state = initialize_loop(["splunk_get_indexes"], required_produces=["result_rows"])
    patch = record_execution_hop(state, {"status": "executed", "result_count": 3})
    delivered = patch["mcp_evidence"][-1]["delivered"]
    assert "result_rows" in delivered and "events" in delivered


def _state_with_host_target(host: str = "fw01") -> dict:
    state = _init()
    return {
        **state,
        "query_understanding": {
            "entities": [{"host": host}],
            "timeframe": {"earliest": "-24h", "latest": "now"},
        },
        "spl_validation": {
            "approved": True,
            "normalized_spl": (
                "search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | head 100"
            ),
        },
    }


def test_metadata_zero_footprint_routes_data_silence_advisory() -> None:
    state = _state_with_host_target()
    for tool in ["splunk_get_info", "splunk_get_indexes"]:
        state = {**state, **record_hop(state, tool=tool, delivered=["x"])}
    state = {
        **state,
        **record_hop(
            state,
            tool="splunk_get_metadata",
            delivered=["hosts", "sourcetypes"],
            payload={
                "preview_rows": [{"host": "fw01", "totalCount": 0}],
                "result_summary": {"sourcetype_count": 0},
            },
        ),
    }
    decision = assess_loop(state)
    assert decision.route == ROUTE_HUMAN_REVIEW
    assert "data_silence" in decision.reason


def test_metadata_nonzero_footprint_routes_execute_unchanged() -> None:
    state = _state_with_host_target()
    for tool in ["splunk_get_info", "splunk_get_indexes"]:
        state = {**state, **record_hop(state, tool=tool, delivered=["x"])}
    state = {
        **state,
        **record_hop(
            state,
            tool="splunk_get_metadata",
            delivered=["hosts", "sourcetypes"],
            payload={
                "preview_rows": [{"host": "fw01", "totalCount": 42}],
                "result_summary": {"sourcetype_count": 3},
            },
        ),
    }
    decision = assess_loop(state)
    assert decision.route == ROUTE_EXECUTE
    assert decision.next_tool == "splunk_run_query"


def _state_for_observer_hint() -> dict:
    state = initialize_loop(["splunk_get_indexes"], required_produces=["accessible_indexes", "hosts"])
    state = {**state, **record_hop(state, tool="splunk_get_indexes", delivered=["accessible_indexes"])}
    return {
        **state,
        "mcp_turn_intents": ["data_silence_check"],
        "evidence_observer_trace": {"next_hop_hint": "splunk_get_metadata"},
    }


def test_observer_hint_matching_intent_appends_discovery_hop() -> None:
    state = _state_for_observer_hint()
    patch = apply_observer_next_hop_hint(state)
    state = {**state, **patch}

    assert state["evidence_observer_trace"]["observer_hint_accepted"] is True
    assert state["mcp_chronology"][-1] == "splunk_get_metadata"
    decision = assess_loop(state)
    assert decision.route == ROUTE_DISCOVERY_HOP
    assert decision.next_tool == "splunk_get_metadata"


def test_observer_hint_execution_tool_rejected() -> None:
    state = {**_state_for_observer_hint(), "evidence_observer_trace": {"next_hop_hint": "splunk_run_query"}}
    patch = apply_observer_next_hop_hint(state)

    assert patch["evidence_observer_trace"]["observer_hint_rejected"] is True
    assert patch["evidence_observer_trace"]["observer_hint_rejected_reason"] == "execution_class_hint"


def test_observer_hint_unknown_tool_rejected() -> None:
    state = {**_state_for_observer_hint(), "evidence_observer_trace": {"next_hop_hint": "splunk_totally_fake"}}
    patch = apply_observer_next_hop_hint(state)

    assert patch["evidence_observer_trace"]["observer_hint_rejected"] is True
    assert patch["evidence_observer_trace"]["observer_hint_rejected_reason"] == "unknown_tool"


def test_observer_hint_already_run_tool_rejected() -> None:
    state = _state_for_observer_hint()
    state = {**state, **record_hop(state, tool="splunk_get_metadata", delivered=["hosts"])}
    patch = apply_observer_next_hop_hint(state)

    assert patch["evidence_observer_trace"]["observer_hint_rejected"] is True
    assert patch["evidence_observer_trace"]["observer_hint_rejected_reason"] == "already_collected"


def test_observer_hint_at_hop_budget_rejected() -> None:
    state = {**_state_for_observer_hint(), "mcp_hops_done": MAX_MCP_HOPS}
    patch = apply_observer_next_hop_hint(state)

    assert patch["evidence_observer_trace"]["observer_hint_rejected"] is True
    assert patch["evidence_observer_trace"]["observer_hint_rejected_reason"] == "budget"


def test_observer_hint_ignored_on_recipe_turn() -> None:
    state = {**_state_for_observer_hint(), "mcp_recipe_id": "recipe.test"}
    patch = apply_observer_next_hop_hint(state)

    assert patch["evidence_observer_trace"]["observer_hint_ignored_recipe_turn"] is True
    assert "mcp_chronology" not in patch
