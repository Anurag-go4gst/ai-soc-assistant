"""SOP-aligned outbound email drafts for the Experience Center. /demo only.

Every draft goes through one composer so they read the same way:

* **Action first.** The first lines say what we need from the recipient and by when. Context
  follows. Recipients act on the first three lines and skim the rest.
* **Ticket block from the lifecycle.** The ticket line states the incident the approved plan opens,
  never "no ticket opened" while the same plan is creating one.
* **Recipient-appropriate footer.** The change-process note only goes to teams that own changes.
  Internal console controls (send approval, allowlists) are shown to the analyst in the UI, not
  printed into the recipient's email.
* **No demo vocabulary** ("fixture", "simulated", scenario ids) in anything a recipient reads.
"""

from __future__ import annotations

from typing import Any

from app.demo.ec_mcp_lifecycle_fixture import INCIDENT_ID, PRIMARY_ATTACKER_IP

_SIGN_OFF = (
    "Regards,\n"
    "SOC Operations\n"
    "Prepared by the AI SOC Assistant · reviewed and sent by the on-shift analyst"
)

# Teams that implement network/firewall changes get the change-process reminder.
_CHANGE_OWNING_TEAMS = frozenset({"FIREWALL_TEAM", "NETWORK_TEAM"})


def _footer(logical_recipient: str) -> str:
    lines = ["Reply to this email to acknowledge, or with any questions."]
    if logical_recipient in _CHANGE_OWNING_TEAMS:
        lines.insert(0, "Please implement any change through the standard change process and reply with the change reference.")
    return "---\n" + "\n".join(lines)


def _header(team: str, sop_ref: str, *, ask: str | None = None, by: str | None = None) -> str:
    opening = f"Dear {team},\n\n"
    if ask:
        opening += f"ACTION REQUESTED: {ask}" + (f" — by {by}" if by else "") + "\n\n"
    return opening + f"This request follows {sop_ref}."


def _section(title: str, lines: list[str]) -> str:
    if not lines:
        return ""
    return f"\n\n{title}\n" + "\n".join(f"• {line}" for line in lines)


def _ticket_status(
    applied: list[str],
    *,
    incident_id: str | None = None,
    ticket_executed: bool = False,
    ticket_draft_only: bool = False,
    closed: bool = False,
    updated: bool = False,
    planned: bool = False,
) -> str:
    """One ticket line derived from lifecycle state.

    ``planned`` means the approved plan opens ``incident_id`` in the same batch as this email, so
    the email references it instead of claiming no ticket exists.
    """
    ref = incident_id or "not assigned"
    if closed:
        return f"Incident {ref} is closed."
    if updated:
        return f"Incident {ref} is open and updated with the evidence in this email."
    if ticket_executed or "create_incident_ticket" in applied or "create_security_incident" in applied:
        if ticket_draft_only and not planned:
            return f"Incident {ref} is drafted and awaiting analyst confirmation."
        return f"Incident {ref} is open. Please quote it in your reply."
    if planned:
        return f"Incident {ref} is being opened as part of this approved response. Please quote it in your reply."
    if "generate_closure_summary" in applied or "generate_current_scope_summary" in applied:
        return f"A closure summary is prepared for {ref}; closure awaits SOC lead approval."
    return "No incident is open for this yet; this email is for coordination."


def _email_envelope(
    *,
    logical_recipient: str,
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
) -> dict[str, Any]:
    email: dict[str, Any] = {
        "to": to,
        "subject": subject,
        "body": body.strip() + "\n\n" + _footer(logical_recipient) + "\n\n" + _SIGN_OFF,
    }
    if cc:
        email["cc"] = cc
    return {"logical_recipient": logical_recipient, "email": email}


# ---------------------------------------------------------------------------------------- S1


def s1_firewall_team_email(
    *,
    applied: list[str],
    jump: str,
    host_b: str,
    host_c: str,
    account: str,
    ticket_executed: bool = False,
) -> dict[str, Any]:
    """SOC shift notice that the 14-day watch is live; firewall team copied for the exception question."""
    from app.demo.fixtures.s1.remediation_plan import S1_PLANNED_INCIDENT_ID

    ticket_line = _ticket_status(
        applied,
        incident_id=S1_PLANNED_INCIDENT_ID,
        ticket_executed=ticket_executed,
        planned=True,
    )
    body = _header(
        "SOC Lead (cc Firewall Team)",
        "the Firewall Change & SOC Coordination SOP §4.2 for newly observed external endpoints",
        ask=(
            f"Keep {PRIMARY_ATTACKER_IP} under the 14-day watch; firewall team, tell us if any exception "
            f"explains its allowed sessions to {jump}"
        ),
        by="end of next business day",
    )
    body += _section(
        "WHAT WE KNOW",
        [
            f"Indicator: {PRIMARY_ATTACKER_IP} — first seen in the last 30 days (prior 30 days empty)",
            "Identity: registered partner integration endpoint (asset inventory)",
            f"3 sessions allowed to jump host {jump} on ports 443/8443; 922 denied",
            f"Other internal targets contacted: {host_b}, {host_c} (all denied)",
            "Not in local threat intelligence; our IOC-based detection did not fire",
        ],
    )
    body += _section(
        "NOT YET KNOWN — YOUR INPUT HELPS",
        [
            f"Whether the 3 allowed sessions are expected partner traffic",
            f"Whether logons by {account} on {jump} came from this IP",
            "Whether a vendor or business exception explains the allowed traffic",
        ],
    )
    body += _section("TICKET STATUS", [ticket_line])
    body += _section(
        "REQUESTED ACTION",
        [
            "SOC lead: the 14-day watch is live — escalate to P1 if it fires",
            "Firewall team: confirm whether any active whitelist/exception covers this IP",
            "This is not a block request — the SOP block threshold is not met",
        ],
    )
    return _email_envelope(
        logical_recipient="SOC_LEAD",
        to="SOC_LEAD",
        cc="FIREWALL_TEAM",
        subject=f"[P2][{S1_PLANNED_INCIDENT_ID}] 14-day watch on {PRIMARY_ATTACKER_IP} — jump host {jump}",
        body=body,
    )


def s1_integration_owner_email(*, jump: str, account: str) -> dict[str, Any]:
    """Ask the owner of the registered partner endpoint to account for the allowed sessions."""
    from app.demo.fixtures.s1.remediation_plan import S1_PLANNED_INCIDENT_ID

    body = _header(
        "Partner Integration Owner",
        "the SOC SOP for newly observed external endpoints (owner confirmation step)",
        ask=f"Confirm whether 3 sessions from {PRIMARY_ATTACKER_IP} to jump host {jump} were expected",
        by="48 hours",
    )
    body += _section(
        "WHAT WE SAW",
        [
            f"{PRIMARY_ATTACKER_IP} is registered to your integration in our asset inventory",
            f"It first appeared in the last 30 days; 3 sessions were allowed to jump host {jump} (ports 443/8443)",
            f"Logons by {account} on {jump} in the same period are not yet tied to this IP",
        ],
    )
    body += _section(
        "PLEASE TELL US",
        [
            "Whether your integration is expected to reach the jump host at all",
            "Who operates the integration and from which systems",
            "Any change or vendor activity in the last 30 days that explains the sessions",
        ],
    )
    body += _section(
        "TICKET STATUS",
        [_ticket_status([], incident_id=S1_PLANNED_INCIDENT_ID, planned=True)],
    )
    return _email_envelope(
        logical_recipient="INCIDENT_OWNER",
        to="INTEGRATION_OWNER",
        cc="SOC_LEAD",
        subject=f"[P2][{S1_PLANNED_INCIDENT_ID}] Please confirm 3 sessions from {PRIMARY_ATTACKER_IP} to jump host {jump}",
        body=body,
    )


# ---------------------------------------------------------------------------------------- S2


def s2_appsec_email(*, applied: list[str]) -> dict[str, Any]:
    ticket_line = _ticket_status(applied, incident_id="AI-SEC-8841", planned=True)
    body = _header(
        "Application Security / AI Platform Team",
        "the AI Application Security SOP §3.1 (attempted abuse notifications)",
        ask="Review the assistant's guardrails against the two prompt patterns below and confirm hardening steps",
        by="5 working days",
    )
    body += _section(
        "WHAT HAPPENED",
        [
            "Prompt-injection (instruction-override) attempts against the customer-facing AI assistant",
            "The assistant requested export_customer_records; tool authorization denied it — no execution",
            "One actor: session sess-ai-8841, user guest-web-5521, source 203.0.113.77, all within 11 minutes",
            "Prompt patterns: 'ignore previous instructions', 'export all customer records'",
        ],
    )
    body += _section(
        "ALREADY DONE",
        [
            "Offending session blocked; user rate-limited for 24 hours",
            "Export connector credential rotated and scoped to approved export jobs",
            "Detection change DET-CHG-0412 raised to cover the observed patterns",
        ],
    )
    body += _section(
        "NOT CONFIRMED",
        [
            "Restricted customer-data exfiltration (DLP and datastore audit show none)",
            "Credential compromise or session hijack",
        ],
    )
    body += _section("TICKET STATUS", [ticket_line])
    body += _section(
        "REQUESTED ACTION",
        [
            "Review gateway prompt logs for the window in AI-SEC-8841",
            "Confirm guardrail changes and whether the assistant should keep export tools at all",
        ],
    )
    return _email_envelope(
        logical_recipient="APPSEC_TEAM",
        to="APPSEC_TEAM",
        subject="[P2][AI-SEC-8841] Blocked prompt-injection attempt on the customer AI assistant — guardrail review",
        body=body,
    )


# ---------------------------------------------------------------------------------------- S3


def s3_firewall_block_request_email(*, process_fields: dict[str, Any], applied: list[str]) -> dict[str, Any]:
    ip = str(process_fields.get("malicious_ip") or PRIMARY_ATTACKER_IP)
    incident_ref = str(process_fields.get("incident_reference") or INCIDENT_ID)
    ticket_line = _ticket_status(applied, incident_id=incident_ref, planned=True)
    body = _header(
        "Firewall Team",
        "the Enterprise Firewall-Block Process (mandatory fields per coordination SOP)",
        ask=f"Block {ip} at the perimeter for {process_fields.get('requested_block_duration') or '30 days'}",
        by="the next emergency change window",
    )
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
            "Process through the firewall change workflow / SOAR defined in the firewall-block SOP",
            "Reply with the change ticket ID and implementation window",
        ],
    )
    return _email_envelope(
        logical_recipient="FIREWALL_TEAM",
        to="FIREWALL_TEAM",
        cc="SOC_LEAD",
        subject=f"[P2][{incident_ref}] Firewall block request — {ip} (mandatory fields attached)",
        body=body,
    )


def s3_soc_lead_email(*, applied: list[str], process_fields: dict[str, Any] | None = None) -> dict[str, Any]:
    fields = process_fields or {}
    ip = str(fields.get("malicious_ip") or PRIMARY_ATTACKER_IP)
    incident_ref = str(fields.get("incident_reference") or INCIDENT_ID)
    ticket_line = _ticket_status(
        applied,
        incident_id=incident_ref,
        ticket_executed="create_security_incident" in applied,
        updated="update_incident_ticket" in applied,
        closed="generate_closure_summary" in applied,
    )
    inbound_note = (
        "Firewall team replied: the IP was manually whitelisted yesterday for vendor testing."
        if "ingest_firewall_reply" in applied
        else "No reply from the firewall team yet."
    )
    body = _header(
        "SOC Lead",
        "the Incident Escalation & Containment Approval SOP §1.4",
        ask=f"Approve or defer the perimeter block and whitelist removal for {ip}",
        by="today",
    )
    body += _section(
        "INVESTIGATION REFERENCE",
        [
            f"Indicator: {ip}",
            f"Incident reference: {incident_ref}",
            f"Severity: {fields.get('severity') or 'P2 High'}",
            f"Affected systems: {', '.join(fields.get('affected_systems') or [])}",
            "Evidence reused from the governed Splunk investigation; no new searches were needed",
        ],
    )
    body += _section(
        "CURRENT STATUS",
        [
            inbound_note,
            "The whitelist exception may explain the allowed sessions; activity during the exception window is not yet confirmed as malicious",
            "Whitelist removal and the IP block will not run without your approval",
        ],
    )
    body += _section("TICKET STATUS", [ticket_line])
    body += _section(
        "REQUESTED ACTION",
        [
            "Review the firewall-team reply and the whitelist conflict",
            "Approve or defer the block and whitelist removal under the containment policy",
            "Set closure criteria if remediation cannot proceed today",
        ],
    )
    return _email_envelope(
        logical_recipient="SOC_LEAD",
        to="SOC_LEAD",
        subject=f"[P2][{incident_ref}] Escalation — approval needed to block {ip}",
        body=body,
    )


def s3_reply_firewall_team_email(*, applied: list[str]) -> dict[str, Any]:
    body = _header(
        "Firewall Team",
        "the Firewall Change SOP §4.4 (follow-up on whitelist exceptions)",
        ask=f"Confirm the business owner and expiry of the whitelist exception for {PRIMARY_ATTACKER_IP}",
        by="end of day",
    )
    body += _section(
        "CONTEXT",
        [
            f"Re: block request for {PRIMARY_ATTACKER_IP}",
            "Your reply: the IP was manually whitelisted yesterday for vendor testing",
            "Our view: the exception may explain the allowed sessions; activity during the exception window is not yet confirmed as malicious",
        ],
    )
    body += _section(
        "TICKET STATUS",
        [_ticket_status(applied, incident_id=INCIDENT_ID, updated="update_incident_ticket" in applied)],
    )
    body += _section(
        "REQUESTED ACTION",
        [
            "Confirm the business owner and expiry of the exception",
            "Advise whether to remove the exception before or after the block",
            "Send an updated change reference if the scope changes",
        ],
    )
    return _email_envelope(
        logical_recipient="FIREWALL_TEAM",
        to="FIREWALL_TEAM",
        subject=f"Re: [{INCIDENT_ID}] Block request for {PRIMARY_ATTACKER_IP} — whitelist exception owner and expiry",
        body=body,
    )


# ---------------------------------------------------------------------------------------- S4


def _s4_incident_id() -> str:
    from app.demo.fixtures.s4.remediation_plan import S4_PLANNED_INCIDENT_ID

    return S4_PLANNED_INCIDENT_ID


def s4_wan_restriction_escalation_email(
    *,
    assets: list[str],
    advisory_id: str,
    anomalous: list[str] | None = None,
) -> dict[str, Any]:
    asset_line = ", ".join(assets)
    anomalous_line = ", ".join(anomalous or [])
    incident_id = _s4_incident_id()
    body = _header(
        "Network Operations Team",
        "the Zero-Day Advisory Response SOP §3 (temporary exposure containment)",
        ask=f"Turn off the WAN management listener on {len(assets)} VPN gateways",
        by="the emergency change window today",
    )
    body += _section(
        "WHY THIS IS REQUIRED",
        [
            f"Advisory {advisory_id}: the WAN management listener on affected EdgeGate firmware is exploitable",
            f"{len(assets)} internet-facing VPN gateways run a vulnerable build",
            "Turning the listener off closes the attack path until the emergency patch is installed",
            "No exploitation is confirmed — this is exposure-driven containment",
        ],
    )
    body += _section(
        "AFFECTED ASSETS",
        [line for line in [asset_line, f"Under compromise review (capture evidence before any reboot): {anomalous_line}" if anomalous_line else ""] if line],
    )
    body += _section("TICKET STATUS", [_ticket_status([], incident_id=incident_id, planned=True)])
    body += _section(
        "REQUESTED ACTION",
        [
            "Disable the WAN management listener; keep management on the management VRF only",
            "Confirm the rollback plan and maintenance notification list",
            "Reply with the change reference",
        ],
    )
    return _email_envelope(
        logical_recipient="NETWORK_TEAM",
        to="NETWORK_TEAM",
        cc="SOC_LEAD",
        subject=f"[P1][{incident_id}] Disable WAN management on {len(assets)} VPN gateways — {advisory_id}",
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
    incident_id = _s4_incident_id()
    body = _header(
        "Identity / IAM Operations",
        "the Zero-Day Advisory Response SOP §3.2 (step-up authentication)",
        ask="Require step-up MFA for all VPN sign-ins until the emergency patch is verified",
        by="within 24 hours (target 4 hours)",
    )
    body += _section(
        "WHY THIS IS REQUIRED",
        [
            f"Advisory {advisory_id}: internet-facing VPN is exposed while the patch change is prepared",
            f"Unusual privileged activity on {anomalous_line or 'two gateways'} (compromise not confirmed)",
            "If VPN credentials were harvested, step-up MFA stops their reuse",
            "Our identity connector is read-only, so this policy change has to come from your team",
        ],
    )
    body += _section(
        "SCOPE",
        [line for line in [
            f"VPN gateways: {asset_line}",
            f"Priority session review: {anomalous_line}" if anomalous_line else "",
            "Applies to active sessions and new sign-ins until the patch is verified",
        ] if line],
    )
    body += _section("TICKET STATUS", [_ticket_status([], incident_id=incident_id, planned=True)])
    body += _section(
        "REQUESTED ACTION",
        [
            "Open an emergency IAM change for step-up MFA / conditional access on the VPN IdP integration",
            "Confirm the user communication plan — staff will see re-authentication prompts",
            "Reply with the IAM change reference",
        ],
    )
    return _email_envelope(
        logical_recipient="IDENTITY_IAM_TEAM",
        to="IDENTITY_IAM_TEAM",
        subject=f"[P1][{incident_id}] Step-up MFA for VPN sign-ins — {advisory_id}",
        body=body,
    )


def s4_network_team_email(*, applied: list[str], advisory_id: str) -> dict[str, Any]:
    incident_id = _s4_incident_id()
    ticket_line = _ticket_status(
        applied,
        incident_id=incident_id,
        ticket_executed="create_emergency_incident" in applied,
        planned=True,
    )
    body = _header(
        "Network Operations and SOC",
        "the Zero-Day Advisory Response SOP §2 (exposure notifications)",
        ask="Note the exposure and the containment in progress; approve the emergency patch window (CHG-29173)",
        by="today",
    )
    body += _section(
        "ADVISORY REFERENCE",
        [
            f"Advisory ID: {advisory_id}",
            "No threat-specific SOAR playbook exists; the response adapts two emergency runbooks",
            "Scope: internet-facing VPN gateways",
        ],
    )
    body += _section(
        "CURRENT ASSESSMENT",
        [
            "4 of 12 internet-facing gateways run affected firmware — exposure PARTIAL",
            "Exploitation in our environment: NOT CONFIRMED",
            "VPN-GW-01 and VPN-GW-02 are under compromise review; evidence captured before patching",
            "A vulnerable gateway is not a compromised gateway",
        ],
    )
    body += _section("TICKET STATUS", [ticket_line])
    body += _section(
        "REQUESTED ACTION",
        [
            "Approve the emergency patch window for change CHG-29173",
            "Coordinate an executive briefing if the patch cannot land within SLA",
        ],
    )
    return _email_envelope(
        logical_recipient="NETWORK_TEAM",
        to="NETWORK_TEAM",
        cc="SOC_LEAD",
        subject=f"[P1][{incident_id}] VPN zero-day {advisory_id} — exposure, containment and patch window",
        body=body,
    )


# ---------------------------------------------------------------------------------------- S5


def s5_network_approval_email(*, device: str, applied: list[str]) -> dict[str, Any]:
    change_line = (
        "Change CHG-R17-15 is open. Please quote it in your reply."
        if "create_change_ticket" in applied
        else "Change CHG-R17-15 is being opened as part of this request."
    )
    body = _header(
        "Network Operations Team",
        "the Network Change Management SOP §5 (hardening remediation)",
        ask=f"Approve a maintenance window to upgrade Cisco router {device} from version 14 to 15",
        by="the next maintenance window",
    )
    body += _section(
        "CHANGE SUMMARY",
        [
            f"Device: Cisco router {device} (security evidence indicates compromise)",
            "Current version: 14 (read from the device)",
            "Policy: the hardening policy requires version 15 on compromised devices",
            "Rollback: previous image retained; rollback plan attached to the change",
            "Verification: the device must report version 15 after the change",
        ],
    )
    body += _section("CHANGE STATUS", [change_line])
    body += _section(
        "REQUESTED ACTION",
        [
            "Approve the maintenance window for a controlled upgrade",
            "Confirm rollback authority and the notification list",
            "Reply with the approval reference for CHG-R17-15",
        ],
    )
    return _email_envelope(
        logical_recipient="NETWORK_TEAM",
        to="NETWORK_TEAM",
        subject=f"[P2][CHG-R17-15] Approval needed — Cisco {device} security upgrade 14→15",
        body=body,
    )


# ---------------------------------------------------------------------------------------- S6


def s6_incident_owner_email(*, applied: list[str]) -> dict[str, Any]:
    if "update_incident_ticket" in applied:
        ticket_line = (
            "INC-VPN-0712 was CLOSED for the earlier administrator-VPN scope. It has now been UPDATED "
            "with the current-scope evidence (service accounts / build servers); reopening needs your confirmation."
        )
    else:
        ticket_line = (
            "INC-VPN-0712 is CLOSED (earlier administrator-VPN scope). It will not be reopened until you "
            "acknowledge the scope change."
        )
    body = _header(
        "Incident Owner",
        "the Incident Continuity SOP §1.3 (scope change notifications)",
        ask="Confirm whether INC-VPN-0712 should stay closed or be reopened under the new scope",
        by="end of next business day",
    )
    body += _section(
        "PRIOR INCIDENT",
        [
            "INC-VPN-0712 (closed): privileged VPN failures from Germany",
            "Scope then: administrator VPN geo-anomaly pattern",
        ],
    )
    body += _section(
        "CURRENT SCOPE",
        [
            "Now investigating: service accounts that touched build servers (svc_deploy)",
            "Administrator VPN evidence is out of scope for this thread",
            "The old ticket is reused only as historical context, not as the active incident",
        ],
    )
    body += _section("TICKET STATUS", [ticket_line])
    body += _section(
        "REQUESTED ACTION",
        [
            "Acknowledge the scope change and the updated evidence",
            "Confirm whether INC-VPN-0712 stays closed or is reopened",
            "Advise on any customer or business communication needed",
        ],
    )
    return _email_envelope(
        logical_recipient="INCIDENT_OWNER",
        to="INCIDENT_OWNER",
        subject="[INC-VPN-0712] Scope change — service accounts on build servers: reopen?",
        body=body,
    )


# ---------------------------------------------------------------------------------------- S7


def s7_ot_team_email(*, applied: list[str]) -> dict[str, Any]:
    body = _header(
        "OT Engineering Team",
        "the OT Security Coordination SOP §2.2 (telemetry vs asset record conflicts)",
        ask="Confirm whether vendor account ot_vendor_svc had authorized maintenance on OT-RTU-14",
        by="4 hours",
    )
    body += _section(
        "WHAT WE FOUND",
        [
            "Splunk shows unauthorized access to OT-RTU-14 (10.80.4.14)",
            "The CMDB lists OT-RTU-14 as retired — but OT inventory shows it active on cell 4",
            "It still answers on vlan ot-4 (MAC 00:1b:44:11:3a:b7) and the firewall allowed the traffic",
            "Source: engineering workstation OT-EWS-03 (10.80.1.23), account ot_vendor_svc",
            "No approved maintenance window covers this access",
        ],
    )
    body += _section(
        "TICKET STATUS",
        [_ticket_status(applied, incident_id="INC-OT-14", planned=True)],
    )
    body += _section(
        "REQUESTED ACTION",
        [
            "Confirm whether ot_vendor_svc was performing authorized maintenance",
            "Confirm OT-RTU-14's operational status so the CMDB can be corrected",
            "Do not power down or isolate the RTU; any path change will be agreed with you first",
        ],
    )
    return _email_envelope(
        logical_recipient="OT_TEAM",
        to="OT_TEAM",
        cc="SOC_LEAD",
        subject="[P2][INC-OT-14] OT-RTU-14 accessed by ot_vendor_svc — was this authorized maintenance?",
        body=body,
    )


# ---------------------------------------------------------------------------------------- R1


def r1_tier2_escalation_email(*, incident_id: str, account: str, host: str, source_ip: str) -> dict[str, Any]:
    """Escalation required by ESC-AUTH-001, carrying the SOP checklist (AUTH-003/AUTH-001)."""
    body = _header(
        "Tier 2 SOC Analyst",
        "the Auth Escalation Matrix ESC-AUTH-001 (privileged account, success after failures)",
        ask=f"Take the escalation for privileged account {account} on {host} and complete the SOP review",
        by="the end of this shift",
    )
    body += _section(
        "WHAT HAPPENED",
        [
            f"{account} (privileged) had 14 failed logins on {host}, then a successful login from {source_ip}",
            "This meets two escalation triggers in ESC-AUTH-001: privileged account and success after failures",
        ],
    )
    body += _section(
        "SOP REVIEW TO COMPLETE (AUTH-003, AUTH-001)",
        [
            "How critical the account is and what it can reach",
            f"Whether {source_ip} is a new source for this user",
            "What the session did after the successful login",
            "Correlate the failures and the success for the same user and source",
        ],
    )
    body += _section(
        "WORDING GUARDRAIL",
        [
            "Record it as 'successful login after failures observed' — not 'compromised account' or 'confirmed brute force' until the review supports it",
            "No account action (disable/reset) without your decision",
        ],
    )
    body += _section("TICKET STATUS", [_ticket_status([], incident_id=incident_id, planned=True)])
    return _email_envelope(
        logical_recipient="SOC_TIER2",
        to="SOC_TIER2",
        cc="SOC_LEAD",
        subject=f"[P2][{incident_id}] Escalation — privileged login after failures: {account} on {host}",
        body=body,
    )
