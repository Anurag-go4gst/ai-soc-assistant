"""S4 — synthetic zero-day with no threat-specific SOAR playbook. EC fixture only."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.demo.fixtures import common as C

S4_SCENARIO_ID = "s4_zero_day_no_playbook"
S4_FAMILY = "s4_zero_day"
S4_ADVISORY_ID = "ZD-FIXTURE-VPN-2026-001"
S4_QUERY = (
    "A critical zero-day affects our internet-facing VPN gateways. We have no detection rule or "
    "SOAR playbook yet. Determine whether we are exposed and what immediate controls we should apply."
)
S4_FOLLOWUPS = (
    C.chip("show_advisory", "Show advisory"),
    C.chip("list_affected_assets", "List VPN gateways"),
    C.chip("check_gateway_versions", "Check gateway versions"),
    C.chip("search_exploitation_indicators", "Search exploitation indicators"),
    C.chip("show_hardening_guidance", "Show temporary hardening guidance"),
    C.chip("create_emergency_incident", "Create emergency incident", action=True),
    C.chip("create_change_ticket", "Create change ticket", action=True),
    C.chip("notify_network_team", "Notify network team", action=True),
    C.chip("apply_temporary_control", "Apply temporary control", action=True),
    C.chip("verify_temporary_control", "Verify temporary control", action=True),
    C.chip("generate_executive_summary", "Generate executive summary"),
)
S4_FOLLOWUP_IDS = frozenset(item.follow_up_id for item in S4_FOLLOWUPS)


def _base_outcome() -> dict[str, Any]:
    return {
        "disposition": "partial",
        "exposure": "PARTIAL",
        "exposure_validation": "REQUIRES_VALIDATION",
        "confirmed": [
            "A scenario advisory describes a critical condition in internet-facing VPN gateways",
            "No threat-specific SOAR playbook is available for this advisory",
        ],
        "supported": ["Investigation can still assemble advisory, inventory, telemetry, and hardening knowledge"],
        "unconfirmed": [
            "Which gateways are running an affected version",
            "Whether any gateway is compromised",
            "Whether exploitation indicators are present",
        ],
        "missing_evidence": ["CMDB VPN inventory", "Device version evidence", "Splunk exploitation search", "Hardening KB"],
        "vulnerable_vs_compromised": "Vulnerable is not the same as compromised",
        "production_investigation_outcome_unused": True,
    }


def _base_state() -> list[dict[str, Any]]:
    return [
        C.state_item("advisory", "Zero-day advisory", "AVAILABLE_NOT_QUERIED", f"{S4_ADVISORY_ID} not opened", "experience_center_fixture"),
        C.state_item("cmdb", "VPN gateway inventory", "MISSING", "CMDB not queried"),
        C.state_item("versions", "Gateway versions", "MISSING", "Device evidence not collected"),
        C.state_item("splunk", "Exploitation indicators", "AVAILABLE_NOT_QUERIED", "Splunk search not run"),
        C.state_item("hardening", "Temporary hardening KB", "AVAILABLE_NOT_QUERIED", "Hardening guidance not opened", "ec_scenario_policy"),
        C.state_item("soar", "Threat-specific SOAR playbook", "NOT_AVAILABLE", "No threat-specific SOAR playbook available — scenario condition, not an error"),
    ]


def _apply(applied: list[str], session_id: str, outcome: dict[str, Any], state: list[dict[str, Any]], extra: list[dict[str, Any]]) -> None:
    if "show_advisory" in applied:
        C.set_status(state, "advisory", "OBTAINED", f"{S4_ADVISORY_ID}: EdgeGate VPN 12.1-12.4 unauthenticated control-plane condition")
        extra.append(C.evidence("ev-s4-advisory", "advisory_fixture", "Scenario zero-day advisory", [{
            "advisory_id": S4_ADVISORY_ID,
            "vendor": "Northgate Access",
            "product_family": "EdgeGate VPN",
            "affected_versions": "12.1 through 12.4",
            "exploitation_condition": "Unauthenticated control-plane request to management listener",
            "ioc_or_behavior": "POST /api/v1/mgmt/session from untrusted WAN plus unexpected admin token mint",
            "temporary_mitigation": "Disable WAN management listener; restrict control plane to management VRF",
            "not_a_real_cve": True,
        }], provenance="experience_center_fixture"))

    if "list_affected_assets" in applied:
        C.set_status(state, "cmdb", "OBTAINED", "Four internet-facing VPN gateways in inventory")
        extra.append(C.evidence("ev-s4-cmdb", "cmdb_fixture", "VPN gateway inventory", [
            {"asset": "VPN-GW-01", "role": "internet-facing", "site": "DC-A"},
            {"asset": "VPN-GW-02", "role": "internet-facing", "site": "DC-B"},
            {"asset": "VPN-GW-03", "role": "internet-facing", "site": "DR"},
            {"asset": "VPN-GW-04", "role": "internet-facing", "site": "branch-hub"},
        ], provenance="simulated_mcp"))
        outcome["missing_evidence"] = [item for item in outcome["missing_evidence"] if "CMDB" not in item]

    if "check_gateway_versions" in applied:
        C.set_status(state, "versions", "OBTAINED", "VPN-GW-01/02 on 12.3 (affected); VPN-GW-03/04 on 13.0 (not affected)")
        extra.append(C.evidence("ev-s4-versions", "device_fixture", "Gateway versions", [
            {"asset": "VPN-GW-01", "version": "12.3", "affected": True},
            {"asset": "VPN-GW-02", "version": "12.3", "affected": True},
            {"asset": "VPN-GW-03", "version": "13.0", "affected": False},
            {"asset": "VPN-GW-04", "version": "13.0", "affected": False},
        ], provenance="simulated_mcp"))
        outcome["exposure"] = "PARTIAL"
        outcome["exposure_validation"] = "VERSION_EVIDENCE_APPLIED"
        outcome["confirmed"] = [
            *outcome["confirmed"],
            "VPN-GW-01 and VPN-GW-02 are running an affected version (vulnerable)",
            "VPN-GW-03 and VPN-GW-04 are not running an affected version",
        ]
        outcome["unconfirmed"] = [item for item in outcome["unconfirmed"] if "affected version" not in item] + [
            "Compromise / active exploitation of vulnerable gateways",
        ]
        outcome["missing_evidence"] = [item for item in outcome["missing_evidence"] if "version" not in item.lower()]

    if "search_exploitation_indicators" in applied:
        C.set_status(state, "splunk", "OBTAINED", "No confirmed exploitation telemetry in the reviewed window")
        extra.append(C.evidence("ev-s4-splunk", "splunk_mcp_fixture", "Exploitation indicator search", [
            {"query": "mgmt/session from WAN", "hits": 0, "exploitation_confirmed": False},
        ], provenance="simulated_mcp"))
        if "Exploitation not confirmed" not in outcome["confirmed"]:
            outcome["confirmed"].append("Exploitation not confirmed in the reviewed Splunk window")
        outcome["disposition"] = "suspicious"
        outcome["missing_evidence"] = [item for item in outcome["missing_evidence"] if "Splunk" not in item]

    if "show_hardening_guidance" in applied:
        C.set_status(state, "hardening", "OBTAINED", "Disable WAN management listener; restrict control plane", "ec_scenario_policy")
        extra.append(C.evidence("ev-s4-hardening", "kb_fixture", "Temporary hardening guidance", [{
            "control": "disable_wan_management_listener",
            "second_control": "restrict_control_plane_to_mgmt_vrf",
            "not_production_vendor_guidance": True,
        }], provenance="ec_scenario_policy"))

    if "create_emergency_incident" in applied:
        C.ensure_executed_action(kind="ticket_create", label="Create emergency incident", session_id=session_id, scenario_id=S4_SCENARIO_ID, extra={"ticket": {"id": "INC-ZD-001", "priority": "P1"}})
    if "create_change_ticket" in applied:
        C.ensure_executed_action(kind="ticket_create", label="Create emergency change", session_id=session_id, scenario_id=S4_SCENARIO_ID, extra={"ticket": {"id": "CHG-ZD-001", "type": "emergency_change"}})
    if "notify_network_team" in applied:
        C.ensure_executed_action(kind="notify", label="Notify network team", session_id=session_id, scenario_id=S4_SCENARIO_ID, extra={"team": "network"})
    if "apply_temporary_control" in applied:
        C.ensure_hil_action(
            kind="firewall_block",
            label="Apply temporary WAN management restriction",
            session_id=session_id,
            scenario_id=S4_SCENARIO_ID,
            extra={"control": "disable_wan_management_listener", "verify_payload": {"wan_mgmt_listener": "disabled"}},
        )
    if "verify_temporary_control" in applied:
        control = next((item for item in C.actions_for(session_id, S4_SCENARIO_ID) if item.kind == "firewall_block" and item.state == "EXECUTED"), None)
        if control is not None:
            from app.demo import ec_actions

            ec_actions.verify_action(control.action_id)
    if "generate_executive_summary" in applied:
        outcome["executive_summary"] = (
            "Two of four internet-facing VPN gateways are running an affected fixture version. "
            "Exploitation is not confirmed. Temporary hardening is available and requires approval."
        )


def build_s4_turn(*, session_id: str, turn: int, applied_follow_up_ids: list[str], pending_action_id: str | None = None, awaiting_external: bool = False):
    applied = list(applied_follow_up_ids)
    outcome = deepcopy(_base_outcome())
    state = deepcopy(_base_state())
    extra: list[dict[str, Any]] = []
    _apply(applied, session_id, outcome, state, extra)
    return C.envelope(
        scenario_id=S4_SCENARIO_ID,
        family=S4_FAMILY,
        session_id=session_id,
        turn=turn,
        applied=applied,
        chips=list(S4_FOLLOWUPS),
        title="Zero-day exposure on VPN gateways — no predefined playbook",
        assessment=(
            "This situation has not yet been engineered into a predefined response workflow. "
            "There is no threat-specific SOAR playbook. Investigation still assembles advisory knowledge, "
            "inventory, version evidence, telemetry, and temporary hardening. Vulnerable is not the same as compromised."
        ),
        found="Exposure starts as partial and requires version validation. Exploitation is not assumed.",
        outcome=outcome,
        evidence_state=state,
        source_evidence=extra or [
            C.evidence("ev-s4-condition", "advisory_fixture", "Scenario condition", [{
                "advisory_id": S4_ADVISORY_ID,
                "soar_playbook": "not_available",
                "not_an_error": True,
            }], provenance="experience_center_fixture"),
        ],
        actions=C.actions_for(session_id, S4_SCENARIO_ID),
        resources=[
            "advisory knowledge",
            "CMDB / asset inventory",
            "device version evidence",
            "Splunk indicator search",
            "hardening KB",
            "No threat-specific SOAR playbook available",
        ],
        controls=["HIL for temporary control", "verification after remediation", "scenario advisory is not a real CVE"],
        pending_action_id=pending_action_id,
        awaiting_external=awaiting_external,
        extra={
            "ec_soar_playbook": "not_available",
            "ec_advisory_id": S4_ADVISORY_ID,
            "ec_exposure": {"status": outcome.get("exposure"), "validation": outcome.get("exposure_validation")},
        },
        recommended=[
            "Open the advisory",
            "Inventory internet-facing VPN gateways",
            "Check running versions",
            "Search for exploitation indicators",
            "Apply temporary hardening only with approval",
        ],
        important=[
            "No threat-specific SOAR playbook available",
            "Exposure requires version validation",
            "Do not equate vulnerable with compromised",
        ],
        table=[
            {"Question": "Playbook", "Status": "No threat-specific SOAR playbook available"},
            {"Question": "Exposure", "Status": str(outcome.get("exposure"))},
            {"Question": "Compromise", "Status": "Not confirmed"},
        ],
        severity="P1 Critical",
    )


def s4_analyst_override(scenario_id: str, base: dict[str, Any]) -> dict[str, Any] | None:
    if scenario_id != S4_SCENARIO_ID:
        return None
    env = build_s4_turn(session_id="s4-override", turn=0, applied_follow_up_ids=[])
    return {**base, **(env.analyst or {})}


def build_s4_demo_scenarios() -> dict[str, Any]:
    return {
        S4_SCENARIO_ID: C.demo_scenario(
            scenario_id=S4_SCENARIO_ID,
            label="S4 · Zero-day / no playbook",
            query=S4_QUERY,
            demo_order=4,
            family=S4_FAMILY,
            summary="No threat-specific SOAR playbook. Assemble advisory, inventory, versions, and hardening. Vulnerable ≠ compromised.",
        )
    }
