"""S4 — critical zero-day on the VPN gateways, no detection or playbook yet."""

from __future__ import annotations

from app.demo import ec_environment as E
from app.demo.ec_agent.spec_engine import Action, Check, Email, ScenarioSpec

GW1, GW2, GW3, GW4 = E.VPN_GATEWAYS
ADVISORY = "VULN-2026-0917"

S4 = ScenarioSpec(
    scenario_id="s4_zero_day_no_playbook",
    family="s4_zero_day",
    label="S4 · VPN zero-day, no playbook",
    question=(
        "A critical zero-day has been announced for our VPN gateways and we don't have a detection rule or "
        "playbook for it yet. Find out whether we are exposed and what we should do right now."
    ),
    legacy_phrasings=(
        'A critical zero-day affects our internet-facing VPN gateways. We have no detection rule or SOAR playbook yet for VPN detection. Determine whether we are exposed and what immediate controls we should apply.',
    ),
    demo_order=4,
    plan_title="VPN gateway zero-day — plan ready",
    plan_intro=(
        f"I'll check which gateways run an affected version, look for signs of exploitation, and pull our SOP "
        "for critical vulnerabilities. Nothing runs until you approve."
    ),
    checks=(
        Check(
            id="affected_versions",
            title="Which VPN gateways are affected?",
            plan=f"Read software version and enabled features on {GW1}–{GW4}.",
            tool="agilus_mcp",
            operation="agilus.read_device_version · VPN-GW-01..04",
            result=(
                f"2 of 4 are affected: {GW1} and {GW2} run 9.18.3 with the vulnerable web feature switched on. "
                f"{GW3} and {GW4} already run the fixed 9.18.4."
            ),
            evidence=(
                f"Vendor advisory tracked internally as {ADVISORY}: fixed in 9.18.4, workaround = disable the web feature",
                f"{GW1}, {GW2}: internet-facing, primary data centre",
            ),
            attention="ATTENTION",
        ),
        Check(
            id="exploitation_signs",
            title="Any sign of exploitation in the last 14 days?",
            plan="Search VPN gateway logs for requests to the vulnerable web path.",
            tool="splunk_mcp",
            spl=(
                'search index=vpn sourcetype=cisco:asa (host="VPN-GW-01" OR host="VPN-GW-02") '
                'uri_path="/+CSCOE+/*" earliest=-14d latest=now '
                "| stats count min(_time) as first_seen by host, src_ip | head 50"
            ),
            result=(
                f"{GW2} received 11 requests to the vulnerable path from 2 outside addresses on {{D-3}}. "
                f"{GW1}: none."
            ),
            evidence=(
                "Sources 103.xx.xx.17 and 103.xx.xx.29 — both on the Talos scanner list",
                "Web logs record the path but not the request body",
            ),
            attention="ATTENTION",
        ),
        Check(
            id="vuln_sop",
            title="What does our SOP say?",
            plan="Retrieve the SOP for critical vulnerabilities on internet-facing systems.",
            tool="soc_kb",
            operation=f"soc_kb.retrieve · {E.SOP_CRITICAL_VULN}",
            result=(
                f"{E.SOP_CRITICAL_VULN}: check for compromise first, apply the vendor workaround within 24 hours "
                "under an emergency change, patch within 7 days."
            ),
            evidence=(f"{E.SOP_CRITICAL_VULN} §2, approved version 2026.1",),
        ),
    ),
    added_check=Check(
        id="after_requests",
        title=f"Did anything follow those requests on {GW2}?",
        plan=f"Check {GW2} for config changes and admin sessions since the requests.",
        tool="agilus_mcp",
        operation=f"agilus.read_device_config · {GW2} (config history, admin sessions)",
        result=(
            "No config changes since {D-21} and no admin sessions after the requests. We can't tell whether the "
            "requests carried an exploit."
        ),
        evidence=(
            "Running config matches the last approved backup",
            "Admin sessions after {D-3}: none",
        ),
    ),
    added_after="exploitation_signs",
    added_when=("exploitation_signs",),
    conclusion_headline=(
        f"Exposed on 2 gateways and probed on one. No sign of compromise, but an exploit attempt can't be ruled out."
    ),
    points=(
        f"Confirmed: {GW1} and {GW2} run an affected version with the vulnerable feature on.",
        f"Confirmed: nothing changed on {GW2} after the requests.",
        "Inference: the requests look like scanning for this vulnerability; there is no evidence they succeeded.",
    ),
    unresolved=("Whether the 11 requests carried an exploit — request bodies aren't logged.",),
    threat="Suspected",
    asset_tier=1,
    evidence_state="exposure",
    subject=f"{GW1}, {GW2}",
    decision=(
        "Proposed: open a {priority} incident, raise an emergency change, disable the vulnerable feature on the 2 gateways "
        "now through Agilus, schedule the patch, and request a detection for the vulnerable path."
    ),
    actions=(
        Action(
            id="open_incident",
            title="Open a {priority} incident",
            proposal=f"ITSM incident at {{priority}} ({{priority_basis}}).",
            tool="itsm",
            verb="incident",
            ticket_id=E.INCIDENT_S4,
            executed=f"Incident {E.INCIDENT_S4} opened ({{priority}})",
            verified="read back from ITSM",
        ),
        Action(
            id="emergency_change",
            title="Raise an emergency change for the workaround and patch",
            proposal=(
                f"ITSM emergency change: disable the web feature on {GW1}/{GW2} now; upgrade both to 9.18.4 in the "
                "next change window. Rollback: re-enable the feature."
            ),
            tool="itsm",
            verb="change",
            ticket_id=E.CHANGE_S4_WORKAROUND,
            ticket_summary="Disable vulnerable web feature on VPN-GW-01/02; patch to 9.18.4",
            assignment_group="Network Operations",
            executed=f"Emergency change {E.CHANGE_S4_WORKAROUND} approved; patch window booked for {{D2 01:00}}",
            status_after="SCHEDULED",
        ),
        Action(
            id="apply_workaround",
            title="Disable the vulnerable feature on both gateways",
            proposal=f"Agilus applies the vendor workaround to {GW1} and {GW2} under the emergency change.",
            tool="agilus_mcp",
            verb="agilus_change",
            executed=f"Web feature disabled on {GW1} and {GW2}",
            verified="Agilus config read confirms the feature is off on both",
        ),
        Action(
            id="request_detection",
            title="Ask Detection Engineering for a detection",
            proposal="ITSM request with the validated search below, to run as an alert until the patch is verified.",
            tool="itsm",
            verb="request",
            ticket_id=E.TASK_S4_DETECTION,
            ticket_summary="Detection for requests to the vulnerable VPN web path",
            assignment_group="Detection Engineering",
            spl=(
                'search index=vpn sourcetype=cisco:asa uri_path="/+CSCOE+/*" earliest=-24h latest=now '
                "| stats count by host, src_ip, uri_path | head 100"
            ),
            executed=f"Request {E.TASK_S4_DETECTION} raised with Detection Engineering",
            status_after="REQUESTED",
        ),
        Action(
            id="notify",
            title="Tell Network Operations and the remote-access owner",
            proposal="Short email with the exposure, the workaround and the patch window.",
            tool="email",
            verb="email",
            email=Email(
                to="Network Operations",
                mailbox="NETWORK_TEAM",
                cc="Remote access service owner",
                subject=f"[{{incident}}] VPN zero-day {ADVISORY} — workaround on VPN-GW-01/02",
                body=(
                    "You're receiving this because two VPN gateways you run are exposed to a critical vulnerability.\n\n"
                    f"What we found: {GW1} and {GW2} run 9.18.3 with the vulnerable web feature on. {GW2} was "
                    "probed on {D-3}; no compromise found. The feature is being disabled under change "
                    "{ticket:emergency_change}; users connect through the standard client and are not affected.\n\n"
                    "Please confirm the patch window ({D2 01:00}) and check remote access after the workaround.\n\n"
                    "{tickets}\n\n"
                    "SOC Tier 2"
                ),
            ),
            executed="Sent to Network Operations, cc remote access owner",
        ),
    ),
    final_state="OPEN — WORKAROUND APPLIED, PATCH SCHEDULED",
    final_headline=f"Vulnerable feature disabled and verified on {GW1}/{GW2}; patch scheduled; detection requested.",
    pending=("Patch to 9.18.4 in the change window ({D2 01:00})", "Detection Engineering to deploy the detection"),
    next_triggers=f"Re-investigate if the detection fires or {GW2} shows admin activity. Close after the patch is verified.",
)
