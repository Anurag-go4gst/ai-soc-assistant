"""S7 CIO layer — Splunk shows OT access, the CMDB says the device was retired."""

from __future__ import annotations

from app.demo.ec_agent.cio_content import CioContent, register_cio_content
from app.demo.fixtures.s7.agent_config import S7_SCENARIO_ID

S7_CIO_CONTENT = CioContent(
    scenario_id=S7_SCENARIO_ID,
    opening_narrative=(
        "Two of our systems disagree: Splunk shows unauthorized access to OT-RTU-14, and the CMDB "
        "says that device was retired. My plan settles which one is right using three independent "
        "sources — OT inventory, firewall logs and the switch — then finds who accessed the device. "
        "Nothing runs until you approve."
    ),
    step_summary={
        "load_cmdb": "Read the OT-RTU-14 asset record, including its retirement date and owner.",
        "ot_inventory": "Check the OT inventory for OT-RTU-14 on its cell, independently of the CMDB.",
        "arp_mac": "Check whether anything still answers on 10.80.4.14 on the OT VLAN.",
        "stale_identity": "Alternative explanation: the telemetry belongs to a reused asset tag, not a live device. Off by default.",
    },
    step_why={
        "replay_splunk": {
            "rationale": "Confirms the alert is real telemetry before we spend effort reconciling it.",
            "decides": "Whether there is anything to investigate.",
            "if_skipped": "We could chase a parsing error.",
        },
        "load_cmdb": {
            "rationale": "The CMDB is the source that contradicts Splunk; we need its exact claim (retired when, by whom).",
            "decides": "What exactly the conflict is.",
            "if_skipped": "We would be arguing with an assumption.",
        },
        "ot_inventory": {
            "rationale": "Independent tie-breaker: OT inventory sees what is physically on the cell.",
            "decides": "Live device (CMDB stale) vs retired device (telemetry stale).",
            "if_skipped": "The conflict stays unresolved.",
        },
        "firewall_window": {
            "rationale": "Shows whether a network path to the device was open when the access happened.",
            "decides": "Whether the access was possible, not just logged.",
            "if_skipped": "We could not rule out a logging artefact.",
        },
        "arp_mac": {
            "rationale": "A device that answers ARP is on the network right now — the strongest proof it is live.",
            "decides": "Confirms or refutes 'retired'.",
            "if_skipped": "Liveness rests on OT inventory alone.",
        },
        "stale_identity": {
            "rationale": "Only worth running if the live checks said the device is gone; they said it is live.",
            "decides": "Recycled identity vs live device.",
            "if_skipped": "Nothing lost on the default path.",
        },
        "identify_source": {
            "rationale": "A live OT device with unauthorized access: who accessed it is the question that decides the response.",
            "decides": "Maintenance by a known engineer vs an unknown actor.",
            "if_skipped": "We would contain without knowing whom we are containing.",
        },
        "ask_ot": {
            "rationale": "The OT team can confirm whether any authorized maintenance explains the access.",
            "reversible": "No — once sent, an email cannot be recalled.",
            "approver": "SOC analyst (explicit Send)",
            "risk_if_skipped": "We could treat planned maintenance as an attack.",
        },
        "ingest_ot": {
            "rationale": "The OT reply is evidence; it is recorded before any containment decision.",
            "reversible": "Yes — record only.",
            "approver": "SOC analyst",
            "risk_if_skipped": "The decision would ignore the device owner.",
        },
        "create_incident": {
            "rationale": "Unauthorized access to a live substation RTU is a security incident, not a data-quality issue.",
            "reversible": "Yes — can be downgraded if OT confirms maintenance.",
            "approver": "SOC lead",
            "risk_if_skipped": "OT exposure with no owner.",
        },
        "restrict_ot_path": {
            "rationale": "The firewall still allows east-west traffic to 10.80.4.14. Narrowing it to the engineering workstation closes the path used.",
            "reversible": "Yes — rule change with rollback; applied in an OT-safe window.",
            "approver": "OT engineering + firewall change owner",
            "risk_if_skipped": "The same path stays open to the same actor.",
        },
        "rtu_integrity": {
            "rationale": "On OT devices the damage is to logic and setpoints, not data; the RTU configuration must be compared to its baseline.",
            "reversible": "Yes — read-only comparison.",
            "approver": "OT engineering",
            "risk_if_skipped": "A tampered setpoint could go unnoticed until it causes an outage.",
        },
        "cmdb_correction": {
            "rationale": "A live device marked retired gets no patches or monitoring; fixing the record removes the blind spot.",
            "reversible": "Yes — record update.",
            "approver": "CMDB owner",
            "risk_if_skipped": "The next alert on this device will be dismissed the same way.",
        },
        "closure": {
            "rationale": "Records the resolved conflict and the actions taken.",
            "reversible": "Yes — can be reopened.",
            "approver": "SOC lead",
            "risk_if_skipped": "No record of why the CMDB was wrong.",
        },
    },
    executive_brief={
        "investigation": {
            "verdict": "Real incident: OT-RTU-14 is live and was accessed without authorization. The CMDB record saying it was retired is wrong.",
            "business_impact": "OT-RTU-14 controls equipment at substation cell 4. A device we believed retired has had no patching or monitoring, and it is still reachable.",
            "risk_from": "HIGH",
            "risk_to": "HIGH",
            "confidence": "High — OT inventory, firewall allows and ARP/MAC all show the device is live.",
            "would_change_if": "The OT team confirms authorized maintenance from a known workstation → downgrade to a process issue.",
            "decision_needed": "Approve: open an incident, narrow the firewall path, check the RTU configuration, and correct the CMDB.",
            "will_not_do": "Power down or isolate the RTU without OT engineering — that could interrupt the substation.",
        },
        "complete": {
            "verdict": "Incident open, access path narrowed, RTU configuration checked against baseline, CMDB corrected.",
            "business_impact": "Substation operation uninterrupted. The device is back under monitoring and patch management.",
            "risk_from": "HIGH",
            "risk_to": "MEDIUM",
            "confidence": "High.",
            "would_change_if": "The source of access turns out to be unknown or external.",
            "decision_needed": "None now. OT engineering to confirm the RTU baseline within 24 hours.",
            "will_not_do": "Close the incident until the source of access is identified.",
        },
    },
)

register_cio_content(S7_CIO_CONTENT)
