"""S1 flagship: newly observed IP review (last 30 days + novelty window) as two bounded searches."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from app.demo import ec_actions, ec_email_drafts, ec_fsm_store
from app.demo.ec_journeys import journey_for
from app.demo.ec_mcp_lifecycle_fixture import INCIDENT_ID, PRIMARY_ATTACKER_IP
from app.demo.ec_siem_s1 import (
    S1_DETECTION_NAME,
    S1_LAYER2_PATH,
    S1_SAVED_SEARCH_NAME,
    build_s1_action_readiness,
    build_s1_investigation_pivot,
    build_s1_investigation_scope,
    build_s1_siem_coverage,
    build_s1_tool_traces,
)
from app.demo.ec_response import (
    EcFollowUpChip,
    EcProjection,
    EcProjectionView,
    EcProvenanceStamp,
    EcSessionState,
    ExperienceCenterResponse,
)
from app.demo.fixtures.s1.agent_config import IDENTITY_PROMOTION
from app.demo.fixtures.s1.agent_config import OPENING_NARRATIVE as S1_OPENING_BRIEFING
from app.demo.fixtures.s1.agent_config import PLAN_READY_TITLE, SEVERITY_LABEL, SEVERITY_REASON
from app.demo.fixtures.s1.llm_advisory import (
    candidate_monitoring_spl,
    novelty_window_spl,
    permitted_session_spl,
    requested_30d_spl,
)
from app.demo.fixtures.s1.sop_rag import sop_source_evidence
from app.safeguards.spl_validator import validate_spl
from app.spl.template_registry import get_spl_template, load_spl_templates

S1_SCENARIO_ID = "s1_governed_splunk_investigation"
S1_FAMILY = "s1_governed_splunk"
S1_QUERY = (
    f"We have seen a new IP {PRIMARY_ATTACKER_IP}. Check and verify over the last 30 days whether it is "
    "malicious, and what is the standard SOP to raise monitoring and block it if required."
)

_JUMP = "10.20.1.10"
_HOST_B = "10.20.4.55"
_HOST_C = "10.20.8.90"
_ACCOUNT = "svc_jump_ops"

_SEARCH_1_SPL = novelty_window_spl()
_SEARCH_2_SPL = requested_30d_spl()


def _firewall_template_profile() -> dict[str, Any]:
    template = get_spl_template("firewall_deny_spike")
    if template is None:
        template = next(
            (item for item in load_spl_templates() if item.use_case_id == "net_firewall_deny_spike"),
            None,
        )
    rules = getattr(template, "validation_rules", None) if template is not None else None
    return dict(rules) if isinstance(rules, dict) else {}


def _validate_search(spl: str) -> dict[str, Any]:
    return validate_spl(spl, template_profile=_firewall_template_profile())


def _search_1_rows() -> list[dict[str, Any]]:
    # Prior 30-day novelty window: empty. This IP is newly observed.
    return []


def _search_2_rows() -> list[dict[str, Any]]:
    return [
        {
            "src": PRIMARY_ATTACKER_IP,
            "dest": _JUMP,
            "event_count": 925,
            "deny_count": 922,
            "allow_count": 3,
            "actions": "deny,allow",
            "account": _ACCOUNT,
            "dest_ports": "443,8443",
            "first_seen": "2026-07-18T02:08:00Z",
            "last_seen": "2026-08-16T16:44:00Z",
            "search_window": "earliest=-30d latest=now",
        },
        {
            "src": PRIMARY_ATTACKER_IP,
            "dest": _HOST_B,
            "event_count": 650,
            "deny_count": 650,
            "allow_count": 0,
            "actions": "deny",
            "dest_ports": "22,443",
            "first_seen": "2026-07-19T13:41:00Z",
            "last_seen": "2026-08-15T19:02:00Z",
            "search_window": "earliest=-30d latest=now",
        },
        {
            "src": PRIMARY_ATTACKER_IP,
            "dest": _HOST_C,
            "event_count": 500,
            "deny_count": 500,
            "allow_count": 0,
            "actions": "deny",
            "dest_ports": "3389,443",
            "first_seen": "2026-07-21T08:12:00Z",
            "last_seen": "2026-08-14T22:17:00Z",
            "search_window": "earliest=-30d latest=now",
        },
    ]


def _merged_systems() -> list[dict[str, Any]]:
    return [
        {
            "system": _JUMP,
            "role": "Jump host",
            "activity": "Denied probing plus 3 allowed connections (requested 30-day window)",
            "first_seen": "2026-07-18T02:08:00Z",
            "last_seen": "2026-08-16T16:44:00Z",
            "allowed_denied": "3 allowed / 922 denied",
            "identity_auth_context": f"Firewall telemetry associates {_ACCOUNT} with the 3 allow events",
            "auth_correlation": f"Firewall telemetry associates {_ACCOUNT} with the 3 allow events",
            "risk_note": "Highest-priority host; account use is correlated, not confirmed as compromise",
            "deny_count": 922,
            "allow_count": 3,
            "ports": "443,8443,22",
        },
        {
            "system": _HOST_B,
            "role": "Internal host",
            "activity": "Denied connections only",
            "first_seen": "2026-07-19T13:41:00Z",
            "last_seen": "2026-08-15T19:02:00Z",
            "allowed_denied": "0 allowed / 650 denied",
            "identity_auth_context": "None in firewall results",
            "auth_correlation": "None in firewall results",
            "risk_note": "Perimeter blocks held; no allowed traffic in the requested 30-day window",
            "deny_count": 650,
            "allow_count": 0,
            "ports": "22,443",
        },
        {
            "system": _HOST_C,
            "role": "Internal host",
            "activity": "Denied connections only",
            "first_seen": "2026-07-21T08:12:00Z",
            "last_seen": "2026-08-14T22:17:00Z",
            "allowed_denied": "0 allowed / 500 denied",
            "identity_auth_context": "None in firewall results",
            "auth_correlation": "None in firewall results",
            "risk_note": "RDP/SSL deny pattern; no allowed traffic in the requested 30-day window",
            "deny_count": 500,
            "allow_count": 0,
            "ports": "3389,443",
        },
    ]


def _source_evidence_item(
    evidence_id: str,
    title: str,
    rows: list[dict[str, Any]],
    spl: str,
    window: str,
) -> dict[str, Any]:
    fields = sorted({key for row in rows for key in row})
    return {
        "evidence_id": evidence_id,
        "trace_id": "pending",
        "source_type": "splunk_mcp_fixture",
        "source_name": title,
        "tool_name": "splunk_run_query",
        "collection_status": "collected",
        "query_or_request_summary": f"Splunk MCP search · {window}",
        "executed_spl": spl,
        "result_count": len(rows),
        "fields_returned": fields,
        "preview_rows": rows,
        "raw_result_hash": f"fixture:{evidence_id}",
        "raw_result_stored": False,
        "time_range": window,
        "warnings": ["coe_synthetic_fixture", "no_live_customer_data"],
        "sensitivity_flags": [],
        "tool_category": "read_only_search",
        "provider_used": "splunk_mcp_fixture",
        "saved_search_name": None,
        "output_type": "fixture_preview",
        "provenance": "governed_search",
        "created_at": "2026-08-16T00:00:00Z",
    }


def search_governance_policy() -> dict[str, Any]:
    return {
        "policy_id": "ec_search_governance_policy",
        "provenance": "ec_scenario_policy",
        "kind": "ec_scenario_policy",
        "detail": "ec_search_governance_policy",
        "user_supplied_time_range": True,
        "coverage_days": 60,
        "window_days": 30,
        "split": "30+30",
        "windows": [
            {
                "search_id": "search_1",
                "label": "Prior 30-day novelty window",
                "earliest": "-60d",
                "latest": "-30d",
                "days": 30,
            },
            {
                "search_id": "search_2",
                "label": "Requested last 30 days",
                "earliest": "-30d",
                "latest": "now",
                "days": 30,
            },
        ],
        "index": "pgcil_soc",
        "sourcetype": "pgcil:firewall",
        "forbid_index_wildcard": True,
        "why": (
            "The analyst asked for the last 30 days. A second bounded 30-day window checks whether this IP "
            "is newly observed. Existing IOC-based suspicious-IP notables would not fire for a newly "
            "registered MCP endpoint."
        ),
        "visitor_summary": "Environment search governance applied.",
        "not_production_spl_policy": True,
        "not_production_phase_policy": True,
    }


def _followup_catalog() -> tuple[EcFollowUpChip, ...]:
    return (
        EcFollowUpChip(
            follow_up_id="run_investigation",
            label="Run investigation",
            group="action",
            leads_to_action=True,
        ),
        EcFollowUpChip(
            follow_up_id="create_remediation_plan",
            label="Yes, create remediation plan",
            group="action",
            leads_to_action=True,
        ),
        EcFollowUpChip(
            follow_up_id="decline_remediation_plan",
            label="Not now",
            group="continue",
        ),
        EcFollowUpChip(
            follow_up_id="run_remediation",
            label="Approve remediation",
            group="action",
            leads_to_action=True,
        ),
        EcFollowUpChip(
            follow_up_id="update_investigation_plan",
            label="Update investigation plan",
            group="continue",
        ),
        EcFollowUpChip(
            follow_up_id="update_remediation_plan",
            label="Update remediation plan",
            group="continue",
        ),
        EcFollowUpChip(
            follow_up_id="review_existing_notable",
            label="Assess existing Splunk detection coverage",
            group="continue",
        ),
        EcFollowUpChip(
            follow_up_id="lookup_inventory_identity",
            label="Identify the IP and its expected role",
            group="continue",
        ),
        EcFollowUpChip(
            follow_up_id="search_firewall_30d",
            label="Investigate network activity — last 30 days",
            group="continue",
        ),
        EcFollowUpChip(
            follow_up_id="retrieve_sop",
            label="Retrieve monitoring and blocking SOP",
            group="continue",
        ),
        EcFollowUpChip(
            follow_up_id="investigate_permitted_sessions",
            label="Investigate permitted sessions and authentication",
            group="continue",
        ),
        EcFollowUpChip(
            follow_up_id="check_successful_auth",
            label="Check successful authentications",
            group="continue",
        ),
        EcFollowUpChip(
            follow_up_id="check_privileged_accounts",
            label="Check privileged accounts",
            group="continue",
        ),
        EcFollowUpChip(
            follow_up_id="check_endpoint_activity",
            label="Check endpoint activity",
            group="continue",
        ),
        EcFollowUpChip(
            follow_up_id="check_threat_intel",
            label="Check threat intelligence",
            group="continue",
        ),
        EcFollowUpChip(
            follow_up_id="compare_previous_incidents",
            label="Compare with previous incidents",
            group="continue",
        ),
        EcFollowUpChip(
            follow_up_id="raise_mcp_monitoring",
            label="Raise targeted monitoring",
            group="action",
            leads_to_action=True,
        ),
        EcFollowUpChip(
            follow_up_id="prepare_monitoring_detection",
            label="Prepare monitoring detection candidate",
            group="action",
        ),
        EcFollowUpChip(
            follow_up_id="monitor_affected_hosts",
            label="Monitor affected internal systems",
            group="continue",
        ),
        EcFollowUpChip(
            follow_up_id="monitor_residual",
            label="Monitor for residual activity",
            group="continue",
        ),
        EcFollowUpChip(
            follow_up_id="prepare_firewall_block",
            label="Prepare firewall block request",
            group="action",
            leads_to_action=True,
        ),
        EcFollowUpChip(
            follow_up_id="create_incident_ticket",
            label="Create incident ticket",
            group="action",
            leads_to_action=True,
        ),
        EcFollowUpChip(
            follow_up_id="email_firewall_team",
            label="Email firewall/security team",
            group="action",
            leads_to_action=True,
        ),
        EcFollowUpChip(
            follow_up_id="verify_firewall_block",
            label="Verify firewall rule",
            group="action",
            leads_to_action=True,
        ),
        EcFollowUpChip(
            follow_up_id="update_incident",
            label="Update incident ticket",
            group="action",
            leads_to_action=True,
        ),
        EcFollowUpChip(
            follow_up_id="generate_closure_summary",
            label="Generate closure / executive summary",
            group="action",
        ),
        EcFollowUpChip(
            follow_up_id="generate_executive_summary",
            label="Generate executive summary",
            group="action",
        ),
    )


S1_FOLLOWUPS = _followup_catalog()
S1_FOLLOWUP_IDS = frozenset(chip.follow_up_id for chip in S1_FOLLOWUPS)


def _base_evidence_state() -> list[dict[str, Any]]:
    return [
        {
            "id": "siem_existing_search",
            "label": "Existing Splunk suspicious-IP notable",
            "status": "OBTAINED",
            "provenance": "simulated_mcp",
            "detail": (
                f"{S1_DETECTION_NAME} evaluated — did not fire "
                "(IP is not present in the IOC lookup/content used by the existing notable)"
            ),
        },
        {
            "id": "splunk_fw_search_1",
            "label": "Splunk firewall search 1",
            "status": "OBTAINED",
            "provenance": "simulated_mcp",
            "detail": "Prior 30-day novelty window (-60d to -30d): no prior hits",
        },
        {
            "id": "splunk_fw_search_2",
            "label": "Splunk firewall search 2",
            "status": "OBTAINED",
            "provenance": "simulated_mcp",
            "detail": "Requested last 30 days (-30d to now)",
        },
        {
            "id": "auth_correlation",
            "label": "Firewall identity association",
            "status": "OBTAINED",
            "provenance": "experience_center_fixture",
            "detail": f"Firewall allow events on {_JUMP} associated with {_ACCOUNT} (not successful authentication)",
        },
        {
            "id": "mcp_monitoring",
            "label": "MCP IP monitoring notable",
            "status": "MISSING",
            "provenance": "experience_center_fixture",
            "detail": "14-day Splunk monitoring is not yet deployed",
        },
        {
            "id": "successful_auth",
            "label": "Successful authentications",
            "status": "MISSING",
            "provenance": "experience_center_fixture",
            "detail": "Dedicated identity/auth search not yet run",
        },
        {
            "id": "privileged_identity",
            "label": "Privileged identity detail",
            "status": "MISSING",
            "provenance": "experience_center_fixture",
            "detail": "IAM/privileged-account review not yet run",
        },
        {
            "id": "dns_telemetry",
            "label": "DNS communication",
            "status": "AVAILABLE_NOT_QUERIED",
            "provenance": "experience_center_fixture",
            "detail": "pgcil:dns available in environment KB; not queried",
        },
        {
            "id": "proxy_telemetry",
            "label": "Proxy / web communication",
            "status": "AVAILABLE_NOT_QUERIED",
            "provenance": "experience_center_fixture",
            "detail": "Proxy telemetry available; not queried in initial pass",
        },
        {
            "id": "vpn_telemetry",
            "label": "VPN communication",
            "status": "AVAILABLE_NOT_QUERIED",
            "provenance": "experience_center_fixture",
            "detail": "pgcil:vpn available; not queried",
        },
        {
            "id": "edr",
            "label": "Endpoint activity (EDR)",
            "status": "MISSING",
            "provenance": "experience_center_fixture",
            "detail": "No EDR evidence in the initial package",
        },
        {
            "id": "iam_detail",
            "label": "IAM detail",
            "status": "MISSING",
            "provenance": "experience_center_fixture",
            "detail": "Deeper IAM evidence not in the initial package",
        },
        {
            "id": "threat_intel",
            "label": "Threat intelligence",
            "status": "AVAILABLE_NOT_QUERIED",
            "provenance": "experience_center_fixture",
            "detail": "Simulated TI resource is available but not queried yet",
        },
        {
            "id": "previous_incidents",
            "label": "Previous incidents",
            "status": "AVAILABLE_NOT_QUERIED",
            "provenance": "experience_center_fixture",
            "detail": "Historical ticket comparison not yet run",
        },
        {
            "id": "mcp_identity",
            "label": "Inventory identity",
            "status": "AVAILABLE_NOT_QUERIED",
            "provenance": "experience_center_fixture",
            "detail": "SOC-KB / inventory identity not yet retrieved",
        },
        {
            "id": "sop_rag",
            "label": "Newly observed external / MCP endpoint SOP",
            "status": "AVAILABLE_NOT_QUERIED",
            "provenance": "experience_center_fixture",
            "detail": "Enterprise SOC SOP not yet retrieved",
        },
        {
            "id": "permitted_sessions",
            "label": "Permitted communication / authentication",
            "status": "MISSING",
            "provenance": "experience_center_fixture",
            "detail": "Allowed-session drill not yet run",
        },
        {
            "id": "team_email",
            "label": "Firewall/security team email",
            "status": "MISSING",
            "provenance": "experience_center_fixture",
            "detail": "SOC notification not yet sent",
        },
        {
            "id": "firewall_verify",
            "label": "Firewall rule verification",
            "status": "MISSING",
            "provenance": "experience_center_fixture",
            "detail": "Firewall rule verification is only required after an approved block",
        },
        {
            "id": "incident_update",
            "label": "Incident ticket update",
            "status": "MISSING",
            "provenance": "experience_center_fixture",
            "detail": "Ticket not updated after investigation actions",
        },
        {
            "id": "closure",
            "label": "Closure / executive summary",
            "status": "MISSING",
            "provenance": "experience_center_fixture",
            "detail": "Closure summary not generated",
        },
    ]


def _base_outcome() -> dict[str, Any]:
    return {
        "disposition": "needs_monitoring",
        "confirmed": [
            f"Newly observed IP {PRIMARY_ATTACKER_IP} communicated with {_JUMP}, {_HOST_B}, and {_HOST_C} in the requested last 30 days",
            "Prior 30-day novelty window has no hits — this IP is newly observed",
            "Denied traffic exists on all three affected systems in the requested window",
            f"Jump host {_JUMP} has 3 allowed / 922 denied in the requested window",
            f"Firewall telemetry associates {_ACCOUNT} with allowed events on {_JUMP}",
        ],
        "supported": [
            "Firewall deny volume in the last 30 days is consistent with probing; malicious use is not confirmed",
        ],
        "unconfirmed": [
            "Successful account compromise",
            "Successful authentication attributable to this IP",
            "Whether the three permitted sessions are expected MCP business traffic",
            "Malicious use of the newly observed IP",
            "Valid-account abuse (T1078)",
            "Password guessing (T1110.001) — requires authentication failure evidence",
            "All communication paths (DNS/proxy/VPN/endpoint network not yet assessed)",
        ],
        "missing_evidence": [
            "EDR / endpoint process telemetry",
            "Deeper IAM / identity evidence",
            "DNS / proxy / VPN communication",
            "Threat intelligence (available, not yet queried)",
        ],
        "mitre": [
            {
                "technique_id": "T1110.001",
                "name": "Password Guessing",
                "status": "candidate",
                "evidence_basis": "Firewall deny volume suggests probing; authentication failure events not yet retrieved",
            },
            {
                "technique_id": "T1078",
                "name": "Valid Accounts",
                "status": "unconfirmed",
                "evidence_basis": f"Firewall allow events mention {_ACCOUNT}; dedicated identity proof is not yet retrieved",
            },
        ],
        "provenance": "experience_center_fixture",
        "production_investigation_outcome_unused": True,
    }


def _set_status(items: list[dict[str, Any]], item_id: str, status: str, detail: str) -> None:
    for item in items:
        if item["id"] == item_id:
            item["status"] = status
            item["detail"] = detail
            return
    items.append({"id": item_id, "label": item_id, "status": status, "detail": detail, "provenance": "experience_center_fixture"})


def _apply_follow_up_effects(
    applied: list[str],
    *,
    session_id: str,
    outcome: dict[str, Any],
    evidence_state: list[dict[str, Any]],
    extra_evidence: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[Any], dict[str, Any]]:
    extras: dict[str, Any] = {}
    actions: list[Any] = list(ec_actions.list_actions_for_session(session_id, S1_SCENARIO_ID))

    if "check_successful_auth" in applied:
        _set_status(
            evidence_state,
            "successful_auth",
            "OBTAINED",
            f"Simulated auth search: 3 successful logons for {_ACCOUNT} on {_JUMP} in the recent window; source IP of those logons is not proven as {PRIMARY_ATTACKER_IP}",
        )
        extra_evidence.append(
            _source_evidence_item(
                "ev-s1-auth-success",
                "Simulated authentication correlation",
                [
                    {
                        "host": _JUMP,
                        "user": _ACCOUNT,
                        "action": "success",
                        "success_count": 3,
                        "src": "not_proven",
                        "first_seen": "2026-08-16T15:10:00Z",
                        "last_seen": "2026-08-16T16:44:00Z",
                    }
                ],
                (
                    "search index=pgcil_soc sourcetype=pgcil:auth earliest=-30d latest=now "
                    f"host={_JUMP} user={_ACCOUNT} action=success "
                    "| stats count as success_count min(_time) as first_seen max(_time) as last_seen by host, user, action "
                    "| head 100"
                ),
                "earliest=-30d latest=now",
            )
        )
        if "Successful logons for svc_jump_ops on the jump host exist in the recent window" not in outcome["confirmed"]:
            outcome["confirmed"].append(
                f"Successful logons for {_ACCOUNT} on {_JUMP} exist in the recent window"
            )
        if "Auth log source IP is the newly observed IP" not in outcome["unconfirmed"]:
            outcome["unconfirmed"].append("Auth log source IP is the newly observed IP")

    if "check_privileged_accounts" in applied:
        _set_status(
            evidence_state,
            "privileged_identity",
            "OBTAINED",
            f"{_ACCOUNT} is a privileged jump-host service account; compromise is still unconfirmed",
        )
        _set_status(
            evidence_state,
            "iam_detail",
            "OBTAINED",
            f"Directory fixture labels {_ACCOUNT} as a privileged service account for jump-host access",
        )
        extra_evidence.append(
            {
                "evidence_id": "ev-s1-privileged",
                "source_type": "identity_fixture",
                "source_name": "Privileged account directory fixture",
                "collection_status": "collected",
                "preview_rows": [
                    {
                        "account": _ACCOUNT,
                        "account_class": "privileged_service",
                        "scope": "jump_host_access",
                        "compromise_confirmed": False,
                    }
                ],
                "result_count": 1,
                "provenance": "experience_center_fixture",
                "warnings": ["coe_synthetic_fixture"],
            }
        )
        if f"{_ACCOUNT} is a privileged jump-host service account" not in outcome["confirmed"]:
            outcome["confirmed"].append(f"{_ACCOUNT} is a privileged jump-host service account")
        if "Privileged-account compromise" not in outcome["unconfirmed"]:
            outcome["unconfirmed"].append("Privileged-account compromise")

    if "check_endpoint_activity" in applied:
        _set_status(
            evidence_state,
            "edr",
            "OBTAINED",
            f"Simulated EDR review on {_JUMP}: no malicious process activity confirmed in either window",
        )
        extra_evidence.append(
            {
                "evidence_id": "ev-s1-edr",
                "source_type": "edr_fixture",
                "source_name": "Simulated endpoint activity",
                "collection_status": "collected",
                "preview_rows": [
                    {
                        "host": _JUMP,
                        "malicious_process_confirmed": False,
                        "detections": 0,
                        "note": "No malicious endpoint activity confirmed",
                    }
                ],
                "result_count": 1,
                "provenance": "simulated_mcp",
                "warnings": ["coe_synthetic_fixture"],
            }
        )
        outcome["missing_evidence"] = [item for item in outcome["missing_evidence"] if "EDR" not in item]
        if "Malicious endpoint activity on the jump host" not in outcome["unconfirmed"]:
            outcome["unconfirmed"].append("Malicious endpoint activity on the jump host")
        if "No malicious endpoint activity confirmed on the jump host" not in outcome["confirmed"]:
            outcome["confirmed"].append("No malicious endpoint activity confirmed on the jump host")

    if "check_threat_intel" in applied:
        _set_status(
            evidence_state,
            "threat_intel",
            "OBTAINED",
            f"{PRIMARY_ATTACKER_IP} is not present in local IOC / threat-intelligence evidence (unlisted, not benign)",
        )
        extra_evidence.append(
            {
                "evidence_id": "ev-s1-ti",
                "source_type": "threat_intel_fixture",
                "source_name": "Simulated threat intelligence",
                "collection_status": "collected",
                "preview_rows": [
                    {
                        "indicator": PRIMARY_ATTACKER_IP,
                        "category": "unlisted",
                        "feed": "ec_ti_fixture",
                        "live_feed": False,
                        "internet_reputation": False,
                        "note": "Not present in local IOC / threat-intelligence evidence. Unlisted is not benign.",
                    }
                ],
                "result_count": 1,
                "provenance": "experience_center_fixture",
                "warnings": ["coe_synthetic_fixture"],
            }
        )
        outcome["missing_evidence"] = [item for item in outcome["missing_evidence"] if "Threat intelligence" not in item]
        if f"{PRIMARY_ATTACKER_IP} is not present in local IOC / threat-intelligence evidence" not in outcome["confirmed"]:
            outcome["confirmed"].append(
                f"{PRIMARY_ATTACKER_IP} is not present in local IOC / threat-intelligence evidence"
            )

    if "compare_previous_incidents" in applied:
        _set_status(
            evidence_state,
            "previous_incidents",
            "OBTAINED",
            f"Overlap with {INCIDENT_ID}: same indicator and jump host; not proof of the same campaign",
        )
        extra_evidence.append(
            {
                "evidence_id": "ev-s1-prior-ticket",
                "source_type": "ticket_fixture",
                "source_name": "Historical incident comparison",
                "collection_status": "collected",
                "preview_rows": [
                    {
                        "ticket_id": INCIDENT_ID,
                        "overlap": ["indicator", "jump_host"],
                        "same_campaign": False,
                        "note": "Similar perimeter activity; independent confirmation still required",
                    }
                ],
                "result_count": 1,
                "provenance": "experience_center_fixture",
                "warnings": ["coe_synthetic_fixture"],
            }
        )
        if f"Historical ticket {INCIDENT_ID} shares this indicator and jump host" not in outcome["supported"]:
            outcome["supported"].append(
                f"Historical ticket {INCIDENT_ID} shares this indicator and jump host; campaign linkage is unconfirmed"
            )

    if "lookup_inventory_identity" in applied or "review_existing_notable" in applied:
        identity_line = (
            f"Identity: registered MCP endpoint ({PRIMARY_ATTACKER_IP}) — inventory/SOC-KB evidence"
        )
        if identity_line not in outcome["confirmed"]:
            outcome["confirmed"].append(identity_line)
        _set_status(
            evidence_state,
            "mcp_identity",
            "OBTAINED",
            f"Identity: registered MCP endpoint ({PRIMARY_ATTACKER_IP})",
        )

    if "retrieve_sop" in applied:
        _set_status(
            evidence_state,
            "sop_rag",
            "OBTAINED",
            "Enterprise SOP retrieved: targeted monitoring default; block requires threshold + Network/SOC HIL",
        )
        extra_evidence.append(sop_source_evidence())
        if "SOP retrieved: targeted monitoring is the default" not in outcome["supported"]:
            outcome["supported"].append(
                "SOP retrieved: targeted monitoring is the default; blocking remains conditional"
            )

    if "investigate_permitted_sessions" in applied:
        _set_status(
            evidence_state,
            "permitted_sessions",
            "OBTAINED",
            f"Three allowed sessions on {_JUMP} (443/8443); authentication not attributable to {PRIMARY_ATTACKER_IP}",
        )
        extra_evidence.append(
            _source_evidence_item(
                "ev-s1-permitted-sessions",
                "Permitted firewall sessions (allow drill)",
                [
                    {
                        "src": PRIMARY_ATTACKER_IP,
                        "dest": _JUMP,
                        "dest_role": "jump_host",
                        "criticality": "high",
                        "dest_port": 443,
                        "service": "HTTPS",
                        "action": "allow",
                        "allow_count": 2,
                        "first_seen": "2026-07-18T02:08:00Z",
                        "last_seen": "2026-08-16T16:40:00Z",
                    },
                    {
                        "src": PRIMARY_ATTACKER_IP,
                        "dest": _JUMP,
                        "dest_role": "jump_host",
                        "criticality": "high",
                        "dest_port": 8443,
                        "service": "TLS-alt",
                        "action": "allow",
                        "allow_count": 1,
                        "first_seen": "2026-08-16T16:44:00Z",
                        "last_seen": "2026-08-16T16:44:00Z",
                    },
                ],
                permitted_session_spl(),
                "earliest=-30d latest=now",
            )
        )
        if f"Three permitted sessions on jump host {_JUMP}" not in outcome["confirmed"]:
            outcome["confirmed"].append(
                f"Three permitted sessions on jump host {_JUMP} (443/8443); auth source IP not proven"
            )

    if "prepare_monitoring_detection" in applied:
        _set_status(
            evidence_state,
            "monitoring_candidate",
            "OBTAINED",
            "Candidate monitoring SPL validated and authorized for splunk_run_query",
        )
        extra_evidence.append(
            _source_evidence_item(
                "ev-s1-monitoring-candidate",
                "14-day Splunk monitoring SPL",
                [
                    {
                        "name": "EC_New_External_IP_Permitted_Session_Watch",
                        "status": "validated",
                        "window": "14d",
                        "llm_output_is_evidence": False,
                    }
                ],
                candidate_monitoring_spl(),
                "earliest=-14d latest=now",
            )
        )

    if "monitor_affected_hosts" in applied:
        _set_status(
            evidence_state,
            "host_watch",
            "OBTAINED",
            f"14-day watch on {_JUMP}, {_HOST_B}, {_HOST_C}",
        )

    if "monitor_residual" in applied:
        _set_status(
            evidence_state,
            "residual_watch",
            "OBTAINED",
            f"Residual-activity watch armed for {PRIMARY_ATTACKER_IP}",
        )

    existing_kinds = {item.kind for item in actions}
    if "raise_mcp_monitoring" in applied:
        if "notify" not in existing_kinds:
            prepared = ec_actions.prepare_action(
                kind="notify",
                label=f"Deploy Splunk monitoring for newly observed MCP IP {PRIMARY_ATTACKER_IP}",
                session_id=session_id,
                scenario_id=S1_SCENARIO_ID,
                extra={
                    "indicator": PRIMARY_ATTACKER_IP,
                    "requested_action": "raise_monitoring",
                    "auto_block": False,
                    "monitoring": {
                        "kind": "new_notable",
                        "name": "EC_New_External_IP_Permitted_Session_Watch",
                        "indicator": PRIMARY_ATTACKER_IP,
                        "reason": (
                            f"{PRIMARY_ATTACKER_IP} is a newly registered MCP endpoint outside the existing "
                            "IOC-based notable. SOP is to deploy 14-day monitoring first; block stays conditional."
                        ),
                    },
                },
            )
            actions.append(prepared)
        notify = next((item for item in actions if item.kind == "notify"), None)
        deployed = notify is not None and notify.state in {"EXECUTED", "VERIFIED"}
        _set_status(
            evidence_state,
            "mcp_monitoring",
            "OBTAINED",
            (
                "Baseline monitoring query executed via splunk_run_query; schedule saved search manually"
                if deployed
                else "Baseline monitoring query authorized via splunk_run_query"
            ),
        )
        if deployed and "Baseline monitoring query executed via splunk_run_query" not in outcome["supported"]:
            outcome["supported"].append("Baseline monitoring query executed via splunk_run_query")
    if "prepare_firewall_block" in applied and "firewall_block" not in existing_kinds:
        prepared = ec_actions.prepare_action(
            kind="firewall_block",
            label=f"Prepare firewall block for {PRIMARY_ATTACKER_IP}",
            session_id=session_id,
            scenario_id=S1_SCENARIO_ID,
            extra={
                "indicator": PRIMARY_ATTACKER_IP,
                "requested_action": "block",
                "auto_block": False,
                "soar": {
                    "playbook": "ip_block",
                    "indicator": PRIMARY_ATTACKER_IP,
                    "action": "block",
                    "reason": (
                        f"SOC Experience Center request to block {PRIMARY_ATTACKER_IP} after a last-30-days "
                        f"review of {_JUMP}, {_HOST_B}, and {_HOST_C}. This IP is a newly observed MCP "
                        "endpoint; malicious use is unconfirmed. Containment is HIL-gated and must go "
                        "through SOAR / firewall MCP if configured."
                    ),
                },
                "verify_payload": {
                    "rule_present": True,
                    "indicator": PRIMARY_ATTACKER_IP,
                    "simulated": True,
                },
            },
        )
        actions.append(prepared)
    if "create_incident_ticket" in applied and "ticket_create" not in existing_kinds:
        ticket_body = {
            "id": "INC-2026-89412",
            "ticket_id": "INC-2026-89412",
            "indicator": PRIMARY_ATTACKER_IP,
            "affected_systems": [_JUMP, _HOST_B, _HOST_C],
            "severity": "P2 High",
            "disposition": outcome["disposition"],
            "confirmed": list(outcome["confirmed"]),
            "unconfirmed": list(outcome["unconfirmed"]),
            "timeline": "Requested last 30 days plus prior 30-day novelty window",
            "recommended_next_step": "Review firewall block request and identity evidence before containment",
            "production_side_effect": False,
        }
        prepared = ec_actions.prepare_action(
            kind="ticket_create",
            label="Create incident ticket",
            session_id=session_id,
            scenario_id=S1_SCENARIO_ID,
            extra={"ticket": ticket_body},
        )
        actions.append(prepared)

    if "email_firewall_team" in applied:
        ticket_executed = any(
            item.kind == "ticket_create" and item.state == "EXECUTED" for item in actions
        )
        email_extra = ec_email_drafts.s1_firewall_team_email(
            applied=applied,
            jump=_JUMP,
            host_b=_HOST_B,
            host_c=_HOST_C,
            account=_ACCOUNT,
            ticket_executed=ticket_executed,
        )
        email = next((item for item in actions if item.kind == "email_send"), None)
        if email is None:
            email = ec_actions.prepare_action(
                kind="email_send",
                label="Email firewall/security team",
                session_id=session_id,
                scenario_id=S1_SCENARIO_ID,
                extra=email_extra,
            )
            actions.append(email)
        _set_status(
            evidence_state,
            "team_email",
            "OBTAINED",
            (
                "SOC notification delivered to FIREWALL_TEAM"
                if email is not None and email.state in {"EXECUTED", "VERIFIED"}
                else "SOC notification queued for FIREWALL_TEAM"
            ),
        )
        extras["ec_email"] = {
            "to": email_extra["email"]["to"],
            "logical_recipient": "FIREWALL_TEAM",
            "subject": email_extra["email"]["subject"],
            "status": "sent" if email is not None and email.state in {"EXECUTED", "VERIFIED"} else "draft_pending_send",
            "not_transmitted": not (email is not None and email.state in {"EXECUTED", "VERIFIED"}),
            "sent_at": "2026-08-16T17:02:11Z" if email is not None and email.state in {"EXECUTED", "VERIFIED"} else None,
        }

    if "verify_firewall_block" in applied:
        block = next((item for item in actions if item.kind == "firewall_block"), None)
        if block is not None and block.state == "EXECUTED":
            verified = ec_actions.verify_action(block.action_id)
            actions = [item for item in actions if item.action_id != verified.action_id]
            actions.append(verified)
            _set_status(
                evidence_state,
                "firewall_verify",
                "OBTAINED",
                f"Simulated firewall rule for {PRIMARY_ATTACKER_IP} verified after execute",
            )
            if "Simulated firewall rule verified after execute" not in outcome["confirmed"]:
                outcome["confirmed"].append("Simulated firewall rule verified after execute")
        else:
            _set_status(
                evidence_state,
                "firewall_verify",
                "MISSING",
                "Verification is unavailable until the firewall action is executed after HIL approval",
            )

    if "update_incident" in applied:
        updated = next((item for item in actions if item.kind == "ticket_update"), None)
        if updated is None:
            ticket_body = {
                "indicator": PRIMARY_ATTACKER_IP,
                "disposition": outcome["disposition"],
                "update": "Investigation actions recorded; compromise remains unconfirmed",
                "production_side_effect": False,
            }
            prepared = ec_actions.prepare_action(
                kind="ticket_update",
                label="Update incident ticket",
                session_id=session_id,
                scenario_id=S1_SCENARIO_ID,
                extra={"ticket": ticket_body},
            )
            actions.append(prepared)
            updated = prepared
        applied_update = updated is not None and updated.state in {"EXECUTED", "VERIFIED"}
        _set_status(
            evidence_state,
            "incident_update",
            "OBTAINED",
            (
                "Incident updated · monitoring active · block threshold not met"
                if applied_update
                else "Incident update queued"
            ),
        )

    if "generate_closure_summary" in applied:
        outcome["closure_summary"] = (
            f"Newly observed IP {PRIMARY_ATTACKER_IP} investigated over the requested last 30 days "
            "(prior window empty). Identified as a new MCP endpoint. Monitoring is the SOP first step; "
            "firewall block is HIL-gated and is not auto-applied from initial evidence. "
            "Malicious use and attributable authentication remain unconfirmed."
        )
        _set_status(evidence_state, "closure", "OBTAINED", "Executive closure summary generated")

    return outcome, evidence_state, extra_evidence, actions, extras


def _assessment(applied: list[str]) -> str:
    extra = ""
    if "check_endpoint_activity" in applied:
        extra = " Endpoint review did not confirm malicious process activity."
    if "check_threat_intel" in applied:
        extra += (
            f" Indicator {PRIMARY_ATTACKER_IP} is not present in local IOC / threat-intelligence evidence."
        )
    identity = (
        "It is identified as a registered MCP endpoint — existing IOC-based detections would not have fired. "
        if "lookup_inventory_identity" in applied or "review_existing_notable" in applied
        else "Inventory identity is pending SOC-KB evidence. "
    )
    return (
        f"A newly observed IP {PRIMARY_ATTACKER_IP} was reviewed over the requested last 30 days. "
        f"Firewall telemetry shows communication with {_JUMP}, {_HOST_B}, and {_HOST_C}. "
        "The prior 30-day window is empty, so this IP is new to the environment. "
        + identity
        + "Standard SOP is to raise monitoring first and prepare a HIL block only if a blocking threshold is met. "
        "Malicious use is not confirmed. This is firewall-observed communication only — DNS, proxy, VPN, and endpoint "
        "network paths were not queried. Account compromise is not confirmed."
        + extra
    )


def _what_we_found_segments(applied: list[str]) -> list[dict[str, str]]:
    segments: list[dict[str, str]] = [
        {"type": "text", "text": "Splunk MCP connected. "},
        {
            "type": "evidence_link",
            "text": S1_DETECTION_NAME,
            "evidence_id": "ev-s1-existing-search",
            "title": f"Splunk MCP saved search · {S1_SAVED_SEARCH_NAME}",
        },
        {"type": "text", "text": " was evaluated and did not fire — the IP is not present in the IOC lookup/content used by the existing notable; "},
        {
            "type": "evidence_link",
            "text": "30-day novelty window (prior)",
            "evidence_id": "ev-s1-fw-search-1",
            "title": "Splunk MCP ad-hoc SPL · earliest=-60d latest=-30d",
        },
        {"type": "text", "text": " is empty, and "},
        {
            "type": "evidence_link",
            "text": "requested last 30 days",
            "evidence_id": "ev-s1-fw-search-2",
            "title": "Splunk MCP ad-hoc SPL · earliest=-30d latest=now",
        },
        {
            "type": "text",
            "text": (
                f" shows firewall communication with {_JUMP}, {_HOST_B}, and {_HOST_C}. "
                + (
                    "The IP is a registered MCP endpoint. "
                    if "lookup_inventory_identity" in applied or "review_existing_notable" in applied
                    else "Inventory identity is pending. "
                )
                + f"Jump host {_JUMP} has 3 allowed connections "
                f"with a firewall identity association to {_ACCOUNT} — not established as successful authentication."
            ),
        },
    ]
    if "check_successful_auth" in applied:
        segments.append(
            {
                "type": "text",
                "text": (
                    f" A follow-up auth search shows successful logons for {_ACCOUNT} on {_JUMP}; "
                    "the auth source IP is not proven."
                ),
            }
        )
    if "check_privileged_accounts" in applied:
        segments.append({"type": "text", "text": f" {_ACCOUNT} is a privileged jump-host service account."})
    return segments


def _what_we_found(applied: list[str]) -> str:
    identity = (
        f"The IP is identified as a registered MCP endpoint. "
        if "lookup_inventory_identity" in applied or "review_existing_notable" in applied
        else ""
    )
    text = (
        f"Splunk MCP connected. {S1_DETECTION_NAME} was evaluated and did not fire because "
        f"{PRIMARY_ATTACKER_IP} is not present in the IOC lookup/content used by the existing notable. "
        f"The prior 30-day novelty window is empty; "
        f"the requested last 30 days show firewall communication with {_JUMP}, {_HOST_B}, and {_HOST_C}. "
        f"{identity}Jump host {_JUMP} has "
        f"3 allowed connections with a firewall identity association to {_ACCOUNT} — not established as successful authentication."
    )
    if "check_successful_auth" in applied:
        text += f" A follow-up auth search shows successful logons for {_ACCOUNT} on {_JUMP}; the auth source IP is not proven."
    if "check_privileged_accounts" in applied:
        text += f" {_ACCOUNT} is a privileged jump-host service account."
    return text


def _recommended_investigations(applied: list[str]) -> list[str]:
    steps = [
        "Check successful authentications for the jump-host service account",
        "Review privileged-account context without assuming compromise",
        "Check endpoint activity on the jump host",
        "Check threat intelligence for the newly observed IP",
        "Compare with previous incidents",
        "Raise monitoring for this MCP IP (SOP first step)",
        "Assess DNS / proxy / VPN communication if broader coverage is required",
    ]
    mapping = {
        "check_successful_auth": 0,
        "check_privileged_accounts": 1,
        "check_endpoint_activity": 2,
        "check_threat_intel": 3,
        "compare_previous_incidents": 4,
        "raise_mcp_monitoring": 5,
    }
    return [step for idx, step in enumerate(steps) if not any(mapping.get(fid) == idx for fid in applied)]


def _recommended(applied: list[str]) -> list[str]:
    steps = [
        "Review successful authentications and identity context for the jump-host service account",
        "Check privileged-account impact without assuming compromise",
        "Query endpoint activity on the jump host",
        "Check threat intelligence for the newly observed IP",
        "Compare with previous incidents before containment",
        "Raise monitoring for this newly observed MCP IP (SOP first step; HIL notable, not auto-deployed)",
        "Prepare a firewall block request only if required and after analyst approval",
        "Open an incident ticket with confirmed vs unconfirmed findings",
        "Email the firewall/security team after reviewing the draft",
        "Verify a simulated firewall rule only after execute",
        "Update the incident and generate a closure summary",
    ]
    mapping = {
        "check_successful_auth": 0,
        "check_privileged_accounts": 1,
        "check_endpoint_activity": 2,
        "check_threat_intel": 3,
        "compare_previous_incidents": 4,
        "raise_mcp_monitoring": 5,
        "prepare_firewall_block": 6,
        "create_incident_ticket": 7,
        "email_firewall_team": 8,
        "verify_firewall_block": 9,
        "update_incident": 10,
        "generate_closure_summary": 11,
    }
    remaining = [step for idx, step in enumerate(steps) if not any(mapping.get(fid) == idx for fid in applied)]
    return remaining or ["Document the investigation outcome and keep compromise unconfirmed until identity evidence lands."]


def _unconfirmed_copy(outcome: dict[str, Any]) -> list[str]:
    return list(outcome["unconfirmed"])


def _spl_governance(search_1: dict[str, Any], search_2: dict[str, Any]) -> dict[str, Any]:
    policy = search_governance_policy()
    return {
        "user_request": S1_QUERY,
        "time_range_supplied": True,
        "environment_governance": policy["visitor_summary"],
        "policy": policy,
        "why": policy["why"],
        "searches": [
            {
                "search_id": "search_1",
                "label": "Search 1 · prior 30-day novelty window",
                "earliest": "-60d",
                "latest": "-30d",
                "candidate_spl": _SEARCH_1_SPL,
                "normalized_spl": search_1.get("normalized_spl"),
                "approved": bool(search_1.get("approved")),
                "reject_reasons": list(search_1.get("reject_reasons") or []),
                "provenance": "production_validator_read_only",
            },
            {
                "search_id": "search_2",
                "label": "Search 2 · requested last 30 days",
                "earliest": "-30d",
                "latest": "now",
                "candidate_spl": _SEARCH_2_SPL,
                "normalized_spl": search_2.get("normalized_spl"),
                "approved": bool(search_2.get("approved")),
                "reject_reasons": list(search_2.get("reject_reasons") or []),
                "provenance": "production_validator_read_only",
            },
        ],
        "controls": [
            "approved index pgcil_soc",
            "approved sourcetype pgcil:firewall",
            "approved field mapping src, dest, action, dest_port",
            "bounded time range 30+30",
            "result limit head 100",
            "blocked command policy",
            "read-only",
            "deterministic validator",
        ],
        "validation": {
            "engine": "validate_spl",
            "provenance": "production_validator_read_only",
            "search_1_approved": bool(search_1.get("approved")),
            "search_2_approved": bool(search_2.get("approved")),
            "override": False,
        },
        "evidence_merge": "Both Splunk search receipts were merged into one investigation by dest host",
        "production_mcp_executed": False,
        "spl_not_required": False,
    }


def _projection(
    *,
    outcome: dict[str, Any],
    evidence_state: list[dict[str, Any]],
    search_1: dict[str, Any],
    search_2: dict[str, Any],
) -> EcProjection:
    fixture = EcProvenanceStamp(kind="experience_center_fixture", detail=S1_SCENARIO_ID)
    policy = EcProvenanceStamp(kind="ec_scenario_policy", detail="ec_search_governance_policy")
    validator = EcProvenanceStamp(kind="production_validator_read_only", detail="validate_spl")
    simulated = EcProvenanceStamp(kind="simulated_mcp", detail="two_bounded_firewall_searches")
    return EcProjection(
        understanding=EcProjectionView(
            title="Understanding",
            summary="Visitor asked to verify a newly observed IP over the last 30 days and the SOP to raise monitoring or block if required.",
            items=[
                f"indicator={PRIMARY_ATTACKER_IP}",
                "time_range_supplied=true",
                "route_source=ec_fixture_selected",
            ],
            provenance=EcProvenanceStamp(kind="ec_fixture_selected", detail="attack_discovery"),
        ),
        resource_plan=EcProjectionView(
            title="Resources selected",
            summary="Env KB firewall index/sourcetype plus simulated Splunk search receipts. No ResourcePlan graph execution.",
            items=["index=pgcil_soc", "sourcetype=pgcil:firewall", "simulated_mcp search_1", "simulated_mcp search_2"],
            provenance=fixture,
        ),
        phase_contract=EcProjectionView(
            title="Environment search governance",
            summary="Environment search governance applied: requested last 30 days plus a prior 30-day novelty window.",
            items=[
                "ec_search_governance_policy",
                "split=30+30",
                "no index=*",
                "not production SPL policy",
                "not production PhasePolicy",
                f"search_1_approved={bool(search_1.get('approved'))}",
                f"search_2_approved={bool(search_2.get('approved'))}",
                f"validator={validator.kind}",
            ],
            provenance=policy,
        ),
        evidence_state=EcProjectionView(
            title="Evidence merged",
            summary="Two simulated Splunk receipts merged by destination host.",
            items=[f"{item['label']} → {item['status']}" for item in evidence_state],
            provenance=simulated,
        ),
        investigation_outcome=EcProjectionView(
            title="InvestigationOutcome",
            summary=f"Disposition {outcome['disposition']}. Malicious use remains unconfirmed.",
            items=[
                "production InvestigationOutcome field unused",
                *[f"confirmed: {item}" for item in outcome["confirmed"]],
                *[f"unconfirmed: {item}" for item in outcome["unconfirmed"]],
                *[f"missing: {item}" for item in outcome["missing_evidence"]],
            ],
            provenance=fixture,
        ),
        provenance=fixture,
    )


def _candidate_spl_envelope(trace_id: str, search_1: dict[str, Any]) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "skill": "attack_discovery",
        "user_query": S1_QUERY,
        "candidate_spl": _SEARCH_1_SPL,
        "generation_mode": "ec_search_governance_policy",
        "confidence": 0.9,
        "assumptions": [
            "Visitor asked for the last 30 days; a prior 30-day novelty window checks whether the IP is newly observed.",
            "COE synthetic fixture; analyst must review before any execution.",
        ],
        "warnings": ["demo_fixture_not_live_data"],
        "reason": "EC scenario policy compiled two bounded searches; this envelope holds search 1 for review.",
        "candidate_spl_generated": True,
        "validation_required": True,
        "execution_eligible": False,
        "saia_available": False,
        "fallback_required": False,
    }


def _validation_envelope(search_1: dict[str, Any], search_2: dict[str, Any]) -> dict[str, Any]:
    return {
        "approved": bool(search_1.get("approved") and search_2.get("approved")),
        "normalized_spl": search_1.get("normalized_spl"),
        "reject_reasons": list(search_1.get("reject_reasons") or []) + list(search_2.get("reject_reasons") or []),
        "warnings": ["demo_fixture_not_live_data"],
        "enforced_limits": search_1.get("enforced_limits") or {},
        "policy_version": search_1.get("policy_version"),
        "override": False,
        "provenance": "production_validator_read_only",
        "search_1_approved": bool(search_1.get("approved")),
        "search_2_approved": bool(search_2.get("approved")),
        "execution_eligible": False,
    }


def _layer2_path() -> list[str]:
    return list(S1_LAYER2_PATH)


def _mcp_identity_evidence() -> dict[str, Any]:
    return {
        "evidence_id": "ev-s1-mcp-identity",
        "trace_id": "pending",
        "source_type": "knowledge_fixture",
        "source_name": "Newly observed MCP endpoint identity",
        "tool_name": "retrieve_soc_kb",
        "collection_status": "collected",
        "query_or_request_summary": f"Identity lookup for {PRIMARY_ATTACKER_IP}",
        "result_count": 1,
        "fields_returned": ["indicator", "identity", "covered_by_suspicious_ip_notable"],
        "preview_rows": [
            {
                "indicator": PRIMARY_ATTACKER_IP,
                "identity": "registered MCP endpoint",
                "covered_by_suspicious_ip_notable": False,
                "note": (
                    "Existing IOC-based known-malicious-IP content does not cover this registered MCP endpoint. "
                    "This is a new concern; Splunk would not have treated the IP as a known-bad IOC."
                ),
            }
        ],
        "provenance": "experience_center_fixture",
        "warnings": ["coe_synthetic_fixture"],
        "output_type": "fixture_preview",
    }


def _existing_detection_evidence() -> dict[str, Any]:
    return {
        "evidence_id": "ev-s1-existing-search",
        "trace_id": "pending",
        "source_type": "splunk_saved_search",
        "source_name": S1_DETECTION_NAME,
        "tool_name": "splunk_run_saved_search",
        "collection_status": "collected",
        "query_or_request_summary": f"saved_search={S1_SAVED_SEARCH_NAME} · evaluated, notable did not fire",
        "result_count": 1,
        "fields_returned": ["saved_search", "fired", "reason"],
        "preview_rows": [
            {
                "saved_search": S1_SAVED_SEARCH_NAME,
                "fired": False,
                "reason": (
                    f"{PRIMARY_ATTACKER_IP} is not present in the IOC lookup/content used by this notable"
                ),
            }
        ],
        "provenance": "simulated_mcp",
        "warnings": ["coe_synthetic_fixture", "partial_coverage_only"],
        "output_type": "fixture_preview",
    }


def _s1_executive_summary(applied: list[str]) -> list[str]:
    if not applied:
        return []
    rem_done = "raise_mcp_monitoring" in applied or "create_incident_ticket" in applied
    bullets = [
        f"Newly observed IP {PRIMARY_ATTACKER_IP}: existing IOC notable did not fire "
        "(IP not in that lookup/content).",
        "Last 30 days: 3 permitted jump-host sessions on 10.20.1.10 (443/8443) remain unexplained; prior window empty.",
        (
            "Identity: registered MCP endpoint — a new concern, not a listed IOC. Malicious use is not confirmed."
            if "lookup_inventory_identity" in applied or "review_existing_notable" in applied
            else "Inventory identity is established only after SOC-KB evidence."
        ),
        "Current risk: MEDIUM. Monitoring: pending. Blocking: CONDITIONAL — SOP threshold is not met.",
    ]
    if rem_done:
        bullets[-1] = (
            "Current risk: MEDIUM. Baseline query: EXECUTED. Saved search: schedule manually. "
            "Blocking: CONDITIONAL — SOP threshold is not met."
        )
        bullets.extend(
            [
                "Baseline monitoring query executed via splunk_run_query for 198.51.100.42, "
                "jump-host 443/8443, and svc_jump_ops — schedule EC_New_External_IP_Permitted_Session_Watch in Splunk next.",
                f"Incident INC-2026-89412 created; SOC notified; incident updated. IP block not required at current SOP threshold.",
            ]
        )
    return bullets


def build_s1_turn(
    *,
    session_id: str,
    turn: int,
    applied_follow_up_ids: list[str],
    pending_action_id: str | None = None,
    awaiting_external: bool = False,
    agent_state: dict[str, Any] | None = None,
) -> ExperienceCenterResponse:
    search_1 = _validate_search(_SEARCH_1_SPL)
    search_2 = _validate_search(_SEARCH_2_SPL)
    search_m = _validate_search(candidate_monitoring_spl())
    if not search_1.get("approved") or not search_2.get("approved") or not search_m.get("approved"):
        raise RuntimeError(
            "S1 fixture SPL failed real validate_spl; fix the EC SPL fixture. "
            f"search_1={search_1.get('reject_reasons')} search_2={search_2.get('reject_reasons')} "
            f"monitoring={search_m.get('reject_reasons')}"
        )

    trace_id = f"demo-{S1_SCENARIO_ID}-{uuid4().hex[:8]}"
    user_applied = list(applied_follow_up_ids)
    outcome = deepcopy(_base_outcome())
    evidence_state = deepcopy(_base_evidence_state())
    extra_evidence: list[dict[str, Any]] = []
    outcome, evidence_state, extra_evidence, actions, extras = _apply_follow_up_effects(
        user_applied,
        session_id=session_id,
        outcome=outcome,
        evidence_state=evidence_state,
        extra_evidence=extra_evidence,
    )
    from app.demo.fixtures.s1.agent_handler import (
        build_s1_agent_workflow,
        finalize_s1_remediation_after_apply,
        get_s1_agent_state,
        s1_followups_for_agent_mode,
    )

    resolved_agent_state = dict(agent_state or get_s1_agent_state(session_id, S1_FAMILY))
    if resolved_agent_state.get("remediation_execute_pending"):
        resolved_agent_state = finalize_s1_remediation_after_apply(
            session_id=session_id,
            family=S1_FAMILY,
            scenario_id=S1_SCENARIO_ID,
            agent_state=resolved_agent_state,
            applied=user_applied,
        )
        if "verify_firewall_block" not in user_applied:
            executed_block = next(
                (
                    item
                    for item in ec_actions.list_actions_for_session(session_id, S1_SCENARIO_ID)
                    if item.kind == "firewall_block" and item.state in {"EXECUTED", "VERIFIED"}
                ),
                None,
            )
            if executed_block is not None:
                user_applied = list(user_applied) + ["verify_firewall_block"]
        outcome = deepcopy(_base_outcome())
        evidence_state = deepcopy(_base_evidence_state())
        extra_evidence = []
        outcome, evidence_state, extra_evidence, actions, extras = _apply_follow_up_effects(
            user_applied,
            session_id=session_id,
            outcome=outcome,
            evidence_state=evidence_state,
            extra_evidence=extra_evidence,
        )

    applied = user_applied
    pending = pending_action_id
    if not pending:
        prepared = next((item for item in actions if item.state in {"PREPARED", "APPROVAL_REQUIRED"}), None)
        pending = prepared.action_id if prepared else None

    use_agent_ui = True
    agent_workflow = build_s1_agent_workflow(
        agent_state=resolved_agent_state,
        applied=applied,
        actions=actions,
        outcome=outcome,
        executive_summary=_s1_executive_summary(applied),
    )
    agent_chips = s1_followups_for_agent_mode(
        str(resolved_agent_state.get("lifecycle") or "PLAN_READY"),
        applied=user_applied,
    )

    source_evidence = [
        _existing_detection_evidence(),
        _source_evidence_item(
            "ev-s1-fw-search-1",
            "Splunk firewall search · prior 30-day window",
            _search_1_rows(),
            _SEARCH_1_SPL,
            "earliest=-60d latest=-30d",
        ),
        _source_evidence_item(
            "ev-s1-fw-search-2",
            "Splunk firewall search · last 30 days",
            _search_2_rows(),
            _SEARCH_2_SPL,
            "earliest=-30d latest=now",
        ),
    ]
    if "lookup_inventory_identity" in applied or "review_existing_notable" in applied:
        source_evidence.append(_mcp_identity_evidence())
    source_evidence.extend(extra_evidence)
    for item in source_evidence:
        item["trace_id"] = trace_id

    remaining = list(agent_chips) if use_agent_ui else [chip for chip in S1_FOLLOWUPS if chip.follow_up_id not in applied]
    firewall = next((item for item in actions if item.kind == "firewall_block"), None)
    if not use_agent_ui and (firewall is None or firewall.state not in {"EXECUTED", "VERIFIED"}):
        remaining = [chip for chip in remaining if chip.follow_up_id != "verify_firewall_block"]
    systems = _merged_systems()
    assessment = S1_OPENING_BRIEFING if use_agent_ui else _assessment(applied)
    lifecycle = str(resolved_agent_state.get("lifecycle") or "PLAN_READY")
    identity_established = "lookup_inventory_identity" in applied or "review_existing_notable" in applied
    finding_title = PLAN_READY_TITLE
    if identity_established:
        finding_title = f"Newly observed IP {PRIMARY_ATTACKER_IP} — {IDENTITY_PROMOTION}"
    important_evidence = [
        (
            f"Splunk MCP connected · existing notable evaluated "
            f"(IP not in IOC lookup/content): {S1_DETECTION_NAME}"
        ),
        "Requested last 30 days show firewall communication; prior 30-day novelty window is empty",
        f"Jump host {_JUMP} has 3 allowed connections with firewall identity association to {_ACCOUNT}",
        f"{_HOST_B} and {_HOST_C} are deny-only in the requested 30-day window",
    ]
    if identity_established:
        important_evidence.insert(
            2,
            f"{IDENTITY_PROMOTION} ({PRIMARY_ATTACKER_IP}) — inventory/SOC-KB evidence",
        )
    analyst = {
        "finding_title": finding_title,
        "severity_label": SEVERITY_LABEL,
        "direct_answer_line": "" if use_agent_ui else (
            f"Three internal systems identified in firewall telemetry ({_JUMP}, {_HOST_B}, {_HOST_C}); "
            "broader DNS/proxy/VPN/endpoint communication is not yet complete."
        ),
        "assessment": assessment,
        "direct_answer_summary": assessment,
        "one_sentence_finding": _what_we_found(applied),
        "what_we_found": _what_we_found(applied),
        "what_we_found_segments": _what_we_found_segments(applied),
        "affected_systems": systems,
        "important_evidence": important_evidence,
        "unconfirmed_findings": _unconfirmed_copy(outcome),
        "recommended_actions": _recommended(applied),
        "key_fields": [PRIMARY_ATTACKER_IP, _JUMP, _HOST_B, _HOST_C, _ACCOUNT],
        "splunk_results_table": [
            {
                "System": row["system"],
                "Activity": row["activity"],
                "First Seen": row["first_seen"],
                "Last Seen": row["last_seen"],
                "Allowed/Denied": row["allowed_denied"],
                "Identity / auth context": row.get("identity_auth_context") or row["auth_correlation"],
                "Risk Note": row["risk_note"],
            }
            for row in systems
        ],
        "mitre_mappings": [
            {
                "Technique": "T1110.001",
                "Name": "Password Guessing",
                "Status": "Candidate",
                "Evidence": "Firewall deny volume suggests probing; authentication failure events not retrieved",
            },
            {
                "Technique": "T1078",
                "Name": "Valid Accounts",
                "Status": "Unconfirmed",
                "Evidence": f"Firewall allow events mention {_ACCOUNT}; dedicated identity proof is not retrieved",
            },
        ],
        "unsupported_claims_avoid": [
            "Do not claim successful account compromise",
            "Do not claim lateral movement",
            "Do not claim production MCP executed",
        ],
        "missing_evidence": list(outcome["missing_evidence"]),
    }

    envelope = {
        "scenario_id": S1_SCENARIO_ID,
        "trace_id": trace_id,
        "message": assessment,
        "note": "Experience Center fixture investigation. Candidate SPL is review-only.",
        "demo_mode": True,
        "analyst_summary": assessment,
        "analyst": analyst,
        "analyst_response": analyst,
        "selected_skill": "attack_discovery",
        "route_source": "ec_fixture_selected",
        "candidate_spl": _candidate_spl_envelope(trace_id, search_1),
        "spl_validation": _validation_envelope(search_1, search_2),
        "execution": {
            "status": "simulated_receipts_packaged",
            "execution_intent": "simulated_mcp",
            "production_mcp_executed": False,
            "executed_spl": None,
            "result_count": sum(int(item.get("result_count") or 0) for item in source_evidence[:2]),
            "block_reason": "live_mcp_not_called",
        },
        "human_review": {
            "required": True,
            "review_type": "spl_review",
            "reason": "candidate_spl_review_only",
            "reviewer_role": "analyst",
            "allowed_actions": ["review_spl", "continue_investigation"],
            "safe_message_for_user": "Candidate SPL is approved by the deterministic validator and remains non-executable.",
        },
        "source_evidence": source_evidence,
        "ec_projection": _projection(
            outcome=outcome,
            evidence_state=evidence_state,
            search_1=search_1,
            search_2=search_2,
        ).model_dump(),
        "ec_actions": [item.model_dump() for item in actions],
        "ec_followups": [chip.model_dump() for chip in remaining],
        "ec_session_state": EcSessionState(
            session_id=session_id,
            family=S1_FAMILY,
            scenario_id=S1_SCENARIO_ID,
            turn=turn,
            pending_action_id=pending,
            awaiting_external=awaiting_external,
            applied_follow_up_ids=applied,
        ).model_dump(),
        "ec_provenance": {
            "envelope": "experience_center_response",
            "route_source": "ec_fixture_selected",
            "live_llm_called": False,
            "live_mcp_called": False,
            "live_rag_called": False,
            "ec_scenario_policy": "ec_search_governance_policy",
            "production_validator_read_only": True,
            "simulated_mcp": True,
        },
        "ec_search_governance_policy": search_governance_policy(),
        "ec_spl_governance": _spl_governance(search_1, search_2),
        "ec_affected_systems": systems,
        "ec_investigation_outcome": outcome,
        "ec_evidence_state": evidence_state,
        "ec_layer2_path": _layer2_path(),
        "production_side_effect": False,
        "ec_execution_journey": journey_for(S1_SCENARIO_ID, applied).model_dump(),
        "ec_status_summary": SEVERITY_REASON,
        "ec_impact_legend": [] if use_agent_ui else [
            "Activity: Confirmed",
            "Systems identified: 3",
            "Allowed communication: Jump host only",
            "Account compromise: Not confirmed",
        ],
        "ec_siem_coverage": build_s1_siem_coverage().model_dump(),
        "ec_investigation_scope": build_s1_investigation_scope().model_dump(),
        "ec_investigation_pivot": build_s1_investigation_pivot().model_dump(),
        "ec_action_readiness": [row.model_dump() for row in build_s1_action_readiness(applied, actions)],
        "ec_recommended_investigations": _recommended_investigations(applied),
        "ec_siem_tool_traces": [
            item.model_dump()
            for item in build_s1_tool_traces(
                {**search_1, "candidate_spl": _SEARCH_1_SPL},
                {**search_2, "candidate_spl": _SEARCH_2_SPL},
            )
        ],
        "ec_spl_governance_summary": (
            "Existing IOC detection did not generate an alert because the IP is not present in that lookup/content, "
            "so the assistant ran the requested last-30-days search plus a prior 30-day novelty window."
        ),
        "ec_opening_briefing": None if use_agent_ui else S1_OPENING_BRIEFING,
        "ec_agent_workflow": agent_workflow,
        "ec_agent_lifecycle": str(resolved_agent_state.get("lifecycle") or "PLAN_READY"),
        "ec_workflow_state": str(resolved_agent_state.get("lifecycle") or "PLAN_READY"),
        **extras,
    }
    return ExperienceCenterResponse.model_validate(envelope)


def s1_analyst_override(scenario_id: str, base: dict[str, Any]) -> dict[str, Any] | None:
    if scenario_id != S1_SCENARIO_ID:
        return None
    systems = _merged_systems()
    assessment = _assessment([])
    return {
        **base,
        "severity_label": "P2 High",
        "finding_title": PLAN_READY_TITLE,
        "one_sentence_finding": _what_we_found([]),
        "direct_answer_summary": assessment,
        "initial_assessment": [
            assessment,
            "Visitor asked for the last 30 days; a prior window confirms the IP is newly observed.",
            "Identity is established only after inventory/SOC-KB evidence. Raise monitoring first; HIL block only if a SOP threshold is met.",
            "Account compromise remains unconfirmed. Malicious use is not confirmed.",
        ],
        "splunk_status_line": "Simulated Splunk receipts · pgcil_soc/pgcil:firewall · last 30 days + novelty window",
        "splunk_results_table": [
            {
                "System": row["system"],
                "Activity": row["activity"],
                "First Seen": row["first_seen"],
                "Last Seen": row["last_seen"],
                "Allowed/Denied": row["allowed_denied"],
                "Auth Correlation": row["auth_correlation"],
                "Risk Note": row["risk_note"],
            }
            for row in systems
        ],
        "mitre_mappings": [
            {
                "Technique": "T1110.001",
                "Name": "Password Guessing",
                "Status": "Candidate",
                "Evidence": "Firewall deny volume suggests probing; authentication failure events not retrieved",
            },
            {
                "Technique": "T1078",
                "Name": "Valid Accounts",
                "Status": "Unconfirmed",
                "Evidence": f"Firewall allow events mention {_ACCOUNT}; dedicated identity proof is not retrieved",
            },
        ],
        "recommended_actions": _recommended([]),
        "key_fields": [PRIMARY_ATTACKER_IP, _JUMP, _HOST_B, _HOST_C, _ACCOUNT],
        "unsupported_claims_avoid": [
            "Do not claim successful account compromise",
            "Do not claim lateral movement",
        ],
        "missing_evidence": list(_base_outcome()["missing_evidence"]),
    }


def build_s1_demo_scenarios() -> dict[str, Any]:
    """PlaceholderResponse-compatible registry entry. Rich EC envelope is built by build_s1_turn."""
    from app.demo.scenarios import DemoScenario

    return {
        S1_SCENARIO_ID: DemoScenario(
            scenario_id=S1_SCENARIO_ID,
            label="S1 · Governed large-scale Splunk investigation",
            category="Flagship",
            query=S1_QUERY,
            display_query=S1_QUERY,
            demo_order=1,
            picker_tier="leadership",
            incident_family="s1_governed_splunk",
            fsm_family=S1_FAMILY,
            environment_mode="connected_coe_demo",
            expected_skill="attack_discovery",
            expected_sources=["mcp:splunk"],
            expected_sufficiency_mode="partial_answer",
            mcp_execution_mode="disabled",
            saia_available=True,
            rag_available=False,
            selected_use_case_id="net_firewall_deny_spike",
            candidate_spl=_SEARCH_1_SPL,
            aliases=(
                f"Find all communication involving suspicious IP {PRIMARY_ATTACKER_IP} and identify affected systems.",
                f"new IP {PRIMARY_ATTACKER_IP}",
                f"verify if {PRIMARY_ATTACKER_IP} is malicious",
            ),
            analyst_summary=_assessment([]),
            trace_explanation=[
                "Visitor asked to verify a newly observed IP over the last 30 days.",
                "A prior 30-day novelty window is empty, so the IP is new. Inventory identity is established only after SOC-KB evidence.",
                "Existing IOC detection: No alert — IP not present in the IOC list used by this detection. SOP: raise monitoring, then HIL block if a threshold is met.",
                "Both candidate SPLs pass real validate_spl; candidate SPL remains non-executable.",
            ],
            source_evidence=[
                _source_evidence_item(
                    "ev-s1-fw-search-1",
                    "Splunk firewall search · prior 30-day window",
                    _search_1_rows(),
                    _SEARCH_1_SPL,
                    "earliest=-60d latest=-30d",
                ),
                _source_evidence_item(
                    "ev-s1-fw-search-2",
                    "Splunk firewall search · last 30 days",
                    _search_2_rows(),
                    _SEARCH_2_SPL,
                    "earliest=-30d latest=now",
                ),
            ],
        )
    }
