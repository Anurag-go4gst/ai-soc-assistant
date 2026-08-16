"""EC architecture-projection dispatch surfaces on Experience Center scenarios."""

from __future__ import annotations

import pytest

from app.demo.scenarios import SCENARIOS, list_demo_scenarios, run_demo_scenario


LEADERSHIP_IDS = {item["scenario_id"] for item in list_demo_scenarios()}

MCP_EXECUTED_IDS = {
    "firewall_deny_coordinated_attack",
    "network_blast_radius_attacker_ip",
    "failed_login_spike_app01",
    "dns_beaconing_c2_hunt",
    "successful_login_after_failures",
}


@pytest.mark.parametrize("scenario_id", sorted(LEADERSHIP_IDS))
def test_leadership_scenarios_project_ec_architecture_authority(scenario_id: str) -> None:
    payload = run_demo_scenario(scenario_id)
    assert payload.get("intent_dispatch")
    assert payload.get("pipeline_dispatch")
    assert payload.get("plan_dispatch")
    assert payload.get("run_contract")
    authority = payload["plan_dispatch"].get("dispatch_authority")
    assert authority == "ec_architecture_projection"
    assert authority != "pipeline_dispatch_v2"
    provenance = payload.get("ec_provenance") or {}
    assert provenance.get("dispatch_authority") != "pipeline_dispatch_v2"


@pytest.mark.parametrize("scenario_id", sorted(MCP_EXECUTED_IDS & LEADERSHIP_IDS | MCP_EXECUTED_IDS))
def test_mcp_executed_scenarios_have_tools_and_execution(scenario_id: str) -> None:
    if scenario_id not in SCENARIOS:
        pytest.skip("lab scenario not in registry")
    payload = run_demo_scenario(scenario_id)
    execution = payload.get("execution") or {}
    if scenario_id in MCP_EXECUTED_IDS:
        assert execution.get("status") == "executed"
        assert execution.get("selected_mcp_tool") == "splunk_run_query"
    trace = payload.get("control_plane_trace") or {}
    dispatch = trace.get("pipeline_dispatch") or payload.get("pipeline_dispatch") or {}
    runtime = dispatch.get("runtime_context") or {}
    if scenario_id in {"firewall_deny_coordinated_attack", "network_blast_radius_attacker_ip"}:
        mcp_ctx = runtime.get("mcp_discovery_context") or {}
        assert mcp_ctx.get("tools_called")


def test_firewall_opener_has_visual_lanes() -> None:
    payload = run_demo_scenario("firewall_deny_coordinated_attack")
    lanes = payload.get("ec_visual_lanes") or {}
    assert lanes.get("mcp_console")
    assert lanes.get("coe_logic")


def test_list_demo_scenarios_leadership_order() -> None:
    pickable = list_demo_scenarios()
    assert pickable[0]["scenario_id"] == "firewall_deny_coordinated_attack"
    assert len(pickable) == 10
