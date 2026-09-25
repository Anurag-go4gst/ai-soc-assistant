"""S6 — returning to an earlier incident: more failed VPN logins from Germany."""

from __future__ import annotations

from app.demo import ec_environment as E
from app.demo.ec_agent.spec_engine import Action, Check, ScenarioSpec

INC = E.INCIDENT_S6_EXISTING

S6 = ScenarioSpec(
    scenario_id="s6_investigation_continuity",
    family="s6_continuity",
    label="S6 · Picking up an open incident",
    question=(
        "There were more failed VPN logins from Germany overnight, and we already have an incident open for "
        "yesterday's attempts. Is this the same activity, and does the incident need updating?"
    ),
    legacy_phrasings=(
        'Investigate failed privileged VPN logins from Germany yesterday.',
    ),
    demo_order=6,
    plan_title="Overnight VPN login failures — plan ready",
    plan_intro=(
        "I'll read what we concluded on the open incident, compare it with last night's attempts, and check "
        "whether the targeted account should use VPN at all. Nothing runs until you approve."
    ),
    checks=(
        Check(
            id="previous_incident",
            title="What did we conclude last time?",
            plan="Read the open incident for yesterday's attempts.",
            tool="itsm",
            operation=f"itsm.read · {INC}",
            result=(
                f"{INC}, opened {{D-1}}: 62 failed logins on VPN-GW-01 against adm_neteng01 from 2 German "
                "hosting addresses. No success. Status: monitoring."
            ),
            evidence=("Addresses 185.xx.xx.201 and 185.xx.xx.214 (same hosting provider)",),
        ),
        Check(
            id="overnight",
            title="What happened overnight?",
            plan="Search VPN logins for the last 12 hours.",
            tool="splunk_mcp",
            spl=(
                'search index=vpn sourcetype=cisco:asa action=failure earliest=-12h latest=now '
                "| stats count by user, src_ip, host | head 50"
            ),
            result=(
                f"41 failed logins between {{D0 00:20}} and {{D0 04:10}}, now against {E.SVC_DEPLOY}, from one of the "
                "same addresses plus a new one at the same provider. No successful login."
            ),
            evidence=(
                "Sources: 185.xx.xx.214 (seen yesterday) and 185.xx.xx.230 (new, same provider)",
                "Successful VPN logins from these addresses: none",
            ),
            attention="ATTENTION",
        ),
        Check(
            id="account_rules",
            title=f"Should {E.SVC_DEPLOY} use VPN at all?",
            plan="Check the service-account register and our SOP for privileged logins.",
            tool="soc_kb",
            operation=f"soc_kb.retrieve · service-account register, {E.SOP_PRIV_LOGON}",
            result=f"No. {E.SVC_DEPLOY} is the build-pipeline account and only logs in on BLD-01/02; VPN access isn't needed.",
            evidence=(f"{E.SOP_PRIV_LOGON} §6: service accounts must not have remote-access rights",),
        ),
    ),
    added_check=Check(
        id="deploy_elsewhere",
        title=f"Did {E.SVC_DEPLOY} log in anywhere unusual?",
        plan=f"Check {E.SVC_DEPLOY}'s successful logins in the last 7 days.",
        tool="splunk_mcp",
        spl=(
            f'search index=wineventlog sourcetype=WinEventLog:Security user="{E.SVC_DEPLOY}" EventCode=4624 '
            "earliest=-7d latest=now | stats count by host, src_ip | head 50"
        ),
        result=f"No. All {E.SVC_DEPLOY} logins were on BLD-01 and BLD-02 from the build network.",
        evidence=("1,318 logins, all from 10.40.2.0/24",),
    ),
    added_after="overnight",
    added_when=("overnight",),
    conclusion_headline=(
        f"Same activity, new target: the same hosting network is now guessing {E.SVC_DEPLOY}'s password. No login "
        "has succeeded."
    ),
    points=(
        "Confirmed: one address is the same as yesterday and the new one belongs to the same provider.",
        f"Confirmed: {E.SVC_DEPLOY} has no successful logins outside the build servers.",
        f"{E.SVC_DEPLOY} still has VPN rights it doesn't need — that is the gap to close.",
    ),
    unresolved=(f"How the attackers learned the {E.SVC_DEPLOY} account name.",),
    threat="Confirmed",
    asset_tier=1,
    evidence_state="attempted_misuse",
    subject=f"{E.SVC_DEPLOY} on the VPN gateways",
    existing_incident=INC,
    decision=(
        f"Proposed: add last night's evidence to {INC} and ask IAM to remove VPN access from {E.SVC_DEPLOY}. "
        "No new incident is needed."
    ),
    actions=(
        Action(
            id="update_incident",
            title=f"Add the overnight evidence to {INC}",
            proposal="Update the existing incident with the new account, the new address and the timeline.",
            tool="itsm",
            verb="ticket_update",
            executed=f"{INC} updated",
            verified="read back from ITSM",
        ),
        Action(
            id="remove_vpn",
            title=f"Ask IAM to remove VPN access from {E.SVC_DEPLOY}",
            proposal="ITSM request to IAM. The SOC cannot change account rights directly.",
            tool="itsm",
            verb="request",
            ticket_id=E.TASK_S6_IAM,
            assignment_group="Identity & Access Management",
            executed=f"Request {E.TASK_S6_IAM} raised with IAM",
            status_after="REQUESTED",
        ),
    ),
    final_state="OPEN — MONITORING",
    final_headline=f"{INC} updated with the overnight evidence; VPN access removal for {E.SVC_DEPLOY} requested.",
    pending=(f"IAM to remove VPN access from {E.SVC_DEPLOY}",),
    next_triggers="Re-investigate if any login from these addresses succeeds or a new account is targeted.",
)
