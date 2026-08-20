"""S1 remediation plan findings and artifact metadata."""

from __future__ import annotations

from typing import Any

from app.demo import ec_email_drafts
from app.demo.ec_mcp_lifecycle_fixture import PRIMARY_ATTACKER_IP
from app.demo.fixtures.s1.llm_advisory import candidate_monitoring_spl, fourteen_day_auth_spl

S1_PLANNED_INCIDENT_ID = "INC-2026-89412"
_JUMP = "10.20.1.10"
_HOST_B = "10.20.4.55"
_HOST_C = "10.20.8.90"
_ACCOUNT = "svc_jump_ops"
_NOTIFY_AT = "2026-08-16T17:02:11Z"
_MONITOR_NAME = "EC_New_External_IP_Permitted_Session_Watch"
S1_MONITOR_SAVED_SEARCH_NAME = _MONITOR_NAME

_FOLLOW_UP_BY_STEP = {
    "generate_spl": "prepare_monitoring_detection",
    "validate_spl": "prepare_monitoring_detection",
    "deploy_monitoring": "raise_mcp_monitoring",
    "verify_monitoring": "raise_mcp_monitoring",
    "monitor_14d": "monitor_affected_hosts",
    "create_incident": "create_incident_ticket",
    "notify_firewall": "email_firewall_team",
    "prepare_block": "prepare_firewall_block",
    "update_ticket": "update_incident",
}

_MONITOR_NEXT_STEP = (
    f"Next step: create scheduled saved search {_MONITOR_NAME} in Splunk "
    "(splunk_run_query only — no MCP deploy tool)"
)

REM_OPERATIONAL_STATUS = {
    "generate_spl": "VALIDATED",
    "validate_spl": "VERIFIED",
    "deploy_monitoring": "EXECUTED",
    "verify_monitoring": "VERIFIED",
    "monitor_14d": "ACTIVE",
    "create_incident": "CREATED",
    "notify_firewall": "SENT",
    "prepare_block": "NOT_REQUIRED",
    "update_ticket": "APPLIED",
}


def _executed(step_id: str, applied: list[str]) -> bool:
    follow_up = _FOLLOW_UP_BY_STEP.get(step_id)
    return bool(follow_up and follow_up in applied)


def _email_preview_from_envelope(envelope: dict[str, Any], *, sent: bool) -> dict[str, Any]:
    email = envelope.get("email") if isinstance(envelope.get("email"), dict) else envelope
    body = str(email.get("body") or "")
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    return {
        "to": email.get("to") or envelope.get("logical_recipient"),
        "subject": email.get("subject"),
        "body": body,
        "body_preview": "\n".join(lines[:16]),
        "status": "sent" if sent else "queued",
        "sent_at": _NOTIFY_AT if sent else None,
        "delivery_result": "DELIVERED" if sent else None,
        "send_note": (
            f"Delivered to FIREWALL_TEAM at {_NOTIFY_AT}."
            if sent
            else "Queued — sent when the remediation plan is approved."
        ),
    }


def _kv_block(rows: list[tuple[str, str]]) -> str:
    return "\n".join(f"{key}={value}" for key, value in rows)


def finding_for_remediation_step(
    step_id: str,
    *,
    status: str,
    normalized: dict[str, Any],
    applied: list[str] | None = None,
) -> dict[str, Any] | None:
    del normalized
    applied = applied or []
    executed = _executed(step_id, applied)
    token = status.upper()
    monitoring_spl = candidate_monitoring_spl()
    auth_spl = fourteen_day_auth_spl()
    copy = {
        "generate_spl": (
            "Queued — generate 14-day monitoring SPL",
            "Generating governed monitoring SPL…",
            f"14-day monitoring SPL generated · {PRIMARY_ATTACKER_IP} → {_JUMP} 443/8443",
        ),
        "validate_spl": (
            "Queued — validate monitoring SPL",
            "Running validate_spl…",
            "Monitoring SPL verified · AUTHORIZED",
        ),
        "deploy_monitoring": (
            f"Ready — run baseline query · {_MONITOR_NAME}",
            "Executing splunk_run_query…",
            f"Baseline query executed · {_MONITOR_NAME} · next: schedule saved search in Splunk",
        ),
        "verify_monitoring": (
            "Ready — replay baseline monitoring query",
            "Re-running splunk_run_query…",
            "Query replay verified · 3 sessions in window · schedule saved search next",
        ),
        "monitor_14d": (
            f"Queued — monitor {PRIMARY_ATTACKER_IP} for 14 days",
            "Arming jump-host and auth watch…",
            f"Monitor permitted jump-host activity · 3 permitted sessions remain unexplained",
        ),
        "create_incident": (
            f"Queued — create incident {S1_PLANNED_INCIDENT_ID}",
            "Creating incident…",
            f"Incident created · {S1_PLANNED_INCIDENT_ID}",
        ),
        "notify_firewall": (
            "Queued — notify SOC team",
            "Sending SOC notification…",
            "SOC team notified · FIREWALL_TEAM",
        ),
        "prepare_block": (
            "Queued — evaluate conditional IP block",
            "Evaluating SOP blocking threshold…",
            "Conditional IP block · threshold not met",
        ),
        "update_ticket": (
            f"Queued — update {S1_PLANNED_INCIDENT_ID}",
            "Updating incident…",
            f"Incident updated · monitoring active · block threshold not met",
        ),
    }.get(step_id, ("Queued", "Running…", "Complete"))
    queued, running, complete = copy
    if token in {"RUNNING"}:
        current = running
    elif token in {
        "COMPLETE",
        "VALIDATED",
        "VERIFIED",
        "DEPLOYED",
        "EXECUTED",
        "ACTIVE",
        "CREATED",
        "SENT",
        "APPLIED",
        "NOT_REQUIRED",
    }:
        current = complete if executed or step_id == "prepare_block" else queued.replace("Queued —", "Ready —")
    else:
        current = queued

    details: dict[str, Any] = {
        "operational_status": REM_OPERATIONAL_STATUS.get(step_id, token),
        "execution": "AUTHORIZED → EXECUTED" if executed and step_id != "prepare_block" else (
            "EVALUATED → NOT_REQUIRED" if step_id == "prepare_block" else "REQUESTED"
        ),
    }

    if step_id in {"generate_spl", "validate_spl", "deploy_monitoring", "verify_monitoring", "monitor_14d"}:
        details["normalized_spl"] = monitoring_spl
        details["related_spl"] = {"svc_jump_ops_auth": auth_spl} if step_id == "monitor_14d" else None
        details["connector"] = "Splunk MCP"
        details["request"] = _kv_block(
            [
                ("action", "splunk_run_query"),
                ("indicator", PRIMARY_ATTACKER_IP),
                ("dest", _JUMP),
                ("dest_ports", "443,8443"),
                ("auth_account", _ACCOUNT),
                ("window", "14d"),
                ("candidate_name", _MONITOR_NAME),
            ]
        )
        if step_id in {"generate_spl", "validate_spl"}:
            details["response"] = _kv_block(
                [
                    ("status", "validated"),
                    ("candidate_name", _MONITOR_NAME),
                    ("dest", _JUMP),
                    ("dest_ports", "443,8443"),
                ]
            )
        elif step_id in {"deploy_monitoring", "verify_monitoring", "monitor_14d"}:
            details["response"] = _kv_block(
                [
                    ("status", "complete" if executed else "queued"),
                    ("tool", "splunk_run_query"),
                    ("row_count", "3" if executed else "0"),
                    ("allow_count", "3"),
                    ("dest", _JUMP),
                    ("dest_ports", "443,8443"),
                ]
            )
            if step_id in {"deploy_monitoring", "verify_monitoring"}:
                details["next_steps"] = _MONITOR_NEXT_STEP

    if step_id == "create_incident":
        details["ticket_detail"] = {
            "ticket_id": S1_PLANNED_INCIDENT_ID,
            "ticket_type": "incident",
            "priority": "P2",
            "title": f"Newly observed MCP endpoint {PRIMARY_ATTACKER_IP} — monitoring first",
            "status": "CREATED" if executed else "QUEUED",
            "assignee_group": "SOC",
            "linked_advisory": PRIMARY_ATTACKER_IP,
        }
        details["connector"] = "ITSM"
        details["request"] = _kv_block(
            [
                ("action", "Create incident"),
                ("indicator", PRIMARY_ATTACKER_IP),
                ("severity", "P2"),
                ("affected", f"{_JUMP},{_HOST_B},{_HOST_C}"),
                ("evidence_refs", "ev-s1-fw-search-2,ev-s1-permitted-sessions"),
            ]
        )
        details["response"] = _kv_block(
            [
                ("incident_id", S1_PLANNED_INCIDENT_ID),
                ("status", "created" if executed else "queued"),
            ]
        )

    if step_id == "update_ticket":
        details["ticket_detail"] = {
            "ticket_id": S1_PLANNED_INCIDENT_ID,
            "ticket_type": "incident_update",
            "priority": "P2",
            "title": f"Update {S1_PLANNED_INCIDENT_ID} — monitoring active; malicious use unconfirmed",
            "status": "APPLIED" if executed else "QUEUED",
            "assignee_group": "SOC",
            "linked_incident": S1_PLANNED_INCIDENT_ID,
        }
        details["connector"] = "ITSM"
        details["request"] = _kv_block(
            [
                ("action", "Update incident"),
                ("ticket_id", S1_PLANNED_INCIDENT_ID),
                ("monitoring", "ACTIVE"),
                ("block", "NOT_REQUIRED"),
            ]
        )
        details["response"] = _kv_block(
            [
                ("incident_id", S1_PLANNED_INCIDENT_ID),
                ("status", "updated" if executed else "queued"),
            ]
        )

    if step_id == "notify_firewall":
        envelope = ec_email_drafts.s1_firewall_team_email(
            applied=applied,
            jump=_JUMP,
            host_b=_HOST_B,
            host_c=_HOST_C,
            account=_ACCOUNT,
            ticket_executed=executed,
        )
        details["email_draft"] = _email_preview_from_envelope(envelope, sent=executed)
        details["email_extra"] = envelope
        details["connector"] = "Email"
        details["notification"] = {
            "recipient": "FIREWALL_TEAM",
            "sent_at": _NOTIFY_AT if executed else None,
            "delivery_result": "DELIVERED" if executed else None,
        }
        details["request"] = _kv_block(
            [
                ("action", "Send notification"),
                ("to", "FIREWALL_TEAM"),
                ("subject", str(envelope.get("email", {}).get("subject") or "")),
            ]
        )
        details["response"] = _kv_block(
            [
                ("status", "sent" if executed else "queued"),
                ("delivery_result", "DELIVERED" if executed else "PENDING"),
                ("sent_at", _NOTIFY_AT if executed else ""),
            ]
        )

    if step_id == "prepare_block":
        details["connector"] = "SOAR / firewall"
        details["request"] = _kv_block(
            [
                ("action", "Evaluate ip_block"),
                ("indicator", PRIMARY_ATTACKER_IP),
                ("sop_threshold", "not_met"),
            ]
        )
        details["response"] = _kv_block(
            [
                ("decision", "NOT_REQUIRED"),
                ("reason", "SOP blocking threshold not met"),
                ("executed", "false"),
            ]
        )

    return {
        "headline_finding": current,
        "headlines_by_status": {
            "QUEUED": queued,
            "RUNNING": running,
            "COMPLETE": complete,
            "VALIDATED": complete,
            "VERIFIED": complete,
            "DEPLOYED": complete,
            "EXECUTED": complete,
            "ACTIVE": complete,
            "CREATED": complete,
            "SENT": complete,
            "APPLIED": complete,
            "NOT_REQUIRED": complete,
        },
        "attention_state": "ATTENTION" if step_id == "monitor_14d" else "NORMAL",
        "key_evidence": (
            [
                f"dest={_JUMP}",
                "dest_ports=443,8443",
                f"auth_account={_ACCOUNT}",
                "3 permitted sessions remain unexplained",
            ]
            if step_id == "monitor_14d"
            else []
        ),
        "details": {key: value for key, value in details.items() if value not in (None, "", [])},
    }


def enrich_remediation_steps(
    steps: list[dict[str, Any]],
    *,
    normalized: dict[str, Any],
    applied: list[str],
) -> list[dict[str, Any]]:
    del normalized
    enriched: list[dict[str, Any]] = []
    for step in steps:
        finding = finding_for_remediation_step(
            str(step["id"]),
            status=str(step.get("status") or "QUEUED"),
            normalized={},
            applied=applied,
        )
        enriched.append({**step, "finding": finding, "result": (finding or {}).get("headline_finding")})
    return enriched


def build_s1_remediation_summary(*, selected_count: int, total_count: int) -> dict[str, Any]:
    return {
        "title": "Remediation plan ready",
        "steps_completed": 0,
        "steps_total": selected_count,
        "plan_steps": f"{selected_count}/{total_count} selected",
        "metrics": [
            {"label": "Monitoring", "value": "14-day Splunk watch"},
            {"label": "Block", "value": "Not required yet"},
            {"label": "Risk", "value": "MEDIUM"},
        ],
    }


def build_s1_remediation_conclusion(*, normalized: dict[str, Any]) -> dict[str, Any]:
    del normalized
    return {
        "title": "Remediation approach",
        "headline": (
            f"Deploy 14-day targeted monitoring for {PRIMARY_ATTACKER_IP}. "
            "Do not block — SOP threshold is not met."
        ),
        "narrative_points": [
            f"Generate and validate monitoring SPL, then run baseline splunk_run_query for {PRIMARY_ATTACKER_IP} "
            f"(including {_JUMP} 443/8443 and {_ACCOUNT} auth correlation). "
            f"Schedule {_MONITOR_NAME} as a saved search in Splunk — MCP has no deploy tool.",
            f"Open incident {S1_PLANNED_INCIDENT_ID} and notify SOC that monitoring is active.",
            "Conditional IP block stays NOT REQUIRED — Network/SOC block approval is not requested.",
            "Keep risk MEDIUM. Malicious use is not confirmed. Monitoring does not prove safety.",
        ],
    }
