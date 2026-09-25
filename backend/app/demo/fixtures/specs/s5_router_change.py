"""S5 — unplanned configuration change on a Cisco branch router."""

from __future__ import annotations

from app.demo import ec_environment as E
from app.demo.ec_agent.spec_engine import Action, Check, ScenarioSpec

R = E.BRANCH_ROUTER

S5 = ScenarioSpec(
    scenario_id="s5_cisco_hardening_remediation",
    family="s5_cisco_remediation",
    label="S5 · Router change and hardening policy",
    question=(
        f"Someone changed the configuration on our Cisco branch router {R} overnight. Check whether the change "
        "was authorised and whether our hardening policy requires us to fix anything."
    ),
    legacy_phrasings=(
        'Investigate the breach on Cisco router R-17 and check whether our hardening policy requires remediation.',
    ),
    demo_order=5,
    plan_title=f"Overnight change on {R} — plan ready",
    plan_intro=(
        f"I'll find out who changed {R}, whether an approved change covers it, and how the configuration now "
        "compares with our hardening standard. Nothing changes until you approve."
    ),
    checks=(
        Check(
            id="who_changed",
            title="Who made the change?",
            plan=f"Search login accounting and router logs for {R} overnight.",
            tool="splunk_mcp",
            spl=(
                f'search index=tacacs sourcetype=tacacs:accounting device="{R}" earliest=-24h latest=now '
                "| stats count values(cmd) as commands by user, src_ip | head 50"
            ),
            result=(
                f"{E.SVC_NETOPS} made it from {E.JUMP_HOST} at {{D0 03:16}}: added a local admin user 'netadmin2' "
                "and an SNMP community with write access."
            ),
            evidence=(
                f"Login accounting: {E.SVC_NETOPS} from {E.JUMP_HOST_IP}, 2 sessions {{D0 03:15}}–{{D0 03:21}}",
                "Router log: configuration changed by svc_netops at {D0 03:16}",
            ),
            attention="RISK",
        ),
        Check(
            id="approved_change",
            title="Is there an approved change for it?",
            plan=f"Look for change records covering {R} in this window.",
            tool="itsm",
            operation=f"itsm.lookup · change records for {R}",
            result=(
                f"No. No change covers {R} overnight, and {E.SVC_NETOPS}'s scheduled job only takes backups — it "
                "never changes configuration."
            ),
            evidence=("Last approved change on this router: {D-40}",),
        ),
        Check(
            id="hardening_gap",
            title="Does the configuration still meet our hardening standard?",
            plan=f"Compare the running config with the approved baseline and {E.STD_ROUTER_HARDENING}.",
            tool="agilus_mcp",
            operation=f"agilus.compare_config · {R} vs approved baseline",
            result=(
                f"No — 2 deviations from {E.STD_ROUTER_HARDENING}: a local user with full admin rights and an SNMP "
                "community with write access."
            ),
            evidence=(
                f"{E.STD_ROUTER_HARDENING} §4.1: no local admin users (TACACS+ only)",
                f"{E.STD_ROUTER_HARDENING} §6.2: SNMP v3 read-only; no v2c write communities",
            ),
            attention="ATTENTION",
        ),
    ),
    added_check=Check(
        id="account_activity",
        title=f"What else did {E.SVC_NETOPS} do?",
        plan=f"Search the last 72 hours of {E.SVC_NETOPS} activity across network devices.",
        tool="splunk_mcp",
        spl=(
            f'search index=tacacs sourcetype=tacacs:accounting user="{E.SVC_NETOPS}" earliest=-72h latest=now '
            "| stats count by device, src_ip | head 50"
        ),
        result=(
            f"Normal backup logins from 10.20.4.55 on 14 devices, plus tonight's 2 sessions from {E.JUMP_HOST} — "
            f"only {R} was changed."
        ),
        evidence=(
            f"{E.SVC_NETOPS} is also named in open incident {E.INCIDENT_S1} (login from an external IP)",
        ),
    ),
    added_after="who_changed",
    added_when=("who_changed",),
    conclusion_headline=(
        f"Unauthorised change: made with {E.SVC_NETOPS} outside any change window, and it weakens the router's "
        "hardening."
    ),
    points=(
        f"Confirmed: the change came from {E.SVC_NETOPS} on {E.JUMP_HOST}, not from its usual automation server.",
        "Confirmed: no approved change covers it and it breaks 2 hardening rules.",
        f"Inference: this is likely the same misuse of {E.SVC_NETOPS} already under investigation in {E.INCIDENT_S1}.",
    ),
    unresolved=("Whether the new local user or SNMP community has been used yet.",),
    threat="Suspected",
    asset_tier=1,
    evidence_state="unauthorized_change",
    subject=R,
    decision=(
        f"Proposed: open a {{priority}} incident, raise an emergency change, revert the two settings through Agilus and "
        f"verify, and ask IAM to reset {E.SVC_NETOPS}."
    ),
    actions=(
        Action(
            id="open_incident",
            title="Open a {priority} incident",
            proposal=f"ITSM incident at {{priority}} ({{priority_basis}}), linked to {E.INCIDENT_S1}.",
            tool="itsm",
            verb="incident",
            ticket_id=E.INCIDENT_S5,
            executed=f"Incident {E.INCIDENT_S5} opened ({{priority}}), linked to {E.INCIDENT_S1}",
            verified="read back from ITSM",
        ),
        Action(
            id="raise_change",
            title="Raise an emergency change to revert",
            proposal="ITSM emergency change: remove the local user and the SNMP community. Rollback: config backup.",
            tool="itsm",
            verb="change",
            ticket_id=E.CHANGE_S5_REVERT,
            ticket_summary="Remove unauthorised local user and SNMP community from RTR-BR-17",
            assignment_group="Network Operations",
            executed=f"Emergency change {E.CHANGE_S5_REVERT} approved",
        ),
        Action(
            id="revert_config",
            title=f"Revert the two settings on {R}",
            proposal=f"Agilus removes the local user and the SNMP community under the emergency change.",
            tool="agilus_mcp",
            verb="agilus_change",
            executed=f"Local user and SNMP community removed from {R}",
            verified=f"Agilus config compare: no deviations from {E.STD_ROUTER_HARDENING}",
        ),
        Action(
            id="reset_account",
            title=f"Ask IAM to reset {E.SVC_NETOPS}",
            proposal="ITSM request to IAM: reset the password and restrict logins to the automation server.",
            tool="itsm",
            verb="request",
            ticket_id=E.TASK_S5_IAM,
            ticket_summary="Reset svc_netops; restrict logins to 10.20.4.55",
            assignment_group="Identity & Access Management",
            executed=f"Request {E.TASK_S5_IAM} raised with IAM",
            status_after="REQUESTED",
        ),
    ),
    final_state="REMEDIATED AND VERIFIED — INVESTIGATION OPEN",
    final_headline=(
        f"{R} is back to standard and verified. {E.SVC_NETOPS} reset requested; the incident stays open to find how "
        "the account was misused."
    ),
    pending=(f"IAM to reset {E.SVC_NETOPS}",),
    next_triggers=f"Re-investigate if {E.SVC_NETOPS} logs in from anywhere other than 10.20.4.55.",
)
