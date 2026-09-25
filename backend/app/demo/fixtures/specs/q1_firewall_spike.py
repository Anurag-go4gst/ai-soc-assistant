"""Q1 — firewall block spike plus a service-account login at the same time."""

from __future__ import annotations

from app.demo import ec_environment as E
from app.demo.ec_agent.spec_engine import Action, Check, Email, ScenarioSpec

IP = E.EXTERNAL_IP
S1, S2 = E.SCANNER_IPS

Q1 = ScenarioSpec(
    scenario_id="firewall_deny_coordinated_attack",
    family="firewall_deny_coordinated_attack",
    label="Q1 · Firewall block spike",
    question=(
        "We've had more than 5,000 firewall blocks in the last hour, and a service account logged in to one of "
        "our servers around the same time. Summarise the top offenders and tell me whether this looks coordinated."
    ),
    category="Coordinated Firewall Incident",
    keep_legacy_entry=True,
    demo_order=10,
    plan_title="Firewall block spike — plan ready",
    plan_intro=(
        "I'll rank the blocked sources, check whether they acted together, and find out which account logged in "
        "and from where. Nothing runs until you approve."
    ),
    checks=(
        Check(
            id="top_offenders",
            title="Who are the top offenders?",
            plan="Rank blocked sources and their targets on the edge firewall for the last hour.",
            tool="splunk_mcp",
            spl=(
                "search index=netfw sourcetype=cisco:ftd action=blocked earliest=-60m latest=now "
                "| stats count as blocked dc(dest_ip) as targets values(dest_port) as ports by src_ip "
                "| sort - blocked | head 20"
            ),
            result=(
                f"5,212 blocked connections from 7 sources. The top 3 — {IP}, {S1} and {S2} — make up 91%, "
                "sweeping 38 internal addresses on ports 22, 443 and 3389."
            ),
            evidence=(
                f"{IP}: 2,140 blocked · {S1}: 1,622 · {S2}: 988 · 4 others: 462",
                f"{IP} is the partner address already in incident {E.INCIDENT_S1}",
                f"Threat intel: {S1} and {S2} are on the Talos scanner list; {IP} has no match",
            ),
            attention="ATTENTION",
        ),
        Check(
            id="coordinated",
            title="Does it look coordinated?",
            plan="Compare timing and targets of the top sources.",
            tool="splunk_mcp",
            spl=(
                "search index=netfw sourcetype=cisco:ftd action=blocked earliest=-60m latest=now "
                f'(src_ip="{IP}" OR src_ip="{S1}" OR src_ip="{S2}") '
                "| stats min(_time) as first_seen dc(dest_ip) as targets by src_ip | head 20"
            ),
            result=(
                "Likely coordinated: the top 3 sources hit the same 38 addresses in the same order, starting "
                "within 4 minutes of each other."
            ),
            evidence=(
                "Start times: {D0 02:51}, {D0 02:53}, {D0 02:55}",
                "Inference: identical target lists and order point to one scanning tool or operator",
            ),
        ),
        Check(
            id="which_login",
            title="Which account logged in, and from where?",
            plan="Check sign-ins on servers in the same hour and the client address recorded for each.",
            tool="splunk_mcp",
            spl=(
                "search index=wineventlog sourcetype=WinEventLog:Security EventCode=4624 earliest=-60m latest=now "
                "| stats count by host, user, src_ip | head 50"
            ),
            result=(
                f"{E.SVC_NETOPS} logged in to {E.JUMP_HOST} at {{D0 03:12}} through the remote-desktop gateway, "
                f"which recorded the client as {IP}."
            ),
            evidence=(
                f"Confirmed: gateway record ties the {E.SVC_NETOPS} session to client address {IP}",
                f"{E.SVC_NETOPS} is an automation account; it should only log in from 10.20.4.55",
            ),
            attention="RISK",
        ),
    ),
    added_check=Check(
        id="after_login",
        title=f"What did {E.SVC_NETOPS} do after logging in?",
        plan="Follow the session on the jump host.",
        tool="splunk_mcp",
        spl=(
            f'search index=wineventlog sourcetype=WinEventLog:Security host="{E.JUMP_HOST}" user="{E.SVC_NETOPS}" '
            "earliest=-60m latest=now | stats count by EventCode, process_name | head 50"
        ),
        result=(
            f"One 9-minute session: opened the network device inventory share and made 2 SSH connections to "
            f"{E.BRANCH_ROUTER}. No outbound data transfer seen."
        ),
        evidence=(
            f"SSH to {E.BRANCH_ROUTER} at {{D0 03:15}} and {{D0 03:18}}",
            "Proxy and firewall logs show no large outbound transfer from the jump host",
        ),
    ),
    added_after="which_login",
    added_when=("which_login",),
    conclusion_headline=(
        f"Coordinated scanning, and one confirmed unauthorised login: {E.SVC_NETOPS} was used from the external "
        f"IP {IP}."
    ),
    points=(
        f"Confirmed: the gateway recorded {IP} as the client for {E.SVC_NETOPS}'s login — an automation account "
        "should never log in interactively from outside.",
        "Inference: three sources sweeping the same targets in step look like one coordinated scan.",
        f"This changes {E.INCIDENT_S1}: a logon is now tied to the IP, which is the block threshold in "
        f"{E.SOP_NEW_EXTERNAL}.",
    ),
    unresolved=(
        f"How the attacker obtained {E.SVC_NETOPS}'s password.",
        f"What was done on {E.BRANCH_ROUTER} during the 2 SSH sessions.",
    ),
    threat="Confirmed",
    asset_tier=0,
    evidence_state="confirmed_compromise",
    subject=f"{E.SVC_NETOPS} on {E.JUMP_HOST}",
    existing_incident=E.INCIDENT_S1,
    decision=(
        f"Proposed: raise {E.INCIDENT_S1} to P1 with this evidence, ask IAM to reset {E.SVC_NETOPS}, and ask the "
        f"SOC lead to approve a block under {E.SOP_FIREWALL_BLOCK}. Nothing is blocked automatically."
    ),
    actions=(
        Action(
            id="escalate_incident",
            title=f"Raise {E.INCIDENT_S1} to P1 and attach the evidence",
            proposal=f"Update the existing incident: P1 under {E.PRIORITY_POLICY} rule 1 (confirmed unauthorised login).",
            tool="itsm",
            verb="ticket_update",
            executed=f"{E.INCIDENT_S1} raised to P1",
            verified="read back from ITSM: P1, evidence attached",
        ),
        Action(
            id="reset_account",
            title=f"Ask IAM to reset {E.SVC_NETOPS} and block interactive logon",
            proposal="ITSM request to the IAM team. The SOC cannot change accounts directly.",
            tool="itsm",
            verb="request",
            ticket_id=E.TASK_Q1_IAM,
            executed=f"Request {E.TASK_Q1_IAM} raised with IAM",
            status_after="REQUESTED",
        ),
        Action(
            id="ask_block_approval",
            title="Ask the SOC lead to approve a block",
            proposal=f"Email the SOC lead with the evidence and ask for a block decision under {E.SOP_FIREWALL_BLOCK}.",
            tool="email",
            verb="email",
            email=Email(
                to="SOC Lead",
                mailbox="SOC_LEAD",
                subject=f"[{{incident}}] Block approval needed — {IP}",
                body=(
                    f"You're receiving this because {E.SOP_FIREWALL_BLOCK} needs your approval before a perimeter block.\n\n"
                    f"Evidence: at {{D0 03:12}} {E.SVC_NETOPS} logged in to {E.JUMP_HOST} through the remote-desktop "
                    f"gateway from {IP}, the partner address already in this incident. The same IP was one of 3 "
                    "sources scanning 38 of our addresses in the last hour. The session then connected to "
                    f"{E.BRANCH_ROUTER}.\n\n"
                    f"Requested: approve a block of {IP} on the edge firewall. IAM has been asked to reset "
                    f"{E.SVC_NETOPS}.\n\n"
                    "Incident: {incident} (now P1)\n\n"
                    "SOC Tier 2"
                ),
            ),
            executed="Sent to the SOC lead",
            status_after="AWAITING_REPLY",
        ),
    ),
    not_proposed=(f"Automatic block — {E.SOP_FIREWALL_BLOCK} requires SOC lead approval first",),
    final_state="ESCALATED — BLOCK APPROVAL REQUESTED",
    final_headline=f"{E.INCIDENT_S1} raised to P1; {E.SVC_NETOPS} reset requested; SOC lead asked to approve a block.",
    pending=("SOC lead's block decision", f"IAM to reset {E.SVC_NETOPS}"),
    next_triggers=f"Once the block is approved, run it through {E.SOP_FIREWALL_BLOCK} (S3).",
)
