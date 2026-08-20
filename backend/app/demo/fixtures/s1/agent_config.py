"""S1 agent step definitions — newly observed IP / SOP monitoring."""

from __future__ import annotations

from typing import Any

from app.demo.ec_mcp_lifecycle_fixture import PRIMARY_ATTACKER_IP

S1_SCENARIO_ID = "s1_governed_splunk_investigation"
S1_FAMILY = "s1_governed_splunk"

INVESTIGATION_STEP_DEFS: tuple[dict[str, Any], ...] = (
    {
        "id": "mcp_identity",
        "title": "Identify the IP and its expected role",
        "summary": "SOC-KB / inventory fixture — establish whether this IP is a registered MCP endpoint.",
        "follow_up_id": "lookup_inventory_identity",
        "tools": ["SOC-KB"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "requested_30d",
        "title": "Investigate network activity — last 30 days",
        "summary": "Governed Splunk search for the analyst-requested window. Candidate SPL stays non-executable.",
        "follow_up_id": "search_firewall_30d",
        "tools": ["Splunk MCP"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "novelty_window",
        "title": "Check historical activity / novelty",
        "summary": "Second bounded search: is this IP newly observed, or already in the prior window?",
        "follow_up_id": None,
        "bundle_with": "search_firewall_30d",
        "tools": ["Splunk MCP"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "threat_intel",
        "title": "Check local threat intelligence",
        "summary": "Local IOC / TI fixture only. No internet reputation services.",
        "follow_up_id": "check_threat_intel",
        "tools": ["SOC-KB"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "evaluate_notable",
        "title": "Assess existing Splunk detection coverage",
        "summary": (
            "Check whether existing known-malicious-IP/IOC detections cover this indicator "
            "and whether an alert was generated. No alert is not proof the IP is benign."
        ),
        "follow_up_id": "review_existing_notable",
        "tools": ["Splunk MCP"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "retrieve_sop",
        "title": "Retrieve monitoring and blocking SOP",
        "summary": "Governed SOC-KB retrieval of the enterprise newly observed external / MCP endpoint SOP.",
        "follow_up_id": "retrieve_sop",
        "tools": ["SOC-KB"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "privileged_accounts",
        "title": "Review privileged-account context",
        "summary": "Optional IAM class check. No IAM MCP is onboarded.",
        "follow_up_id": "check_privileged_accounts",
        "tools": ["IAM (simulated)"],
        "default_selected": False,
        "phase": "investigation",
    },
    {
        "id": "endpoint_activity",
        "title": "Check endpoint activity on the jump host",
        "summary": "Optional. No EDR MCP is onboarded — do not invent an EDR connector.",
        "follow_up_id": "check_endpoint_activity",
        "tools": ["EDR (simulated)"],
        "default_selected": False,
        "phase": "investigation",
    },
    {
        "id": "previous_incidents",
        "title": "Compare with previous incidents",
        "summary": "Optional historical ticket overlap. Campaign linkage stays unconfirmed.",
        "follow_up_id": "compare_previous_incidents",
        "tools": ["ITSM (simulated)"],
        "default_selected": False,
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
        "title": "Generate 14-day monitoring SPL",
        "summary": "Governed Splunk query for 198.51.100.42, jump-host 10.20.1.10 ports 443/8443, and svc_jump_ops auth.",
        "follow_up_id": "prepare_monitoring_detection",
        "tools": ["Splunk MCP"],
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "validate_spl",
        "title": "Validate monitoring SPL",
        "summary": "Deterministic validate_spl on the 14-day monitoring candidate.",
        "follow_up_id": None,
        "bundle_with": "prepare_monitoring_detection",
        "tools": ["SPL validator"],
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "deploy_monitoring",
        "title": "Run baseline monitoring query",
        "summary": "Execute the 14-day watch candidate via splunk_run_query (MCP has no saved-search deploy tool).",
        "follow_up_id": "raise_mcp_monitoring",
        "tools": ["Splunk MCP · splunk_run_query"],
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "verify_monitoring",
        "title": "Verify baseline query results",
        "summary": "Replay splunk_run_query and confirm row counts before scheduling the saved search manually.",
        "follow_up_id": None,
        "bundle_with": "raise_mcp_monitoring",
        "tools": ["Splunk MCP · splunk_run_query"],
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "monitor_14d",
        "title": "Monitor 198.51.100.42 → 10.20.1.10 443/8443 and svc_jump_ops",
        "summary": "Watch permitted jump-host 10.20.1.10 activity on 443/8443 and correlate svc_jump_ops authentication.",
        "follow_up_id": "monitor_affected_hosts",
        "tools": ["Splunk MCP"],
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "create_incident",
        "title": "Create incident with investigation evidence",
        "summary": "Record confirmed vs unconfirmed findings. Do not close as malicious.",
        "follow_up_id": "create_incident_ticket",
        "tools": ["ITSM"],
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "notify_firewall",
        "title": "Notify SOC team",
        "summary": "Notify SOC that 14-day monitoring is active. Block approval is not requested.",
        "follow_up_id": "email_firewall_team",
        "tools": ["Email"],
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "prepare_block",
        "title": "Conditional IP block",
        "summary": "SOP blocking threshold is not met — do not execute a firewall block.",
        "follow_up_id": "prepare_firewall_block",
        "tools": ["SOAR / firewall"],
        "hil_required": True,
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "update_ticket",
        "title": "Update incident with final outcome",
        "summary": "Monitoring active; malicious use unconfirmed; block threshold not met.",
        "follow_up_id": "update_incident",
        "tools": ["ITSM"],
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
IDENTITY_PROMOTION = "Identity: registered MCP endpoint"
SEVERITY_LABEL = "P2 High"
SEVERITY_REASON = (
    "P2 High · newly observed external endpoint · permitted access to high-criticality jump host · "
    "malicious use unconfirmed"
)
