"""S7 — Splunk sees access to an OT device the asset system says is retired."""

from __future__ import annotations

from app.demo import ec_environment as E
from app.demo.ec_agent.spec_engine import Action, Check, Email, ScenarioSpec

RTU = E.OT_RTU

S7 = ScenarioSpec(
    scenario_id="s7_conflicting_ot_evidence",
    family="s7_conflicting_evidence",
    label="S7 · OT device the asset system says is retired",
    question=(
        "Splunk shows access to one of our substation OT devices, but the asset system says that device was "
        "retired. Is this a real incident?"
    ),
    legacy_phrasings=(
        'Splunk shows unauthorized access to an OT device, but the asset system says the device was retired. Determine whether this is a real incident.',
    ),
    demo_order=7,
    plan_title="Access to a 'retired' OT device — plan ready",
    plan_intro=(
        "I'll look at what Splunk recorded, what the asset record says, and whether a device still answers at "
        "that address. Nothing runs until you approve."
    ),
    checks=(
        Check(
            id="splunk_activity",
            title="What did Splunk record?",
            plan="Search OT network monitoring for traffic to the device in the last 24 hours.",
            tool="splunk_mcp",
            spl=(
                f'search index=ot_ids sourcetype=ot:ids dest_ip="{E.OT_RTU_IP}" earliest=-24h latest=now '
                "| stats count by src_ip, protocol, function | head 50"
            ),
            result=(
                f"14 Modbus write requests from engineering workstation {E.OT_EWS} to {RTU} ({E.OT_RTU_IP}) between "
                "{D-1 22:40} and {D-1 22:52}."
            ),
            evidence=(
                "The OT sensor saw the requests but not the replies",
                f"Firewall {E.OT_FIREWALL} permits {E.OT_EWS} to the whole RTU subnet",
            ),
            attention="ATTENTION",
        ),
        Check(
            id="asset_record",
            title="What does the asset record say?",
            plan=f"Read the CMDB record and decommission change for {RTU}.",
            tool="itsm",
            operation=f"itsm.cmdb_read · {RTU}",
            result=(
                f"CMDB marks {RTU} retired on {{D-23}}, but its decommission change is still 'Scheduled', not "
                "'Completed'."
            ),
            evidence=("The record was updated before the field work was done",),
        ),
        Check(
            id="device_present",
            title="Is anything still answering at that address?",
            plan=f"Read the substation access switch's address table for {E.OT_RTU_IP}.",
            tool="agilus_mcp",
            operation="agilus.read_device · SUB07 access switch (MAC/ARP table)",
            result=(
                f"Yes. The switch still sees a device at {E.OT_RTU_IP} on port Gi1/0/14, and its hardware address "
                "belongs to the RTU's manufacturer."
            ),
            evidence=("Port Gi1/0/14 up since {D-60}",),
            attention="RISK",
        ),
    ),
    added_check=Check(
        id="who_used_ews",
        title=f"Who was using {E.OT_EWS} at the time?",
        plan=f"Check logons on {E.OT_EWS} around the write requests.",
        tool="splunk_mcp",
        spl=(
            f'search index=wineventlog sourcetype=WinEventLog:Security host="{E.OT_EWS}" EventCode=4624 '
            "earliest=-24h latest=now | stats count by user, logon_type | head 50"
        ),
        result=(
            "Engineer account eng_sub07 logged on at the console at {D-1 22:31}. The maintenance calendar has no work "
            "booked for that night."
        ),
        evidence=("Console logon — someone was physically at the substation workstation",),
    ),
    added_after="device_present",
    added_when=("device_present",),
    conclusion_headline=(
        f"Real device, wrong record: {RTU} is still live despite being marked retired, and it received write "
        "requests outside any maintenance window."
    ),
    points=(
        f"Confirmed: a device of the RTU's make still answers at {E.OT_RTU_IP}; the CMDB record is wrong.",
        f"Confirmed: the writes came from {E.OT_EWS} during a console session by eng_sub07.",
        "Inference: this may be unplanned engineering work rather than an attack — only the OT team can confirm.",
    ),
    unresolved=(
        f"Whether the write requests changed the RTU's settings — replies aren't logged.",
        "Whether eng_sub07's session was authorised.",
    ),
    threat="Suspected",
    asset_tier=1,
    evidence_state="unexplained_access",
    subject=f"{RTU} ({E.OT_RTU_IP})",
    decision=(
        "Proposed: open a {priority} incident, ask OT on-call to check the device and the engineer's work, request a "
        f"change to limit {E.OT_FIREWALL} to what the workstation needs, and fix the CMDB record."
    ),
    actions=(
        Action(
            id="open_incident",
            title="Open a {priority} incident",
            proposal=f"ITSM incident at {{priority}} ({{priority_basis}}).",
            tool="itsm",
            verb="incident",
            ticket_id=E.INCIDENT_S7,
            executed=f"Incident {E.INCIDENT_S7} opened ({{priority}})",
            verified="read back from ITSM",
        ),
        Action(
            id="ask_ot",
            title="Ask OT on-call to check the device and the engineer's work",
            proposal="Short email to OT on-call, copied to the substation engineering lead.",
            tool="email",
            verb="email",
            email=Email(
                to="OT on-call",
                mailbox="OT_TEAM",
                cc="Substation engineering lead",
                subject=f"[{{incident}}] {RTU} is live and received write requests",
                body=(
                    f"You're receiving this as OT on-call for substation 07.\n\n"
                    f"What we saw: {RTU} ({E.OT_RTU_IP}) is marked retired in CMDB but is still connected. Between "
                    f"{{D-1 22:40}} and {{D-1 22:52}} it received 14 Modbus write requests from {E.OT_EWS}, where "
                    "eng_sub07 was logged on at the console. No maintenance was booked.\n\n"
                    "Please:\n"
                    "1. Check on site whether the RTU's settings changed.\n"
                    "2. Confirm whether eng_sub07's work was authorised.\n\n"
                    "Incident: {incident}\n\n"
                    "SOC Tier 2"
                ),
            ),
            executed="Sent to OT on-call, cc substation engineering lead",
            status_after="AWAITING_REPLY",
        ),
        Action(
            id="restrict_firewall",
            title=f"Request a change to limit {E.OT_FIREWALL}",
            proposal=f"ITSM change for OT and network review: allow {E.OT_EWS} only to RTUs in service.",
            tool="itsm",
            verb="change",
            ticket_id=E.CHANGE_S7_FW,
            assignment_group="OT Engineering",
            executed=f"Change {E.CHANGE_S7_FW} raised for OT change board review",
            status_after="REQUESTED",
        ),
        Action(
            id="fix_cmdb",
            title="Ask for the CMDB record to be corrected",
            proposal=f"ITSM request to asset management: mark {RTU} in service until the decommission is completed.",
            tool="itsm",
            verb="request",
            ticket_id=E.TASK_S7_CMDB,
            assignment_group="Asset Management",
            executed=f"Request {E.TASK_S7_CMDB} raised with asset management",
            status_after="REQUESTED",
        ),
    ),
    final_state="OPEN — AWAITING OT CONFIRMATION",
    final_headline="Incident open; OT on-call asked to check the RTU; firewall change and CMDB fix requested.",
    pending=(
        "OT on-call to check the RTU on site",
        f"{E.CHANGE_S7_FW} awaiting OT change board",
        "Asset management to correct the record",
    ),
    next_triggers="Re-investigate if the OT team finds changed settings, or more writes reach the RTU.",
)
