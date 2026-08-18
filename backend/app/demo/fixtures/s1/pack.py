"""S1 flagship: governed 60-day suspicious-IP investigation as two bounded 30-day searches."""

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
from app.safeguards.spl_validator import validate_spl
from app.spl.template_registry import get_spl_template, load_spl_templates

S1_SCENARIO_ID = "s1_governed_splunk_investigation"
S1_FAMILY = "s1_governed_splunk"
S1_QUERY = (
    f"Find all communication involving suspicious IP {PRIMARY_ATTACKER_IP} and identify affected systems."
)

_JUMP = "10.20.1.10"
_HOST_B = "10.20.4.55"
_HOST_C = "10.20.8.90"
_ACCOUNT = "svc_jump_ops"

_SEARCH_1_SPL = (
    f"search index=pgcil_soc sourcetype=pgcil:firewall earliest=-60d latest=-30d "
    f"(src={PRIMARY_ATTACKER_IP} OR dest={PRIMARY_ATTACKER_IP}) "
    "| stats count as event_count count(eval(action=\"deny\")) as deny_count "
    "count(eval(action=\"allow\")) as allow_count min(_time) as first_seen max(_time) as last_seen "
    "dc(dest_port) as distinct_ports values(dest_port) as dest_ports values(action) as actions by src, dest "
    "| sort -event_count | head 100"
)
_SEARCH_2_SPL = _SEARCH_1_SPL.replace("earliest=-60d latest=-30d", "earliest=-30d latest=now")


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
    return [
        {
            "src": PRIMARY_ATTACKER_IP,
            "dest": _JUMP,
            "event_count": 920,
            "deny_count": 920,
            "allow_count": 0,
            "actions": "deny",
            "dest_ports": "443,8443,22",
            "first_seen": "2026-06-18T04:12:00Z",
            "last_seen": "2026-07-16T21:40:00Z",
            "search_window": "earliest=-60d latest=-30d",
        },
        {
            "src": PRIMARY_ATTACKER_IP,
            "dest": _HOST_B,
            "event_count": 610,
            "deny_count": 610,
            "allow_count": 0,
            "actions": "deny",
            "dest_ports": "22,443",
            "first_seen": "2026-06-20T11:03:00Z",
            "last_seen": "2026-07-15T18:22:00Z",
            "search_window": "earliest=-60d latest=-30d",
        },
        {
            "src": PRIMARY_ATTACKER_IP,
            "dest": _HOST_C,
            "event_count": 480,
            "deny_count": 480,
            "allow_count": 0,
            "actions": "deny",
            "dest_ports": "3389,443",
            "first_seen": "2026-06-22T09:18:00Z",
            "last_seen": "2026-07-14T07:55:00Z",
            "search_window": "earliest=-60d latest=-30d",
        },
    ]


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
            "activity": "Denied probing plus 3 allowed connections",
            "first_seen": "2026-06-18T04:12:00Z",
            "last_seen": "2026-08-16T16:44:00Z",
            "allowed_denied": "3 allowed / 1842 denied",
            "identity_auth_context": f"Firewall telemetry associates {_ACCOUNT} with the 3 allow events",
            "auth_correlation": f"Firewall telemetry associates {_ACCOUNT} with the 3 allow events",
            "risk_note": "Highest-priority host; account use is correlated, not confirmed as compromise",
            "deny_count": 1842,
            "allow_count": 3,
            "ports": "443,8443,22",
        },
        {
            "system": _HOST_B,
            "role": "Internal host",
            "activity": "Denied connections only",
            "first_seen": "2026-06-20T11:03:00Z",
            "last_seen": "2026-08-15T19:02:00Z",
            "allowed_denied": "0 allowed / 1260 denied",
            "identity_auth_context": "None in firewall results",
            "auth_correlation": "None in firewall results",
            "risk_note": "Perimeter blocks held; no allowed traffic in either window",
            "deny_count": 1260,
            "allow_count": 0,
            "ports": "22,443",
        },
        {
            "system": _HOST_C,
            "role": "Internal host",
            "activity": "Denied connections only",
            "first_seen": "2026-06-22T09:18:00Z",
            "last_seen": "2026-08-14T22:17:00Z",
            "allowed_denied": "0 allowed / 980 denied",
            "identity_auth_context": "None in firewall results",
            "auth_correlation": "None in firewall results",
            "risk_note": "RDP/SSL deny pattern; no allowed traffic in either window",
            "deny_count": 980,
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
        "query_or_request_summary": f"Simulated Splunk search receipt · {window}",
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
        "provenance": "simulated_mcp",
        "created_at": "2026-08-16T00:00:00Z",
    }


def search_governance_policy() -> dict[str, Any]:
    return {
        "policy_id": "ec_search_governance_policy",
        "provenance": "ec_scenario_policy",
        "kind": "ec_scenario_policy",
        "detail": "ec_search_governance_policy",
        "user_supplied_time_range": False,
        "coverage_days": 60,
        "window_days": 30,
        "split": "30+30",
        "windows": [
            {
                "search_id": "search_1",
                "label": "First 30-day window",
                "earliest": "-60d",
                "latest": "-30d",
                "days": 30,
            },
            {
                "search_id": "search_2",
                "label": "Next 30-day window",
                "earliest": "-30d",
                "latest": "now",
                "days": 30,
            },
        ],
        "index": "pgcil_soc",
        "sourcetype": "pgcil:firewall",
        "forbid_index_wildcard": True,
        "why": (
            "Historical suspicious-IP investigations cover 60 days using two bounded 30-day searches "
            "instead of one unrestricted search."
        ),
        "visitor_summary": "Environment search governance applied.",
        "not_production_spl_policy": True,
        "not_production_phase_policy": True,
    }


def _followup_catalog() -> tuple[EcFollowUpChip, ...]:
    return (
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
    )


S1_FOLLOWUP_IDS = frozenset(chip.follow_up_id for chip in _followup_catalog())


def _base_evidence_state() -> list[dict[str, Any]]:
    return [
        {
            "id": "siem_existing_search",
            "label": "Existing Splunk suspicious-IP search",
            "status": "OBTAINED",
            "provenance": "simulated_mcp",
            "detail": f"{S1_DETECTION_NAME} replayed (partial coverage)",
        },
        {
            "id": "splunk_fw_search_1",
            "label": "Splunk firewall search 1",
            "status": "OBTAINED",
            "provenance": "simulated_mcp",
            "detail": "First 30-day window (-60d to -30d)",
        },
        {
            "id": "splunk_fw_search_2",
            "label": "Splunk firewall search 2",
            "status": "OBTAINED",
            "provenance": "simulated_mcp",
            "detail": "Next 30-day window (-30d to now)",
        },
        {
            "id": "auth_correlation",
            "label": "Firewall identity association",
            "status": "OBTAINED",
            "provenance": "experience_center_fixture",
            "detail": f"Firewall allow events on {_JUMP} associated with {_ACCOUNT} (not successful authentication)",
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
            "id": "team_email",
            "label": "Firewall/security team email",
            "status": "MISSING",
            "provenance": "experience_center_fixture",
            "detail": "Outbound team notification not prepared",
        },
        {
            "id": "firewall_verify",
            "label": "Firewall rule verification",
            "status": "MISSING",
            "provenance": "experience_center_fixture",
            "detail": "No simulated rule verification until execute completes",
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
        "disposition": "suspicious",
        "confirmed": [
            f"Suspicious IP {PRIMARY_ATTACKER_IP} communicated with {_JUMP}, {_HOST_B}, and {_HOST_C} in firewall telemetry",
            "Traffic was observed across both historical 30-day windows",
            "Denied traffic exists on all three affected systems",
            f"At least one relevant allowed connection exists on jump host {_JUMP}",
            f"Firewall telemetry associates {_ACCOUNT} with allowed events on {_JUMP}",
        ],
        "supported": [
            "Persistent external probing and multi-port deny activity across three internal destinations",
        ],
        "unconfirmed": [
            "Successful account compromise",
            "Successful authentication attributable to the suspicious IP",
            "Valid-account abuse (T1078)",
            "Password guessing (T1110.001) — requires authentication failure evidence",
            "Lateral movement from the jump host to peer systems",
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
        if "Auth log source IP is the suspicious indicator" not in outcome["unconfirmed"]:
            outcome["unconfirmed"].append("Auth log source IP is the suspicious indicator")

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
            f"{PRIMARY_ATTACKER_IP} is listed in the EC TI fixture as a suspicious scanning source (TEST-NET-2 documentation range); not a live intel feed",
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
                        "category": "suspicious_scanner",
                        "feed": "ec_ti_fixture",
                        "live_feed": False,
                        "note": "TEST-NET-2 documentation address used as the EC suspicious-IP fixture",
                    }
                ],
                "result_count": 1,
                "provenance": "experience_center_fixture",
                "warnings": ["coe_synthetic_fixture"],
            }
        )
        outcome["missing_evidence"] = [item for item in outcome["missing_evidence"] if "Threat intelligence" not in item]
        if f"{PRIMARY_ATTACKER_IP} is listed as a suspicious scanning source in the EC TI fixture" not in outcome["confirmed"]:
            outcome["confirmed"].append(
                f"{PRIMARY_ATTACKER_IP} is listed as a suspicious scanning source in the EC TI fixture"
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

    existing_kinds = {item.kind for item in actions}
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
                        f"SOC Experience Center request to block {PRIMARY_ATTACKER_IP} after governed "
                        f"60-day review of {_JUMP}, {_HOST_B}, and {_HOST_C}. Compromise is unconfirmed; "
                        "containment is HIL-gated and must go through SOAR / firewall MCP if configured."
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
            "indicator": PRIMARY_ATTACKER_IP,
            "affected_systems": [_JUMP, _HOST_B, _HOST_C],
            "severity": "P2 High",
            "disposition": outcome["disposition"],
            "confirmed": list(outcome["confirmed"]),
            "unconfirmed": list(outcome["unconfirmed"]),
            "timeline": "Governed 60-day coverage as two 30-day windows",
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
        email = next((item for item in actions if item.kind == "email_send"), None)
        if email is None:
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
            "Draft prepared for logical recipient FIREWALL_TEAM; not transmitted until Send email",
        )
        extras["ec_email"] = {
            "to": email_extra["email"]["to"],
            "logical_recipient": "FIREWALL_TEAM",
            "subject": email_extra["email"]["subject"],
            "status": "draft_pending_send",
            "not_transmitted": True,
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
        _set_status(evidence_state, "incident_update", "MISSING", "Ticket update draft is waiting for confirmation")

    if "generate_closure_summary" in applied:
        outcome["closure_summary"] = (
            f"Suspicious IP {PRIMARY_ATTACKER_IP} investigated over governed 60-day coverage (30+30). "
            "Probing is supported; account compromise and lateral movement remain unconfirmed. "
            "Firewall block is HIL-gated and is not auto-applied from initial evidence."
        )
        _set_status(evidence_state, "closure", "OBTAINED", "Executive closure summary generated")

    return outcome, evidence_state, extra_evidence, actions, extras


def _assessment(applied: list[str]) -> str:
    extra = ""
    if "check_endpoint_activity" in applied:
        extra = " Endpoint review did not confirm malicious process activity."
    if "check_threat_intel" in applied:
        extra += f" Indicator {PRIMARY_ATTACKER_IP} is listed as a suspicious scanning source in the EC threat-intel fixture."
    return (
        f"Firewall telemetry shows suspicious activity from {PRIMARY_ATTACKER_IP} against {_JUMP}, {_HOST_B}, and {_HOST_C} "
        "during a governed 60-day review. This is firewall-observed communication only — DNS, proxy, VPN, and endpoint "
        "network paths were not queried. Persistent probing is supported; account compromise and lateral movement are not confirmed."
        + extra
    )


def _what_we_found(applied: list[str]) -> str:
    text = (
        f"Existing Splunk content ({S1_DETECTION_NAME}) was reused for recent suspicious-IP firewall activity. "
        "Because full 60-day history was not covered, two governed 30+30 firewall searches completed the historical view. "
        f"All three internal systems show denied traffic in both windows. Jump host {_JUMP} also has "
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
        "Check threat intelligence for the suspicious IP",
        "Compare with previous incidents",
        "Assess DNS / proxy / VPN communication if broader coverage is required",
    ]
    mapping = {
        "check_successful_auth": 0,
        "check_privileged_accounts": 1,
        "check_endpoint_activity": 2,
        "check_threat_intel": 3,
        "compare_previous_incidents": 4,
    }
    return [step for idx, step in enumerate(steps) if not any(mapping.get(fid) == idx for fid in applied)]


def _recommended(applied: list[str]) -> list[str]:
    steps = [
        "Review successful authentications and identity context for the jump-host service account",
        "Check privileged-account impact without assuming compromise",
        "Query endpoint activity on the jump host",
        "Check threat intelligence for the suspicious IP",
        "Compare with previous incidents before containment",
        "Prepare a firewall block request only after analyst approval",
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
        "prepare_firewall_block": 5,
        "create_incident_ticket": 6,
        "email_firewall_team": 7,
        "verify_firewall_block": 8,
        "update_incident": 9,
        "generate_closure_summary": 10,
    }
    remaining = [step for idx, step in enumerate(steps) if not any(mapping.get(fid) == idx for fid in applied)]
    return remaining or ["Document the investigation outcome and keep compromise unconfirmed until identity evidence lands."]


def _unconfirmed_copy(outcome: dict[str, Any]) -> list[str]:
    return list(outcome["unconfirmed"])


def _spl_governance(search_1: dict[str, Any], search_2: dict[str, Any]) -> dict[str, Any]:
    policy = search_governance_policy()
    return {
        "user_request": S1_QUERY,
        "time_range_supplied": False,
        "environment_governance": policy["visitor_summary"],
        "policy": policy,
        "why": policy["why"],
        "searches": [
            {
                "search_id": "search_1",
                "label": "Search 1 · first 30-day window",
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
                "label": "Search 2 · next 30-day window",
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
        "evidence_merge": "Both simulated search receipts were merged into one investigation by dest host",
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
            summary="Visitor asked for communications involving a suspicious IP and named no time range.",
            items=[
                f"indicator={PRIMARY_ATTACKER_IP}",
                "time_range_supplied=false",
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
            summary="Environment search governance applied: 60-day coverage as two bounded 30-day searches.",
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
            summary=f"Disposition {outcome['disposition']}. Compromise and lateral movement remain unconfirmed.",
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
            "Visitor supplied no time range; EC search-governance policy selected 30+30 windows.",
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


def _existing_detection_evidence() -> dict[str, Any]:
    return {
        "evidence_id": "ev-s1-existing-search",
        "trace_id": "pending",
        "source_type": "splunk_saved_search",
        "source_name": S1_DETECTION_NAME,
        "tool_name": "splunk_run_saved_search",
        "collection_status": "collected",
        "query_or_request_summary": f"saved_search={S1_SAVED_SEARCH_NAME} · recent window",
        "result_count": 3,
        "fields_returned": ["src", "dest", "event_count", "actions"],
        "preview_rows": _search_2_rows(),
        "provenance": "simulated_mcp",
        "warnings": ["coe_synthetic_fixture", "partial_coverage_only"],
        "output_type": "fixture_preview",
    }


def build_s1_turn(
    *,
    session_id: str,
    turn: int,
    applied_follow_up_ids: list[str],
    pending_action_id: str | None = None,
    awaiting_external: bool = False,
) -> ExperienceCenterResponse:
    search_1 = _validate_search(_SEARCH_1_SPL)
    search_2 = _validate_search(_SEARCH_2_SPL)
    if not search_1.get("approved") or not search_2.get("approved"):
        raise RuntimeError(
            "S1 fixture SPL failed real validate_spl; fix the EC SPL fixture. "
            f"search_1={search_1.get('reject_reasons')} search_2={search_2.get('reject_reasons')}"
        )

    trace_id = f"demo-{S1_SCENARIO_ID}-{uuid4().hex[:8]}"
    applied = list(applied_follow_up_ids)
    outcome = deepcopy(_base_outcome())
    evidence_state = deepcopy(_base_evidence_state())
    extra_evidence: list[dict[str, Any]] = []
    outcome, evidence_state, extra_evidence, actions, extras = _apply_follow_up_effects(
        applied,
        session_id=session_id,
        outcome=outcome,
        evidence_state=evidence_state,
        extra_evidence=extra_evidence,
    )
    pending = pending_action_id
    if not pending:
        prepared = next((item for item in actions if item.state in {"PREPARED", "APPROVAL_REQUIRED"}), None)
        pending = prepared.action_id if prepared else None

    source_evidence = [
        _existing_detection_evidence(),
        _source_evidence_item(
            "ev-s1-fw-search-1",
            "Simulated Splunk firewall search 1",
            _search_1_rows(),
            _SEARCH_1_SPL,
            "earliest=-60d latest=-30d",
        ),
        _source_evidence_item(
            "ev-s1-fw-search-2",
            "Simulated Splunk firewall search 2",
            _search_2_rows(),
            _SEARCH_2_SPL,
            "earliest=-30d latest=now",
        ),
        *extra_evidence,
    ]
    for item in source_evidence:
        item["trace_id"] = trace_id

    remaining = [chip for chip in _followup_catalog() if chip.follow_up_id not in applied]
    firewall = next((item for item in actions if item.kind == "firewall_block"), None)
    if firewall is None or firewall.state not in {"EXECUTED", "VERIFIED"}:
        remaining = [chip for chip in remaining if chip.follow_up_id != "verify_firewall_block"]
    systems = _merged_systems()
    assessment = _assessment(applied)
    analyst = {
        "finding_title": f"Suspicious IP observed across three internal systems — compromise not confirmed",
        "severity_label": "P2 High",
        "direct_answer_line": (
            f"Three internal systems identified in firewall telemetry ({_JUMP}, {_HOST_B}, {_HOST_C}); "
            "broader DNS/proxy/VPN/endpoint communication is not yet complete."
        ),
        "assessment": assessment,
        "direct_answer_summary": assessment,
        "one_sentence_finding": _what_we_found(applied),
        "what_we_found": _what_we_found(applied),
        "affected_systems": systems,
        "important_evidence": [
            f"Existing Splunk search reused: {S1_DETECTION_NAME}",
            f"{PRIMARY_ATTACKER_IP} appears in both 30-day firewall windows against three internal systems",
            f"Jump host {_JUMP} has 3 allowed connections with firewall identity association to {_ACCOUNT}",
            f"{_HOST_B} and {_HOST_C} are deny-only in both windows",
            "Governed 30+30 searches completed the 60-day firewall history gap",
        ],
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
        "ec_status_summary": (
            "P2 High · Activity: Confirmed · Systems: 3 · Allowed on jump host · "
            "Account compromise: Not confirmed · Lateral movement: Not confirmed"
        ),
        "ec_impact_legend": [
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
            "Existing SIEM coverage did not satisfy the complete 60-day historical requirement, so the assistant "
            "ran two governed 30-day firewall searches to complete the view."
        ),
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
        "finding_title": f"Governed 60-day investigation of {PRIMARY_ATTACKER_IP}",
        "one_sentence_finding": _what_we_found([]),
        "direct_answer_summary": assessment,
        "initial_assessment": [
            assessment,
            "Visitor supplied no time range; environment search governance applied 30+30 windows.",
            "Account compromise and lateral movement remain unconfirmed.",
        ],
        "splunk_status_line": "Simulated Splunk receipts · pgcil_soc/pgcil:firewall · 30+30 merge",
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
            aliases=(),
            analyst_summary=_assessment([]),
            trace_explanation=[
                "Visitor supplied no time range.",
                "EC search-governance policy applied 60-day coverage as two bounded 30-day searches.",
                "Both candidate SPLs pass real validate_spl; candidate SPL remains non-executable.",
            ],
            source_evidence=[
                _source_evidence_item(
                    "ev-s1-fw-search-1",
                    "Simulated Splunk firewall search 1",
                    _search_1_rows(),
                    _SEARCH_1_SPL,
                    "earliest=-60d latest=-30d",
                ),
                _source_evidence_item(
                    "ev-s1-fw-search-2",
                    "Simulated Splunk firewall search 2",
                    _search_2_rows(),
                    _SEARCH_2_SPL,
                    "earliest=-30d latest=now",
                ),
            ],
        )
    }
