"""S1 — a new external IP reaches the admin jump host."""

from __future__ import annotations

from app.demo import ec_environment as E
from app.demo.ec_agent.spec_engine import Action, Check, Email, ScenarioSpec

IP = E.EXTERNAL_IP

S1 = ScenarioSpec(
    scenario_id="s1_governed_splunk_investigation",
    family="s1_governed_splunk",
    label="S1 · New external IP on an admin system",
    question=(
        f"We're seeing repeated traffic from {IP}, an IP we haven't seen before, to one of our admin systems — "
        "including a few connections the firewall allowed. Check who this IP belongs to, what it has done over "
        "the last 30 days, and whether we need to monitor or block it."
    ),
    aliases=("new external IP on an admin system",),
    legacy_phrasings=(
        'We have seen a new IP 198.51.100.42. Check and verify over the last 30 days whether it is malicious, and what is the standard SOP to raise monitoring and block it if required.',
        'Find all communication involving suspicious IP 198.51.100.42 and identify affected systems.',
        'new IP 198.51.100.42',
        'verify if 198.51.100.42 is malicious',
    ),
    demo_order=1,
    plan_title="New external IP on an admin system — plan ready",
    plan_intro=(
        f"I'll find out who {IP} belongs to, what it did in the last 30 days, and what our SOP requires. "
        "Nothing runs until you approve."
    ),
    checks=(
        Check(
            id="who_owns_ip",
            title="Who owns this IP?",
            plan="Look the address up in our partner and supplier register.",
            tool="soc_kb",
            operation="soc_kb.retrieve · partner integration register",
            result=(
                f"Registered to our {E.PARTNER_NAME} partner ({E.PARTNER_ID}). The partner is approved to reach "
                f"the API gateway {E.API_GATEWAY} only — not admin systems."
            ),
            evidence=(
                f"Register entry {E.PARTNER_ID}: 3 registered outbound addresses including {IP}; approved destination {E.API_GATEWAY} "
                "(port 443), owner: Integration team",
            ),
        ),
        Check(
            id="last_30_days",
            title="What did it do in the last 30 days?",
            plan=f"Search firewall logs for {IP} from {{W30}}, and check it against our threat-intel lists.",
            tool="splunk_mcp",
            spl=(
                f'search index=netfw sourcetype=cisco:ftd src_ip="{IP}" earliest=-30d latest=now '
                '| stats count as events count(eval(action="allowed")) as allowed '
                'count(eval(action="blocked")) as blocked min(_time) as first_seen max(_time) as last_seen '
                "by dest_ip, dest_port, rule | head 100"
            ),
            result=(
                f"First seen {{D-12}}. 1,184 connections blocked and 3 allowed — all 3 to {E.JUMP_HOST} on "
                "port 443, let through by firewall rule ACL-PARTNER-0147. No threat-intel match."
            ),
            evidence=(
                "Allowed connections: {D-9 02:41}, {D-6 03:05}, {D-2 02:58} — each 2–6 seconds and 4–9 KB",
                f"Rule ACL-PARTNER-0147 lets the partner's addresses ({E.PARTNER_EGRESS_GROUP}) reach the whole admin subnet 10.20.1.0/24, "
                f"wider than the register allows ({E.API_GATEWAY} only)",
                "No traffic from this IP in the 30 days before {D-12}",
                f"Threat intel: no match in {E.THREAT_INTEL_SOURCE}. No match does not mean the IP is safe.",
                "A firewall 'allow' means the connection was permitted — not that anyone logged in",
            ),
            attention="ATTENTION",
        ),
        Check(
            id="sop",
            title="What does our SOP say?",
            plan="Retrieve the SOP for new external sources reaching critical systems.",
            tool="soc_kb",
            operation=f"soc_kb.retrieve · {E.SOP_NEW_EXTERNAL}",
            result=(
                f"{E.SOP_NEW_EXTERNAL}: open an incident, watch the source for 14 days and ask the owner to "
                "explain it. Block only if a logon is tied to the source or malice is confirmed."
            ),
            evidence=(f"{E.SOP_NEW_EXTERNAL} §3, approved version 2026.2",),
        ),
    ),
    added_check=Check(
        id="logons_during_sessions",
        title="Did anyone log in during those connections?",
        plan=f"Check sign-in logs on {E.JUMP_HOST} at the times of the 3 allowed connections.",
        tool="splunk_mcp",
        spl=(
            f'search index=wineventlog sourcetype=WinEventLog:Security host="{E.JUMP_HOST}" '
            "(EventCode=4624 OR EventCode=4625) earliest=-30d latest=now "
            "| stats count by user, src_ip, EventCode | head 100"
        ),
        result=(
            f"No logons from {IP}. The only logons at those times were {E.SVC_NETOPS} from our internal "
            "automation server 10.20.4.55."
        ),
        evidence=(
            f"{E.JUMP_HOST} records the client address on every logon; none came from {IP}",
            f"{E.SVC_NETOPS} logons at the same times came from 10.20.4.55 (scheduled network backup job)",
        ),
    ),
    added_after="last_30_days",
    added_when=("last_30_days",),
    conclusion_headline=(
        f"Not confirmed malicious. A partner IP reached our admin jump host through a firewall rule that is "
        f"wider than approved; no logon came from it."
    ),
    points=(
        "Confirmed: the connections were allowed by ACL-PARTNER-0147, which covers the whole admin subnet "
        f"instead of {E.API_GATEWAY} only.",
        f"Confirmed: no logon on {E.JUMP_HOST} came from {IP}.",
        "Inference: short connections with no logon look like probing or a misconfigured partner client — not access.",
    ),
    unresolved=(
        f"Why the partner's system connected to {E.JUMP_HOST} at all — only the partner can answer.",
        "Whether the partner's own host is compromised.",
    ),
    threat="Unconfirmed",
    asset_tier=0,
    evidence_state="unexplained_access",
    subject=f"{IP} → {E.JUMP_HOST}",
    decision=(
        "Proposed: open a {priority} incident, ask Detection Engineering to schedule a 14-day watch, and ask the "
        f"partner's owner and Network Operations about the connections. Blocking is not proposed — "
        f"{E.SOP_NEW_EXTERNAL}'s threshold is not met."
    ),
    actions=(
        Action(
            id="open_incident",
            title="Open a {priority} incident",
            proposal=f"ITSM incident at {{priority}} ({{priority_basis}}) with these findings attached.",
            tool="itsm",
            verb="incident",
            ticket_id=E.INCIDENT_S1,
            executed=f"Incident {E.INCIDENT_S1} opened ({{priority}})",
            verified="read back from ITSM: New, assigned to SOC Tier 2",
        ),
        Action(
            id="request_watch",
            title="Ask Detection Engineering to schedule a 14-day watch",
            proposal=(
                "No existing saved search covers this IP. Send the validated search below and ask for it to be "
                "scheduled as a 14-day alert. Splunk MCP can run searches but cannot schedule them."
            ),
            tool="itsm",
            verb="request",
            ticket_id=E.TASK_S1_DETECTION,
            ticket_summary="Schedule a 14-day watch: 3.110.47.92 to the admin subnet",
            assignment_group="Detection Engineering",
            spl=(
                f'search index=netfw sourcetype=cisco:ftd src_ip="{IP}" dest_ip="10.20.1.*" '
                "earliest=-14d latest=now "
                "| stats count as connections min(_time) as first_seen max(_time) as last_seen "
                "by src_ip, dest_ip, dest_port | head 100"
            ),
            executed=f"Request {E.TASK_S1_DETECTION} raised with Detection Engineering",
            verified="search run once through Splunk MCP returns the 3 known connections",
            status_after="REQUESTED",
        ),
        Action(
            id="ask_owner",
            title="Ask the partner's owner and Network Operations about the connections",
            proposal="Short email to the Integration team (owner of PRT-0147), copied to Network Operations.",
            tool="email",
            verb="email",
            email=Email(
                to="Integration team",
                mailbox="INCIDENT_OWNER",
                cc="Network Operations",
                cc_mailbox="NETWORK_TEAM",
                subject=f"Partner {E.PARTNER_ID} — connections to an admin host, please confirm",
                body=(
                    f"You're receiving this as owner of the {E.PARTNER_NAME} integration ({E.PARTNER_ID}).\n\n"
                    f"What we saw: {IP}, one of the partner's registered addresses, made 3 short connections to "
                    f"our admin jump host {E.JUMP_HOST} on {{D-9}}, {{D-6}} and {{D-2}}. Our firewall allowed them "
                    "because rule ACL-PARTNER-0147 covers the whole admin subnet. No one logged in from that "
                    "address.\n\n"
                    "Please:\n"
                    "1. Ask the partner why their system connected to our jump host.\n"
                    f"2. Network Operations — confirm whether ACL-PARTNER-0147 should be limited to {E.API_GATEWAY}.\n\n"
                    "{tickets}\n\n"
                    "SOC Tier 2"
                ),
            ),
            executed="Sent to the Integration team, cc Network Operations",
            status_after="AWAITING_REPLY",
        ),
    ),
    not_proposed=(f"Block {IP} — not proposed: no logon tied to the IP and malice not confirmed ({E.SOP_NEW_EXTERNAL})",),
    final_state="OPEN — MONITORING REQUESTED",
    final_headline="Incident open at {priority}. Watch requested and the partner asked to explain; IP not blocked.",
    pending=(
        "Detection Engineering to schedule the 14-day watch",
        "Integration team to explain the connections",
    ),
    next_triggers=(
        "Re-investigate if the watch alerts, a logon is tied to the IP, or the partner can't explain the "
        "traffic. Review on {D14}."
    ),
)
