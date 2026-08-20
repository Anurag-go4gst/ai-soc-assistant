"""S7 agent step definitions — Splunk vs retired CMDB conflict."""

from __future__ import annotations

from typing import Any

S7_SCENARIO_ID = "s7_conflicting_ot_evidence"
S7_FAMILY = "s7_conflicting_evidence"

INVESTIGATION_STEP_DEFS: tuple[dict[str, Any], ...] = (
    {
        "id": "replay_splunk",
        "title": "Replay Splunk unauthorized-access telemetry",
        "summary": "Confirm Splunk events for OT-RTU-14 / 10.80.4.14 before treating CMDB as authority.",
        "follow_up_id": "review_splunk_telemetry",
        "tools": ["Splunk MCP"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "load_cmdb",
        "title": "Load CMDB retirement record",
        "summary": "Read the OT-RTU-14 asset record. There is no CMDB MCP — this is a simulated inventory lookup.",
        "follow_up_id": "review_cmdb_record",
        "tools": ["CMDB (simulated)"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "ot_inventory",
        "title": "Check live OT inventory",
        "summary": "Independent of CMDB: is OT-RTU-14 still present on the OT cell? No OT-inventory MCP is onboarded.",
        "follow_up_id": "check_ot_inventory",
        "tools": ["OT inventory (simulated)"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "firewall_window",
        "title": "Check firewall segmentation in the same window",
        "summary": "East-west OT allows to 10.80.4.14 from Splunk-indexed firewall telemetry.",
        "follow_up_id": "check_firewall_activity",
        "tools": ["Splunk MCP"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "arp_mac",
        "title": "Check switch ARP/MAC",
        "summary": "Confirm whether 10.80.4.14 is still answering on the OT VLAN. No network/switch MCP is onboarded.",
        "follow_up_id": "check_arp_mac",
        "tools": ["Network (simulated)"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "stale_identity",
        "title": "Confirm recycled / stale identity (Path B)",
        "summary": "Alternate path: telemetry belongs to a recycled asset tag, not a live device. Off by default.",
        "follow_up_id": "confirm_stale_identity",
        "tools": ["OT inventory (simulated)"],
        "default_selected": False,
        "phase": "investigation",
    },
)

REMEDIATION_STEP_DEFS: tuple[dict[str, Any], ...] = (
    {
        "id": "ask_ot",
        "title": "Ask the OT team",
        "summary": "HIL-gated email to OT_TEAM. Confirm whether OT-RTU-14 is active or the identity was recycled.",
        "follow_up_id": "ask_ot_team",
        "tools": ["Email (allowlisted SMTP)"],
        "hil_required": True,
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "ingest_ot",
        "title": "Ingest OT team response",
        "summary": "Fixture-backed inbound reply — not a live mailbox poll.",
        "follow_up_id": "ingest_ot_response",
        "tools": ["Email (allowlisted SMTP)"],
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "create_incident",
        "title": "Create security incident",
        "summary": "Path A only: device is active and CMDB is stale. Splunk alone must not mint this ticket.",
        "follow_up_id": "create_incident_ticket",
        "tools": ["ITSM (simulated)"],
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "cmdb_correction",
        "title": "Open CMDB data-quality ticket",
        "summary": "Retirement record is stale (Path A) or identity reuse needs a process fix (Path B).",
        "follow_up_id": "recommend_cmdb_correction",
        "tools": ["ITSM (simulated)"],
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "closure",
        "title": "Generate closure summary",
        "summary": "Close with an honest disposition: real concern vs recycled identity — never Splunk-alone.",
        "follow_up_id": "generate_closure_summary",
        "tools": [],
        "default_selected": True,
        "phase": "remediation",
    },
)

INVESTIGATION_PLAN_SUMMARY = (
    "Reconcile Splunk unauthorized-access telemetry with the retired CMDB record using independent "
    "OT inventory and network evidence. Do not force an incident from Splunk alone."
)
ACTION_PLAN_SUMMARY = (
    "Confirm the conflict, then check whether the device is actually live before choosing incident "
    "vs data-quality."
)
CONVERSATIONAL_FOLLOWUPS = frozenset({"generate_executive_summary"})

OPENING_NARRATIVE = (
    "To determine whether the unauthorized access to an OT (Operational Technology) device reported "
    "by Splunk is a real incident, despite the asset system indicating the device was retired, you "
    "can follow these steps using Splunk and MCP Tools and RAG Guidelines.\n\n"
    "This investigation would typically involve reconciling Splunk telemetry with the asset record, "
    "then gathering independent OT inventory and network evidence before treating the alert as an incident."
)
BRIEF = {
    "what_i_know": [
        "Splunk unauthorized-access telemetry for OT-RTU-14 / 10.80.4.14",
        "CMDB lists OT-RTU-14 as retired",
        "The two sources conflict — Splunk alone is not enough",
        "No live MCP or live LLM on this Experience Center path",
    ],
    "objective": [
        "Is the device actually active?",
        "Does the telemetry belong to a recycled identity?",
        "Is this a real incident, or a data-quality issue?",
    ],
}
ACTION_PLAN_STEPS = [
    "Replay Splunk unauthorized-access events and the CMDB retirement record",
    "Check live OT inventory, then firewall and ARP/MAC in the same window",
    "Ask OT to confirm active-vs-recycled before forcing an incident",
    "Open a security incident only if the device is live; otherwise a CMDB correction",
]

PLAN_PREREAD: tuple[str, ...] = ()
