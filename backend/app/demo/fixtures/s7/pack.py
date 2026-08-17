"""S7 — conflicting Splunk vs retired CMDB. No forced incident. EC fixture only."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.demo.ec_conflict_s7 import (
    S7_LAYER2_PATH,
    build_s7_action_readiness,
    build_s7_investigation_pivot,
    build_s7_status_summary,
)
from app.demo.ec_journeys import journey_for
from app.demo import ec_email_drafts
from app.demo.fixtures import common as C

S7_SCENARIO_ID = "s7_conflicting_ot_evidence"
S7_FAMILY = "s7_conflicting_evidence"
S7_QUERY = (
    "Splunk shows unauthorized access to an OT device, but the asset system says the device was retired. "
    "Determine whether this is a real incident."
)
S7_FOLLOWUPS = (
    C.chip("check_ot_inventory", "Check OT inventory"),
    C.chip("check_firewall_activity", "Check firewall segmentation"),
    C.chip("check_arp_mac", "Check switch ARP/MAC"),
    C.chip("ask_ot_team", "Ask the OT team", action=True),
    C.chip("ingest_ot_response", "Ingest OT team response"),
    C.chip("confirm_stale_identity", "Confirm recycled/stale identity"),
    C.chip("create_incident_ticket", "Create incident ticket", action=True),
    C.chip("recommend_cmdb_correction", "Recommend CMDB correction", action=True),
    C.chip("generate_closure_summary", "Generate closure summary"),
)
S7_FOLLOWUP_IDS = frozenset(item.follow_up_id for item in S7_FOLLOWUPS)


def _visible_chips(applied: list[str]) -> list[Any]:
    chips = list(S7_FOLLOWUPS)
    path_a = "check_ot_inventory" in applied
    path_b = "confirm_stale_identity" in applied
    if not path_a:
        chips = [item for item in chips if item.follow_up_id != "create_incident_ticket"]
    if not path_b:
        chips = [item for item in chips if item.follow_up_id != "recommend_cmdb_correction"]
    if path_a:
        chips = [item for item in chips if item.follow_up_id != "confirm_stale_identity"]
    if path_b:
        chips = [item for item in chips if item.follow_up_id != "create_incident_ticket"]
    return chips


def _base_outcome() -> dict[str, Any]:
    return {
        "disposition": "unresolved_conflict",
        "confirmed": [
            "Splunk contains unauthorized-access telemetry involving OT device identity OT-RTU-14 / 10.80.4.14",
            "CMDB lists OT-RTU-14 as retired",
        ],
        "supported": ["The two sources currently conflict"],
        "unconfirmed": [
            "Whether the device is actually active",
            "Whether telemetry belongs to a recycled identity",
            "Whether this is a real incident",
        ],
        "missing_evidence": ["OT inventory", "Firewall segmentation", "Switch ARP/MAC", "Ownership confirmation"],
        "forced_incident": False,
        "production_investigation_outcome_unused": True,
    }


def _base_state() -> list[dict[str, Any]]:
    return [
        C.state_item("splunk", "Splunk OT access telemetry", "OBTAINED", "Unauthorized access events for OT-RTU-14"),
        C.state_item("cmdb", "CMDB asset record", "CONFLICTING", "retired"),
        C.state_item("ot_inventory", "OT inventory", "MISSING", "Not queried"),
        C.state_item("firewall", "Firewall segmentation", "MISSING", "Not queried"),
        C.state_item("arp", "Switch ARP/MAC", "MISSING", "Not queried"),
        C.state_item("ot_team", "OT team confirmation", "MISSING", "Not requested"),
    ]


def _apply(applied: list[str], session_id: str, outcome: dict[str, Any], state: list[dict[str, Any]], extra: list[dict[str, Any]]) -> None:
    if "check_ot_inventory" in applied:
        C.set_status(state, "ot_inventory", "OBTAINED", "OT inventory shows OT-RTU-14 active on cell 4")
        extra.append(C.evidence("ev-s7-otinv", "ot_inventory_fixture", "OT inventory", [{"asset": "OT-RTU-14", "status": "active", "cell": 4}], provenance="simulated_mcp"))
        outcome["path"] = "A"
        outcome["disposition"] = "suspicious"
        outcome["confirmed"].append("OT inventory contradicts CMDB retirement — device appears active")
        outcome["unconfirmed"] = ["Whether unauthorized access is malicious vs mis-documented maintenance"]
        C.set_status(state, "cmdb", "CONFLICTING", "CMDB retired vs OT inventory active — CMDB likely stale")

    if "check_firewall_activity" in applied:
        C.set_status(state, "firewall", "OBTAINED", "East-west OT allow to 10.80.4.14 in the same window")
        extra.append(C.evidence("ev-s7-fw", "firewall_fixture", "Firewall segmentation", [{"dest": "10.80.4.14", "action": "allow", "src_zone": "ot-eng"}], provenance="simulated_mcp"))

    if "check_arp_mac" in applied:
        C.set_status(state, "arp", "OBTAINED", "MAC 00:1b:44:11:3a:b7 still answering on the OT VLAN")
        extra.append(C.evidence("ev-s7-arp", "network_fixture", "Switch ARP/MAC", [{"ip": "10.80.4.14", "mac": "00:1b:44:11:3a:b7", "vlan": "ot-4"}], provenance="simulated_mcp"))

    if "ask_ot_team" in applied:
        email_extra = ec_email_drafts.s7_ot_team_email(applied=applied)
        C.ensure_hil_action(
            kind="email_send",
            label="Ask OT team about OT-RTU-14",
            session_id=session_id,
            scenario_id=S7_SCENARIO_ID,
            extra=email_extra,
        )
        C.set_status(state, "ot_team", "AWAITING_EXTERNAL_RESPONSE", "Draft prepared for OT_TEAM; inbound reply is fixture-backed")

    if "ingest_ot_response" in applied:
        if "check_ot_inventory" in applied:
            extra.append(C.evidence("ev-s7-ot-a", "email_mcp_fixture", "OT team response", [{"body": "Device was never decommissioned; CMDB was not updated after a cell move."}], provenance="experience_center_fixture"))
            C.set_status(state, "ot_team", "OBTAINED", "OT team confirms device is active; CMDB stale")
            outcome["disposition"] = "confirmed"
            outcome["confirmed"].append("OT team confirms the device is active and CMDB is stale")
            outcome["path"] = "A"
        else:
            extra.append(C.evidence("ev-s7-ot-b", "email_mcp_fixture", "OT team response", [{"body": "Identity was recycled; telemetry is from a lab simulator using the old asset tag."}], provenance="experience_center_fixture"))
            C.set_status(state, "ot_team", "OBTAINED", "OT team reports recycled identity")
            outcome["path"] = "B"
            outcome["disposition"] = "not_an_incident"
            outcome["confirmed"] = [
                "Telemetry exists",
                "CMDB retired record is consistent with a recycled identity",
                "No active compromise on a live OT device",
            ]
            outcome["unconfirmed"] = []
            C.set_status(state, "cmdb", "OBTAINED", "Retirement stands; identity was recycled")

    if "confirm_stale_identity" in applied:
        outcome["path"] = "B"
        outcome["disposition"] = "not_an_incident"
        C.set_status(state, "ot_inventory", "OBTAINED", "No live asset behind OT-RTU-14")
        C.set_status(state, "cmdb", "OBTAINED", "Retirement stands; identity recycled")
        extra.append(C.evidence("ev-s7-stale", "ot_inventory_fixture", "Recycled identity", [{"asset": "OT-RTU-14", "status": "retired_identity_recycled"}], provenance="simulated_mcp"))
        outcome["confirmed"] = [
            "Telemetry belongs to a recycled/stale asset identity",
            "No active compromise",
        ]
        outcome["forced_incident"] = False
        outcome["data_quality_recommendation"] = "Correct CMDB / identity reuse process"

    if "generate_closure_summary" in applied:
        if outcome.get("path") == "A":
            outcome["closure_summary"] = (
                "Path A: device is active and CMDB is stale. Security incident is appropriate after conflict resolution."
            )
        elif outcome.get("path") == "B":
            outcome["closure_summary"] = (
                "Path B: recycled/stale identity. No active incident. Data-quality correction is the right ticket."
            )
        else:
            outcome["closure_summary"] = (
                "Conflict is unresolved. Do not force remediation or an incident until Path A or B is evidenced."
            )

    if "create_incident_ticket" in applied and outcome.get("path") == "A":
        C.ensure_executed_action(
            kind="ticket_create",
            label="Create OT unauthorized-access incident",
            session_id=session_id,
            scenario_id=S7_SCENARIO_ID,
            extra={"ticket": {"id": "INC-OT-14", "reason": "active device, stale CMDB"}},
        )
        outcome["ticket_id"] = "INC-OT-14"

    if "recommend_cmdb_correction" in applied:
        C.ensure_executed_action(
            kind="ticket_create",
            label="Open CMDB data-quality ticket",
            session_id=session_id,
            scenario_id=S7_SCENARIO_ID,
            extra={"ticket": {"id": "CHG-CMDB-14", "type": "data_quality"}},
        )


def build_s7_turn(*, session_id: str, turn: int, applied_follow_up_ids: list[str], pending_action_id: str | None = None, awaiting_external: bool = False):
    applied = list(applied_follow_up_ids)
    outcome = deepcopy(_base_outcome())
    state = deepcopy(_base_state())
    extra: list[dict[str, Any]] = []
    _apply(applied, session_id, outcome, state, extra)
    source = [
        C.evidence("ev-s7-splunk", "splunk_mcp_fixture", "Unauthorized OT access", [{"asset": "OT-RTU-14", "ip": "10.80.4.14", "signature": "unauthorized_ot_access"}], provenance="simulated_mcp"),
        C.evidence("ev-s7-cmdb", "cmdb_fixture", "CMDB", [{"asset": "OT-RTU-14", "status": "retired"}], provenance="simulated_mcp"),
        *extra,
    ]
    return C.envelope(
        scenario_id=S7_SCENARIO_ID,
        family=S7_FAMILY,
        session_id=session_id,
        turn=turn,
        applied=applied,
        chips=_visible_chips(applied),
        title="Splunk vs CMDB conflict — do not force an incident",
        assessment=(
            "Splunk shows unauthorized access involving OT-RTU-14, while the asset system lists the device as retired. "
            "Those sources conflict. This is not automatically a confirmed incident."
        ),
        found="Confirmed conflict between telemetry and CMDB. Additional evidence is required before disposition.",
        outcome=outcome,
        evidence_state=state,
        source_evidence=source,
        actions=C.actions_for(session_id, S7_SCENARIO_ID),
        resources=["Splunk", "CMDB", "OT inventory", "firewall", "ARP/MAC", "OT team email"],
        controls=["No forced incident", "ticket only after an appropriate outcome"],
        pending_action_id=pending_action_id,
        awaiting_external=awaiting_external or any(item["status"] == "AWAITING_EXTERNAL_RESPONSE" for item in state),
        extra={
            "ec_conflict": {"status": "CONFLICTING", "sources": ["splunk", "cmdb"]},
            "ec_path": outcome.get("path"),
            "ec_investigation_pivot": build_s7_investigation_pivot().model_dump(),
            "ec_action_readiness": [row.model_dump() for row in build_s7_action_readiness(applied, outcome)],
            "ec_status_summary": build_s7_status_summary(outcome),
            **(
                {
                    "ec_email": {
                        "to": "OT_TEAM",
                        "logical_recipient": "OT_TEAM",
                        "status": "draft_pending_send",
                        "not_transmitted": True,
                        "inbound_fixture_backed": "ingest_ot_response" in applied,
                    }
                }
                if "ask_ot_team" in applied
                else {}
            ),
        },
        journey=journey_for(S7_SCENARIO_ID, applied),
        recommended=[
            "Check OT inventory",
            "Check firewall and ARP/MAC",
            "Ask the OT team",
            "Create an incident only if the device is confirmed active",
        ],
        important=["CMDB says retired", "Splunk shows activity", "Conflict is explicit"],
        table=[
            {"Source": "Splunk", "Finding": "Unauthorized access OT-RTU-14", "State": "Confirmed telemetry"},
            {"Source": "CMDB", "Finding": "retired", "State": "CONFLICTING"},
        ],
        layer2_path=list(S7_LAYER2_PATH),
    )


def s7_analyst_override(scenario_id: str, base: dict[str, Any]) -> dict[str, Any] | None:
    if scenario_id != S7_SCENARIO_ID:
        return None
    env = build_s7_turn(session_id="s7-override", turn=0, applied_follow_up_ids=[])
    return {**base, **(env.analyst or {})}


def build_s7_demo_scenarios() -> dict[str, Any]:
    return {
        S7_SCENARIO_ID: C.demo_scenario(
            scenario_id=S7_SCENARIO_ID,
            label="S7 · Conflicting evidence",
            query=S7_QUERY,
            demo_order=7,
            family=S7_FAMILY,
            summary="Splunk vs retired CMDB. Conflict is explicit. No forced incident.",
        )
    }
