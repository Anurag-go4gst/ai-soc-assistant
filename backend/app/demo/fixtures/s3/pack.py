"""S3 — firewall-team coordination. Independent of S1 session. EC fixture only."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.demo.ec_mcp_lifecycle_fixture import INCIDENT_ID, PRIMARY_ATTACKER_IP
from app.demo.fixtures import common as C

S3_SCENARIO_ID = "s3_firewall_team_coordination"
S3_FAMILY = "s3_firewall_coordination"
S3_QUERY = (
    "Malicious activity from this IP is confirmed. Follow our company's firewall-block process "
    "and coordinate the block with the firewall team."
)
S3_FOLLOWUPS = (
    C.chip("show_firewall_process", "Retrieve firewall-block process"),
    C.chip("prepare_firewall_email", "Prepare firewall-team request"),
    C.chip("send_firewall_email", "Send request to firewall team", action=True),
    C.chip("ingest_firewall_reply", "Review firewall-team reply"),
    C.chip("fetch_firewall_ticket", "Fetch firewall change ticket"),
    C.chip("reply_firewall_team", "Reply to firewall team", action=True),
    C.chip("remove_whitelist", "Remove vendor whitelist", action=True),
    C.chip("request_ip_block", "Request IP block", action=True),
    C.chip("create_security_incident", "Create security incident", action=True),
    C.chip("update_incident_ticket", "Update incident with team evidence", action=True),
    C.chip("notify_soc_lead", "Notify SOC lead", action=True),
    C.chip("verify_firewall_rule", "Verify firewall rule", action=True),
)
S3_FOLLOWUP_IDS = frozenset(item.follow_up_id for item in S3_FOLLOWUPS)

_PROCESS_FIELDS = {
    "malicious_ip": PRIMARY_ATTACKER_IP,
    "reason": "Confirmed malicious scanning and allow/deny mix against internal jump host",
    "incident_reference": INCIDENT_ID,
    "severity": "P2 High",
    "affected_systems": ["10.20.1.10", "10.20.4.55", "10.20.8.90"],
    "evidence_summary": "Firewall telemetry shows coordinated denies plus limited allows from the indicator.",
    "first_seen": "2026-06-18T04:12:00Z",
    "last_seen": "2026-08-16T16:44:00Z",
    "requested_block_duration": "30 days, review at expiry",
    "business_impact": "Vendor testing exception may be in conflict with observed traffic",
    "requester": "SOC analyst (Experience Center session)",
    "required_approval": "Firewall change owner + SOC lead",
    "rollback": "Restore previous exception only with documented business owner approval",
}

_WORKFLOW = (
    "Investigation",
    "Process retrieved",
    "Request prepared",
    "Email sent",
    "Awaiting team",
    "Response received",
    "Evidence updated",
    "Decision",
    "Remediation",
    "Verified",
)


def _workflow_state(applied: list[str]) -> str:
    if "verify_firewall_rule" in applied:
        return "Verified"
    if "request_ip_block" in applied or "remove_whitelist" in applied:
        return "Remediation"
    if "ingest_firewall_reply" in applied:
        return "Decision"
    if "send_firewall_email" in applied:
        return "AWAITING_FIREWALL_TEAM_CONFIRMATION"
    if "prepare_firewall_email" in applied:
        return "Request prepared"
    if "show_firewall_process" in applied:
        return "Process retrieved"
    return "Investigation"


def _base_outcome() -> dict[str, Any]:
    return {
        "disposition": "suspicious",
        "confirmed": [
            f"Malicious-pattern traffic from {PRIMARY_ATTACKER_IP} is in evidence",
            "Internal hosts 10.20.1.10, 10.20.4.55, and 10.20.8.90 were contacted",
        ],
        "supported": ["Firewall deny/allow mix supports a coordinated scan"],
        "unconfirmed": [
            "Whether a current firewall exception fully explains the traffic",
            "Whether the vendor-testing whitelist is still valid",
            "Whether a block should proceed without exception review",
        ],
        "missing_evidence": ["Firewall-team confirmation", "Whitelist approval record", "Exception expiry"],
        "production_investigation_outcome_unused": True,
    }


def _base_state() -> list[dict[str, Any]]:
    return [
        C.state_item("prior_investigation", "Prior suspicious-IP investigation", "OBTAINED", f"Compact fixture state for {PRIMARY_ATTACKER_IP}"),
        C.state_item("fw_process", "Company firewall-block process", "AVAILABLE_NOT_QUERIED", "Process knowledge not opened", "ec_scenario_policy"),
        C.state_item("fw_email", "Firewall-team email", "MISSING", "Request not yet sent"),
        C.state_item("fw_reply", "Firewall-team reply", "MISSING", "No inbound confirmation"),
        C.state_item("whitelist", "Vendor whitelist record", "MISSING", "Exception not reviewed"),
        C.state_item("fw_ticket", "Firewall change ticket", "MISSING", "Ticket not fetched"),
    ]


def _apply(applied: list[str], session_id: str, outcome: dict[str, Any], state: list[dict[str, Any]], extra: list[dict[str, Any]]) -> bool:
    awaiting = False
    if "show_firewall_process" in applied:
        C.set_status(state, "fw_process", "OBTAINED", "Mandatory request fields retrieved from EC process knowledge", "ec_scenario_policy")
        extra.append(C.evidence("ev-s3-process", "kb_fixture", "Firewall-block process", [dict(_PROCESS_FIELDS)], provenance="ec_scenario_policy"))
        outcome["missing_evidence"] = [item for item in outcome["missing_evidence"] if "process" not in item.lower()]

    if "prepare_firewall_email" in applied:
        extra.append(C.evidence("ev-s3-email-draft", "email_mcp_fixture", "Prepared firewall-team request", [dict(_PROCESS_FIELDS)], provenance="simulated_mcp"))

    if "send_firewall_email" in applied:
        C.ensure_executed_action(
            kind="email_send",
            label="Send firewall-block request",
            session_id=session_id,
            scenario_id=S3_SCENARIO_ID,
            extra={"email": {"to": "firewall-team@internal", "subject": f"Block request for {PRIMARY_ATTACKER_IP}", "fields": _PROCESS_FIELDS}},
        )
        C.set_status(state, "fw_email", "OBTAINED", "Request sent; awaiting firewall-team confirmation")
        awaiting = "ingest_firewall_reply" not in applied

    if "ingest_firewall_reply" in applied:
        awaiting = False
        C.set_status(state, "fw_reply", "OBTAINED", "Inbound reply: IP manually whitelisted yesterday for vendor testing")
        extra.append(C.evidence(
            "ev-s3-reply",
            "email_mcp_fixture",
            "Firewall-team inbound reply",
            [{
                "from": "firewall-team@internal",
                "body": "This IP was manually whitelisted yesterday for vendor testing.",
                "received_at": "2026-08-16T18:02:00Z",
            }],
            provenance="experience_center_fixture",
        ))
        extra.append(C.evidence(
            "ev-s3-whitelist",
            "firewall_change_fixture",
            "Whitelist exception record",
            [{
                "indicator": PRIMARY_ATTACKER_IP,
                "approved_by": "netops.oncall",
                "created": "2026-08-15T09:10:00Z",
                "expiry": "2026-08-22T09:10:00Z",
                "business_purpose": "Vendor connectivity test for remote support",
                "malicious_traffic_during_exception": "Possible — last_seen overlaps exception window",
                "explains_all_evidence": False,
            }],
            provenance="simulated_mcp",
        ))
        C.set_status(state, "whitelist", "OBTAINED", "Exception exists; does not automatically make traffic benign")
        outcome["confirmed"] = [
            *outcome["confirmed"],
            "Firewall team reports a vendor-testing whitelist created yesterday",
        ]
        outcome["unconfirmed"] = [
            "Whether vendor activity explains the full evidence window",
            "Whether malicious traffic occurred during the exception",
            "Whether the exception should be removed",
        ]
        outcome["missing_evidence"] = ["Business-owner reconfirmation of vendor test", "Packet-level confirmation inside exception window"]
        outcome["disposition"] = "needs_reassessment"
        outcome["reassessment"] = {
            "whitelist_approver": "netops.oncall",
            "created": "2026-08-15T09:10:00Z",
            "expiry": "2026-08-22T09:10:00Z",
            "business_purpose": "Vendor connectivity test for remote support",
            "blind_benign": False,
            "blind_malicious": False,
        }

    if "fetch_firewall_ticket" in applied:
        C.ensure_executed_action(
            kind="ticket_fetch",
            label="Fetch firewall change ticket",
            session_id=session_id,
            scenario_id=S3_SCENARIO_ID,
            extra={"ticket": {"id": "CHG-FW-8841", "status": "exception_active"}},
        )
        C.set_status(state, "fw_ticket", "OBTAINED", "CHG-FW-8841 exception_active")

    if "reply_firewall_team" in applied:
        C.ensure_executed_action(
            kind="email_reply",
            label="Reply to firewall team",
            session_id=session_id,
            scenario_id=S3_SCENARIO_ID,
            extra={"email": {"to": "firewall-team@internal", "subject": f"Re: Block request for {PRIMARY_ATTACKER_IP}"}},
        )

    if "remove_whitelist" in applied:
        C.ensure_hil_action(
            kind="firewall_remove_whitelist",
            label="Remove vendor whitelist",
            session_id=session_id,
            scenario_id=S3_SCENARIO_ID,
            extra={"indicator": PRIMARY_ATTACKER_IP, "verify_payload": {"whitelist_present": False}},
        )

    if "request_ip_block" in applied:
        C.ensure_hil_action(
            kind="firewall_block",
            label=f"Request IP block for {PRIMARY_ATTACKER_IP}",
            session_id=session_id,
            scenario_id=S3_SCENARIO_ID,
            extra={"indicator": PRIMARY_ATTACKER_IP, "verify_payload": {"rule_present": True}},
        )

    if "create_security_incident" in applied:
        C.ensure_executed_action(
            kind="ticket_create",
            label="Create security incident",
            session_id=session_id,
            scenario_id=S3_SCENARIO_ID,
            extra={"ticket": {"id": "INC-S3-10042", "from_outcome": True}},
        )

    if "update_incident_ticket" in applied:
        C.ensure_executed_action(
            kind="ticket_update",
            label="Update incident with firewall-team evidence",
            session_id=session_id,
            scenario_id=S3_SCENARIO_ID,
            extra={"ticket": {"id": "INC-S3-10042", "comment": "Whitelist exception overlapping last_seen"}},
        )

    if "notify_soc_lead" in applied:
        C.ensure_executed_action(
            kind="notify",
            label="Notify SOC lead",
            session_id=session_id,
            scenario_id=S3_SCENARIO_ID,
            extra={"team": "soc-lead"},
        )

    if "verify_firewall_rule" in applied:
        C.ensure_executed_action(
            kind="firewall_verify_rule",
            label="Verify firewall rule",
            session_id=session_id,
            scenario_id=S3_SCENARIO_ID,
            extra={"indicator": PRIMARY_ATTACKER_IP, "read_only": True},
        )

    return awaiting


def build_s3_turn(*, session_id: str, turn: int, applied_follow_up_ids: list[str], pending_action_id: str | None = None, awaiting_external: bool = False):
    applied = list(applied_follow_up_ids)
    outcome = deepcopy(_base_outcome())
    state = deepcopy(_base_state())
    extra: list[dict[str, Any]] = []
    awaiting = _apply(applied, session_id, outcome, state, extra)
    workflow = _workflow_state(applied)
    source = [
        C.evidence(
            "ev-s3-prior",
            "splunk_mcp_fixture",
            "Compact prior investigation",
            [{"src": PRIMARY_ATTACKER_IP, "dest": "10.20.1.10", "deny_count": 1842, "allow_count": 3}],
            provenance="experience_center_fixture",
        ),
        *extra,
    ]
    return C.envelope(
        scenario_id=S3_SCENARIO_ID,
        family=S3_FAMILY,
        session_id=session_id,
        turn=turn,
        applied=applied,
        chips=list(S3_FOLLOWUPS),
        title=f"Coordinate firewall-block process for {PRIMARY_ATTACKER_IP}",
        assessment=(
            f"Malicious-pattern activity from {PRIMARY_ATTACKER_IP} is already in evidence. "
            "The company firewall-block process must be followed with the firewall team. "
            "A vendor whitelist, if present, is new evidence — not an automatic benign close."
        ),
        found="Investigation is ready to retrieve the firewall-block process and coordinate a team request.",
        outcome=outcome,
        evidence_state=state,
        source_evidence=source,
        actions=C.actions_for(session_id, S3_SCENARIO_ID),
        resources=["process knowledge", "email", "firewall change ticket", "simulated firewall control"],
        controls=["HIL for whitelist removal and IP block", "inbound email becomes evidence", "no live email connector"],
        pending_action_id=pending_action_id,
        awaiting_external=awaiting or awaiting_external or workflow == "AWAITING_FIREWALL_TEAM_CONFIRMATION",
        extra={
            "ec_workflow_state": workflow,
            "ec_workflow_path": list(_WORKFLOW),
            "ec_email": {
                "to": "firewall-team@internal",
                "subject": f"Block request for {PRIMARY_ATTACKER_IP}",
                "mandatory_fields": _PROCESS_FIELDS,
                "status": "awaiting_reply" if workflow == "AWAITING_FIREWALL_TEAM_CONFIRMATION" else workflow,
                "inbound": (
                    "This IP was manually whitelisted yesterday for vendor testing."
                    if "ingest_firewall_reply" in applied
                    else None
                ),
            },
            "ec_prior_investigation": {"indicator": PRIMARY_ATTACKER_IP, "independent_of_s1_session": True},
        },
        recommended=[
            "Retrieve the firewall-block process",
            "Send the mandatory-field request",
            "Treat any team reply as evidence and reassess",
            "Do not remove a whitelist or place a block without approval",
        ],
        important=[
            f"Indicator {PRIMARY_ATTACKER_IP} is independently seeded",
            "Process knowledge is scenario policy, not production SOAR",
        ],
        table=[
            {"Field": "Indicator", "Value": PRIMARY_ATTACKER_IP},
            {"Field": "Incident reference", "Value": INCIDENT_ID},
            {"Field": "Workflow", "Value": workflow},
        ],
        layer2_path=[
            "Understanding",
            "Process retrieved",
            "Request prepared",
            "Email sent",
            "Awaiting team",
            "Response received",
            "Evidence updated",
            "InvestigationOutcome",
        ],
    )


def s3_analyst_override(scenario_id: str, base: dict[str, Any]) -> dict[str, Any] | None:
    if scenario_id != S3_SCENARIO_ID:
        return None
    env = build_s3_turn(session_id="s3-override", turn=0, applied_follow_up_ids=[])
    return {**base, **(env.analyst or {})}


def build_s3_demo_scenarios() -> dict[str, Any]:
    return {
        S3_SCENARIO_ID: C.demo_scenario(
            scenario_id=S3_SCENARIO_ID,
            label="S3 · Firewall-team coordination",
            query=S3_QUERY,
            demo_order=3,
            family=S3_FAMILY,
            summary="Coordinate a firewall-block process with the firewall team. A whitelist reply is evidence, not a close.",
        )
    }
