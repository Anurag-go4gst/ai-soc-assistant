"""Professional SOP-aligned outbound email drafts for Experience Center. /demo only."""

from __future__ import annotations

from typing import Any

from app.demo.ec_mcp_lifecycle_fixture import INCIDENT_ID, PRIMARY_ATTACKER_IP

_SIGN_OFF = (
    "Regards,\n"
    "AI SOC Assistant\n"
    "Security Operations Center\n"
    "Experience Center (governed demonstration — not a live production ticket unless confirmed below)"
)

_FOOTER = (
    "---\n"
    "Outbound coordination controls (SOC Coordination SOP):\n"
    "• Analyst review and explicit Send approval required before transmission\n"
    "• Allowlisted recipients only; edits to To/Subject/Body are logged with the action receipt\n"
    "• Firewall containment must be executed through SOAR / firewall change process — not direct from this console\n"
    "• Reply to this thread to acknowledge receipt or request clarification"
)


def _header(team: str, sop_ref: str) -> str:
    return (
        f"Dear {team},\n\n"
        f"Per {sop_ref}, I am sending you the investigation details below for your review, "
        "coordination, and action as appropriate."
    )


def _section(title: str, lines: list[str]) -> str:
    if not lines:
        return ""
    body = f"\n{title}\n" + "\n".join(f"• {line}" for line in lines)
    return body


def _ticket_status(
    applied: list[str],
    *,
    incident_id: str | None = None,
    ticket_executed: bool = False,
    ticket_draft_only: bool = False,
    closed: bool = False,
    updated: bool = False,
) -> str:
    ref = incident_id or "not assigned"
    if closed:
        return f"Incident ticket CLOSED (reference {ref}). Closure recorded in the simulated ITSM channel."
    if updated:
        return f"Incident ticket UPDATED (reference {ref}). New evidence attached per ticket-update SOP."
    if ticket_executed or "create_incident_ticket" in applied or "create_security_incident" in applied:
        if ticket_draft_only:
            return f"Incident ticket draft prepared — pending analyst confirmation (reference {ref})."
        return f"Incident ticket OPEN (reference {ref}). Status tracked in SOC workflow."
    if "generate_closure_summary" in applied or "generate_current_scope_summary" in applied:
        return (
            f"Closure / executive summary prepared for reference {ref}. "
            "Ticket closure pending SOC lead approval per incident-management SOP."
        )
    return "No incident ticket opened in this session yet. This email is for coordination only."


def _email_envelope(
    *,
    logical_recipient: str,
    to: str,
    subject: str,
    body: str,
) -> dict[str, Any]:
    return {
        "logical_recipient": logical_recipient,
        "email": {
            "to": to,
            "subject": subject,
            "body": body.strip() + "\n\n" + _FOOTER + "\n\n" + _SIGN_OFF,
        },
    }


def s1_firewall_team_email(
    *,
    applied: list[str],
    jump: str,
    host_b: str,
    host_c: str,
    account: str,
    ticket_executed: bool = False,
) -> dict[str, Any]:
    ticket_line = _ticket_status(
        applied,
        incident_id=INCIDENT_ID,
        ticket_executed=ticket_executed,
        ticket_draft_only="create_incident_ticket" in applied and not ticket_executed,
    )
    body = _header("Firewall / Security Team", "Firewall Change & SOC Coordination SOP §4.2 (outbound team requests)")
    body += _section(
        "INVESTIGATION REFERENCE",
        [
            f"Scenario: S1 governed suspicious-IP investigation",
            f"Indicator: {PRIMARY_ATTACKER_IP}",
            f"Primary jump host: {jump}",
            f"Additional internal targets: {host_b}, {host_c}",
            f"Service account observed: {account}",
            "Evidence window: governed 60-day coverage (two bounded 30-day Splunk searches)",
        ],
    )
    body += _section(
        "CONFIRMED FINDINGS",
        [
            "Coordinated probing and password-guessing pattern (MITRE T1110.001)",
            "Firewall allow/deny mix consistent with scanning against internal jump infrastructure",
            "Governed Splunk searches completed and validated",
        ],
    )
    body += _section(
        "UNCONFIRMED / REQUIRES YOUR INPUT",
        [
            "Account compromise",
            "Lateral movement",
            "Malicious process activity on endpoints",
            "Whether vendor or business exceptions explain observed allows",
        ],
    )
    body += _section(
        "TICKET STATUS",
        [ticket_line],
    )
    body += _section(
        "REQUESTED ACTION",
        [
            "Review the indicator and affected systems above",
            "If you concur, initiate block via SOAR playbook ip_block (not a direct production change from this console)",
            "Confirm whether any active whitelist/exception applies to this indicator",
            "Reply with change ticket reference or escalation path if block cannot proceed",
        ],
    )
    return _email_envelope(
        logical_recipient="FIREWALL_TEAM",
        to="FIREWALL_TEAM",
        subject=f"[SOC Action Required] Firewall review & block request — indicator {PRIMARY_ATTACKER_IP}",
        body=body,
    )


def s2_appsec_email(*, applied: list[str]) -> dict[str, Any]:
    ticket_line = _ticket_status(applied, incident_id="AI-SEC-8841", ticket_draft_only="create_ai_incident_ticket" in applied)
    body = _header("Application Security / AI Platform Team", "AI Application Security SOP §3.1 (attempted abuse notifications)")
    body += _section(
        "INVESTIGATION REFERENCE",
        [
            "Scenario: S2 AI application security — prompt injection and tool abuse",
            "Platform: customer-facing AI assistant gateway",
            "Session: Experience Center demonstration",
        ],
    )
    body += _section(
        "CONFIRMED FINDINGS",
        [
            "Prompt-injection / instruction-override attempt observed",
            "Unauthorized tool call export_customer_records attempted",
            "Tool authorization layer blocked execution (attempted/blocked — not confirmed breach)",
        ],
    )
    body += _section(
        "UNCONFIRMED",
        [
            "Successful unauthorized tool execution",
            "Restricted customer-data exfiltration",
            "Credential compromise or session hijack",
        ],
    )
    body += _section("TICKET STATUS", [ticket_line])
    body += _section(
        "REQUESTED ACTION",
        [
            "Review gateway and tool-call audit trails for the window cited in the incident package",
            "Confirm integration credential posture and whether disable/rotate is warranted",
            "Advise on additional containment per AI security runbook",
        ],
    )
    return _email_envelope(
        logical_recipient="APPSEC_TEAM",
        to="APPSEC_TEAM",
        subject="[SOC Coordination] Blocked AI tool-abuse attempt — review required (Experience Center)",
        body=body,
    )


def s3_firewall_block_request_email(*, process_fields: dict[str, Any], applied: list[str]) -> dict[str, Any]:
    ip = str(process_fields.get("malicious_ip") or PRIMARY_ATTACKER_IP)
    ticket_line = _ticket_status(applied, incident_id=str(process_fields.get("incident_reference") or INCIDENT_ID))
    body = _header("Firewall Team", "Enterprise Firewall-Block Process (mandatory fields per coordination SOP)")
    body += _section(
        "MANDATORY REQUEST FIELDS (per policy)",
        [
            f"Malicious IP: {process_fields.get('malicious_ip')}",
            f"Reason: {process_fields.get('reason')}",
            f"Incident reference: {process_fields.get('incident_reference')}",
            f"Severity: {process_fields.get('severity')}",
            f"Affected systems: {', '.join(process_fields.get('affected_systems') or [])}",
            f"Evidence summary: {process_fields.get('evidence_summary')}",
            f"First seen / Last seen: {process_fields.get('first_seen')} / {process_fields.get('last_seen')}",
            f"Requested block duration: {process_fields.get('requested_block_duration')}",
            f"Business impact: {process_fields.get('business_impact')}",
            f"Required approval: {process_fields.get('required_approval')}",
            f"Rollback plan: {process_fields.get('rollback')}",
        ],
    )
    body += _section("TICKET STATUS", [ticket_line])
    body += _section(
        "REQUESTED ACTION",
        [
            "Acknowledge receipt of this block request",
            "Process through firewall change workflow / SOAR as defined in the firewall-block SOP",
            "Reply with change ticket ID and expected implementation window",
        ],
    )
    return _email_envelope(
        logical_recipient="FIREWALL_TEAM",
        to="FIREWALL_TEAM",
        subject=f"[Firewall Block Request] Malicious IP {ip} — SOC coordination (mandatory fields attached)",
        body=body,
    )


def s3_soc_lead_email(*, applied: list[str], process_fields: dict[str, Any] | None = None) -> dict[str, Any]:
    fields = process_fields or {}
    ip = str(fields.get("malicious_ip") or PRIMARY_ATTACKER_IP)
    incident_ref = str(fields.get("incident_reference") or INCIDENT_ID)
    ticket_line = _ticket_status(
        applied,
        incident_id="INC-S3-10042" if "create_security_incident" in applied else incident_ref,
        ticket_executed="create_security_incident" in applied,
        updated="update_incident_ticket" in applied,
        closed="generate_closure_summary" in applied,
    )
    inbound_note = (
        "Firewall team inbound reply received: IP manually whitelisted yesterday for vendor testing."
        if "ingest_firewall_reply" in applied
        else "No inbound firewall-team reply in this session yet."
    )
    body = _header("SOC Lead", "Incident Escalation & Containment Approval SOP §1.4 (SOC lead notifications)")
    body += _section(
        "INVESTIGATION REFERENCE",
        [
            f"Scenario: S3 firewall-team coordination — indicator {ip}",
            f"Incident reference: {incident_ref}",
            f"Severity: {fields.get('severity') or 'P2 High'}",
            f"Affected systems: {', '.join(fields.get('affected_systems') or [])}",
            "SIEM evidence reused from prior governed investigation — no new Splunk SPL in this session",
        ],
    )
    body += _section(
        "CURRENT STATUS",
        [
            inbound_note,
            "Vendor whitelist exception may explain allows; malicious traffic during exception window remains unconfirmed",
            "Whitelist removal and IP block actions remain HIL-gated pending your direction",
        ],
    )
    body += _section("TICKET STATUS", [ticket_line])
    body += _section(
        "REQUESTED ACTION",
        [
            "Review firewall-team coordination evidence and whitelist conflict summary",
            "Approve or defer perimeter block / whitelist removal per containment policy",
            "Advise on closure criteria if remediation cannot proceed immediately",
        ],
    )
    return _email_envelope(
        logical_recipient="SOC_LEAD",
        to="SOC_LEAD",
        subject=f"[SOC Escalation] Firewall coordination — approval requested for {ip}",
        body=body,
    )


def s3_reply_firewall_team_email(*, applied: list[str]) -> dict[str, Any]:
    body = _header("Firewall Team", "Firewall Change SOP §4.4 (follow-up on whitelist exception)")
    body += _section(
        "CONTEXT",
        [
            f"Re: block request for indicator {PRIMARY_ATTACKER_IP}",
            "Inbound reply received: IP was manually whitelisted yesterday for vendor testing",
            "SOC reassessment: exception may explain allows; malicious traffic during exception window remains unconfirmed",
        ],
    )
    body += _section(
        "TICKET STATUS",
        [
            _ticket_status(applied, incident_id="INC-S3-10042", updated="update_incident_ticket" in applied),
        ],
    )
    body += _section(
        "REQUESTED ACTION",
        [
            "Confirm business owner and expiry for the whitelist exception",
            "Advise whether exception should be removed before or after block implementation",
            "Provide updated change ticket reference if scope changes",
        ],
    )
    return _email_envelope(
        logical_recipient="FIREWALL_TEAM",
        to="FIREWALL_TEAM",
        subject=f"Re: Block request for {PRIMARY_ATTACKER_IP} — whitelist exception follow-up",
        body=body,
    )


def s4_wan_restriction_escalation_email(
    *,
    assets: list[str],
    advisory_id: str,
    anomalous: list[str] | None = None,
) -> dict[str, Any]:
    asset_line = ", ".join(assets)
    anomalous_line = ", ".join(anomalous or [])
    body = _header("Network Operations Team", "Zero-Day Advisory Response SOP §3 (temporary exposure containment)")
    body += _section(
        "WHY THIS IS REQUIRED",
        [
            f"Advisory {advisory_id} — WAN management listener exposed on affected EdgeGate firmware",
            f"{len(assets)} internet-facing VPN gateways confirmed on vulnerable builds",
            "Compensating control requested: disable WAN management listener; restrict control plane to management VRF",
            "Splunk hunt returned 0 advisory-specific IOC hits — containment is exposure-driven, not compromise-confirmed",
        ],
    )
    body += _section(
        "AFFECTED ASSETS",
        [line for line in [asset_line, f"Deeper auth review requested on: {anomalous_line}" if anomalous_line else ""] if line],
    )
    body += _section(
        "REQUESTED ACTION",
        [
            "Schedule emergency change window to disable WAN management listener on listed gateways",
            "Confirm rollback plan and maintenance notification list",
            "Reply with change reference — AI SOC will link to incident package",
        ],
    )
    return _email_envelope(
        logical_recipient="NETWORK_TEAM",
        to="NETWORK_TEAM",
        subject=f"[Urgent] WAN management restriction — {advisory_id} ({len(assets)} gateways)",
        body=body,
    )


def s4_identity_mfa_escalation_email(
    *,
    assets: list[str],
    advisory_id: str,
    anomalous: list[str] | None = None,
) -> dict[str, Any]:
    asset_line = ", ".join(assets)
    anomalous_line = ", ".join(anomalous or [])
    body = _header("Identity / IAM Operations", "Zero-Day Advisory Response SOP §3.2 (step-up authentication)")
    body += _section(
        "WHY THIS IS REQUIRED",
        [
            f"Advisory {advisory_id} — elevated risk on internet-facing VPN while patch change is prepared",
            "Investigation flagged privileged auth anomalies on two gateways (not compromise-confirmed)",
            "Step-up MFA cannot be applied via Identity MCP in this tenant (read-only connector)",
            "Emergency conditional-access policy required before or during WAN restriction change window",
        ],
    )
    body += _section(
        "SCOPE",
        [line for line in [
            f"VPN gateways: {asset_line}",
            f"Priority session review: {anomalous_line}" if anomalous_line else "",
            "Applies to active sessions and new authentications until patch verified",
        ] if line],
    )
    body += _section(
        "REQUESTED ACTION",
        [
            "Open IAM emergency change for step-up MFA / conditional access on VPN IdP integration",
            "Target SLA: policy published within 4–24 hours (not instant)",
            "Confirm user re-authentication comms plan — expect session prompts",
            "Reply with IAM change ticket reference for SOC incident linkage",
        ],
    )
    return _email_envelope(
        logical_recipient="IDENTITY_IAM_TEAM",
        to="IDENTITY_IAM_TEAM",
        subject=f"[IAM Change] Step-up MFA for VPN — {advisory_id}",
        body=body,
    )


def s4_network_team_email(*, applied: list[str], advisory_id: str) -> dict[str, Any]:
    ticket_line = _ticket_status(
        applied,
        incident_id="INC-ZD-001",
        ticket_executed="create_emergency_incident" in applied,
    )
    body = _header("Network Operations / SOC", "Zero-Day Advisory Response SOP §2 (exposure assessment notifications)")
    body += _section(
        "ADVISORY REFERENCE",
        [
            f"Advisory ID: {advisory_id}",
            "Threat-specific SOAR playbook: NOT AVAILABLE (scenario condition — not an operational error)",
            "Scope: internet-facing VPN gateways",
        ],
    )
    body += _section(
        "CURRENT ASSESSMENT",
        [
            "4 of 12 internet-facing gateways run affected firmware — exposure PARTIAL",
            "Exploitation in environment: NOT CONFIRMED",
            "VPN-GW-01 and VPN-GW-02 flagged for deeper compromise review",
            "Vulnerable asset ≠ compromised asset per advisory handling policy",
        ],
    )
    body += _section("TICKET STATUS", [ticket_line])
    body += _section(
        "REQUESTED ACTION",
        [
            "Review exposure summary and version inventory attached to the incident package",
            "Confirm emergency change path if temporary hardening controls are approved",
            "Coordinate executive briefing if exposure cannot be remediated within SLA",
        ],
    )
    return _email_envelope(
        logical_recipient="NETWORK_TEAM",
        to="NETWORK_TEAM",
        subject=f"[Zero-Day Coordination] Exposure review {advisory_id} — network team action",
        body=body,
    )


def s5_network_approval_email(*, device: str, applied: list[str]) -> dict[str, Any]:
    ticket_line = _ticket_status(applied, incident_id="CHG-R17-15", ticket_executed="create_change_ticket" in applied)
    body = _header("Network Operations Team", "Network Change Management SOP §5 (Cisco hardening remediation)")
    body += _section(
        "CHANGE SUMMARY",
        [
            f"Device: Cisco router {device}",
            "Current version: 14 (fixture replay via cisco.get_version)",
            "Policy requirement: upgrade to version 15 per EC hardening policy",
            "Implementation: simulated cisco.upgrade with rollback plan documented",
            "Verification: cisco.get_version expected to read 15 post-change",
        ],
    )
    body += _section("TICKET STATUS", [ticket_line])
    body += _section(
        "REQUESTED ACTION",
        [
            "Approve maintenance window for controlled upgrade",
            "Confirm rollback authority and notification list",
            "Reply with approval reference for change ticket CHG-R17-15",
        ],
    )
    return _email_envelope(
        logical_recipient="NETWORK_TEAM",
        to="NETWORK_TEAM",
        subject=f"[Change Approval] Cisco {device} security upgrade 14→15 — SOC request",
        body=body,
    )


def s6_incident_owner_email(*, applied: list[str]) -> dict[str, Any]:
    if "update_incident_ticket" in applied:
        ticket_line = (
            "Incident ticket INC-VPN-0712 was CLOSED for the prior administrator-VPN scope. "
            "Per incident-continuity SOP, the ticket has been UPDATED with current-scope evidence "
            "(service accounts / build servers). Closure status is pending your confirmation."
        )
    else:
        ticket_line = (
            "Incident ticket INC-VPN-0712 is CLOSED (prior administrator VPN scope). "
            "No reopen until scope change is acknowledged by incident owner."
        )
    body = _header("Incident Owner", "Incident Continuity SOP §1.3 (scope change notifications)")
    body += _section(
        "PRIOR INCIDENT CONTEXT",
        [
            "Historical ticket INC-VPN-0712 (closed): privileged VPN failures from Germany",
            "Prior scope: administrator VPN geo-anomaly pattern",
        ],
    )
    body += _section(
        "CURRENT SCOPE UPDATE",
        [
            "Current investigation scope: service accounts that touched build servers (svc_deploy)",
            "Administrator VPN evidence explicitly OUT OF SCOPE for this thread",
            "Prior ticket remains REUSABLE only as historical geo/VPN context — not as active incident",
        ],
    )
    body += _section("TICKET STATUS", [ticket_line])
    body += _section(
        "REQUESTED ACTION",
        [
            "Acknowledge scope change and updated evidence package",
            "Confirm whether INC-VPN-0712 should remain closed or be reopened under new scope",
            "Advise incident owner on any customer or business communication requirements",
        ],
    )
    return _email_envelope(
        logical_recipient="INCIDENT_OWNER",
        to="INCIDENT_OWNER",
        subject="INC-VPN-0712 — current-scope evidence update (service accounts / build servers)",
        body=body,
    )


def s7_ot_team_email(*, applied: list[str]) -> dict[str, Any]:
    body = _header("OT Engineering Team", "OT Security Coordination SOP §2.2 (telemetry vs asset record conflicts)")
    body += _section(
        "CONFLICT SUMMARY",
        [
            "Splunk unauthorized-access telemetry observed for OT asset OT-RTU-14",
            "CMDB record: device marked RETIRED / decommissioned",
            "Disposition: unresolved conflict — do not force incident without OT confirmation",
        ],
    )
    body += _section(
        "EVIDENCE OBTAINED",
        [
            "Splunk OT auth events in investigation window",
            "CMDB retirement timestamp and owner",
            "Firewall east-west allow to 10.80.4.14 in same window (if checked)",
        ],
    )
    body += _section(
        "TICKET STATUS",
        [_ticket_status(applied, incident_id="pending OT confirmation")],
    )
    body += _section(
        "REQUESTED ACTION",
        [
            "Confirm whether OT-RTU-14 is active, relocated, or decommissioned",
            "Clarify whether CMDB retirement is stale or identity was recycled",
            "Reply with operational status so SOC can close or escalate per OT incident SOP",
        ],
    )
    return _email_envelope(
        logical_recipient="OT_TEAM",
        to="OT_TEAM",
        subject="[OT Coordination] OT-RTU-14 — Splunk activity vs CMDB retirement conflict",
        body=body,
    )
