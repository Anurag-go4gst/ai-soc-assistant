"""S1 agent step definitions — newly observed IP / SOP monitoring."""

from __future__ import annotations

from typing import Any

from app.demo.ec_mcp_lifecycle_fixture import PRIMARY_ATTACKER_IP

S1_SCENARIO_ID = "s1_governed_splunk_investigation"
S1_FAMILY = "s1_governed_splunk"

INVESTIGATION_STEP_DEFS: tuple[dict[str, Any], ...] = (
    {
        "id": "mcp_identity",
        "title": "Who owns this IP?",
        "summary": "Look it up in the asset inventory (SOC-KB).",
        "follow_up_id": "lookup_inventory_identity",
        "tools": ["SOC-KB"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "requested_30d",
        "title": "What did it do in the last 30 days?",
        "summary": "Firewall traffic to and from the IP, whether it is new, and whether threat intel or our detections flag it.",
        "follow_up_id": "search_firewall_30d",
        # Novelty rides the same search; TI and detection-coverage checks are folded in.
        "also_applies": ("check_threat_intel", "review_existing_notable"),
        "tools": ["Splunk MCP"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "retrieve_sop",
        "title": "What does our SOP say to do?",
        "summary": "Newly observed external endpoint SOP.",
        "follow_up_id": "retrieve_sop",
        "tools": ["SOC-KB"],
        "default_selected": True,
        "phase": "investigation",
    },
)

ADAPTATION_STEP: dict[str, Any] = {
    "id": "permitted_sessions",
    "title": "Investigate permitted sessions and authentication",
    "added_by_agent": True,
    "reason": (
        "Added because three permitted sessions reached a high-criticality jump host. "
        "Denied volume must not hide successful communication."
    ),
    "summary": "Read-only Splunk drill of the three allowed sessions plus auth correlation.",
    "follow_up_id": "investigate_permitted_sessions",
    "tools": ["Splunk MCP"],
    "default_selected": False,
    "phase": "investigation",
}

REMEDIATION_STEP_DEFS: tuple[dict[str, Any], ...] = (
    {
        "id": "generate_spl",
        "title": "Put a 14-day Splunk watch on the IP and jump host 10.20.1.10",
        "summary": "Alert on any session from 198.51.100.42 to jump host 10.20.1.10 (443/8443) and any svc_jump_ops logon.",
        "follow_up_id": "prepare_monitoring_detection",
        "also_applies": ("raise_mcp_monitoring", "monitor_affected_hosts"),
        "tools": ["Splunk MCP"],
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "create_incident",
        "title": "Open an incident",
        "summary": "Record the 3 unexplained sessions; not closed as malicious.",
        "follow_up_id": "create_incident_ticket",
        "tools": ["ITSM"],
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "notify_firewall",
        "title": "Email the SOC lead and ask the integration owner about the sessions",
        "summary": "No block — the SOP threshold is not met.",
        "follow_up_id": "email_firewall_team",
        # The block decision (not required) and the incident update are recorded, not separate steps.
        "also_applies": ("prepare_firewall_block", "update_incident"),
        "tools": ["Email"],
        "hil_required": True,
        "default_selected": True,
        "phase": "remediation",
    },
)

INVESTIGATION_PLAN_SUMMARY = (
    "Identify the IP, search the last 30 days, investigate any permitted sessions, "
    "check novelty and local TI, then assess existing Splunk detection coverage and retrieve the SOP."
)
ACTION_PLAN_SUMMARY = (
    "Start with identity and observed activity, not existing detections. "
    "If permitted sessions appear, investigate them. SOP default is targeted monitoring; "
    "blocking requires a defined threshold plus Network/SOC approval."
)
CONVERSATIONAL_FOLLOWUPS = frozenset({"generate_executive_summary"})

OPENING_NARRATIVE = (
    f"To check and verify whether the newly observed IP {PRIMARY_ATTACKER_IP} is malicious over the "
    "last 30 days, and to follow the standard SOP to raise monitoring and block it if required, "
    "you can follow these steps using Splunk and MCP Tools and RAG Guidelines.\n\n"
    "This investigation first identifies the IP and its expected role, then reviews last-30-days "
    "network activity. If anything is permitted, those sessions and related authentication are "
    "investigated. Next it checks whether the IP is genuinely new, whether it is listed in local "
    "threat intelligence, whether existing Splunk detections would have alerted, and what the "
    "enterprise monitoring-and-blocking SOP requires. No alert is not proof the IP is benign."
)
BRIEF = {
    "what_i_know": [
        f"Newly observed IP {PRIMARY_ATTACKER_IP}",
        "Analyst asked for the last 30 days",
        "Existing known-malicious-IP detections are IOC-based",
        "No live MCP, live LLM, or internet reputation services on this Experience Center path",
    ],
    "objective": [
        "Who is this IP, and what is its expected role?",
        "What did it do in the last 30 days — did anything succeed?",
        "Is it new, and is it known bad?",
        "Would existing detections catch it, and what does SOP require?",
    ],
}
ACTION_PLAN_STEPS = [
    "Identify the IP and its expected role from inventory/SOC-KB",
    "Investigate last-30-days network activity; if permits appear, investigate them and authentication",
    "Check historical novelty and local threat intelligence (unlisted ≠ benign)",
    "Assess existing Splunk IOC detection coverage (no alert ≠ safe)",
    "Retrieve the SOP: 14-day targeted monitoring; HIL block only if a threshold is met",
]

PLAN_PREREAD: tuple[str, ...] = ()

PLAN_READY_TITLE = f"Newly observed IP {PRIMARY_ATTACKER_IP} — malicious use not confirmed"
IDENTITY_PROMOTION = "Identity: partner API endpoint (Northwind Logistics)"
SEVERITY_LABEL = "P2 High"
SEVERITY_REASON = (
    "P2 High · newly observed external endpoint · permitted access to high-criticality jump host · "
    "malicious use unconfirmed"
)
