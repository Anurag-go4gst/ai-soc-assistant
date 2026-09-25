"""R1 — what our SOP requires after a privileged login succeeds following failures (RAG)."""

from __future__ import annotations

from app.demo import ec_environment as E
from app.demo.ec_agent.spec_engine import Action, Check, Email, ScenarioSpec

R1 = ScenarioSpec(
    scenario_id="r1_rag_privileged_success_after_failure",
    family="r1_governed_rag",
    label="R1 · What does our SOP say? (knowledge base)",
    question=(
        "A privileged database admin account logged in successfully after repeated failed logins. What does our "
        "SOP require, and who do we need to escalate to?"
    ),
    legacy_phrasings=(
        'A privileged account logged in successfully after repeated failed logins. What does our SOP require, and what does our escalation matrix say?',
    ),
    demo_order=8,
    plan_title="Privileged login after failures — plan ready",
    plan_intro=(
        "I'll look up our SOP and escalation matrix, then check the login itself so the answer fits this case. "
        "Nothing runs until you approve."
    ),
    checks=(
        Check(
            id="sop",
            title="What does our SOP require?",
            plan=f"Retrieve the SOP for privileged login anomalies from the knowledge base.",
            tool="soc_kb",
            operation=f"soc_kb.retrieve · {E.SOP_PRIV_LOGON}",
            result=(
                f"{E.SOP_PRIV_LOGON} §4: (1) confirm with the account owner within 1 hour; (2) if not confirmed, "
                "the SOC lead decides whether to disable the account and review the session; (3) open an incident."
            ),
            evidence=(f"{E.SOP_PRIV_LOGON} §4, approved version 2026.2 — best match of 3 passages retrieved",),
        ),
        Check(
            id="escalation",
            title="Who do we escalate to?",
            plan="Retrieve the escalation matrix entry for finance systems.",
            tool="soc_kb",
            operation=f"soc_kb.retrieve · {E.ESCALATION_MATRIX}",
            result=(
                f"{E.ESCALATION_MATRIX}, finance systems: SOC Tier 2 lead and the DBA team manager. The CISO is "
                "informed only if data access is confirmed."
            ),
            evidence=(f"{E.ESCALATION_MATRIX} row 'Finance systems — privileged access'",),
        ),
        Check(
            id="the_login",
            title="What happened on the database server?",
            plan=f"Search logins for {E.ADM_DBA} on {E.FINANCE_DB} today.",
            tool="splunk_mcp",
            spl=(
                f'search index=wineventlog sourcetype=WinEventLog:Security host="{E.FINANCE_DB}" user="{E.ADM_DBA}" '
                "(EventCode=4624 OR EventCode=4625) earliest=-24h latest=now "
                "| stats count by EventCode, src_ip | head 50"
            ),
            result=(
                f"{E.ADM_DBA}: 14 failed logins in 6 minutes, then a success at {{D0 08:42}} — all from "
                "10.30.2.18, the DBA team's admin workstation."
            ),
            evidence=("No other source addresses; no logins from outside the admin network",),
        ),
    ),
    conclusion_headline=(
        "The SOP's first step applies: confirm with the account owner within 1 hour before anything else."
    ),
    points=(
        "The login came from the DBA team's own admin workstation, so a mistyped password is plausible — but only "
        "the owner can confirm it.",
        "Escalate to the SOC Tier 2 lead and the DBA team manager; no CISO notice unless data access is confirmed.",
    ),
    sources=(f"{E.SOP_PRIV_LOGON} §4", f"{E.ESCALATION_MATRIX} · finance systems"),
    unresolved=(f"Did the owner of {E.ADM_DBA} make these logins? This is the one detail the SOP needs first.",),
    threat="Unconfirmed",
    asset_tier=1,
    evidence_state="unexplained_access",
    subject=f"{E.ADM_DBA} on {E.FINANCE_DB}",
    decision=(
        "Proposed, as the SOP requires: open a {priority} incident and ask the account owner and the DBA team manager to "
        "confirm the login within 1 hour."
    ),
    actions=(
        Action(
            id="open_incident",
            title="Open a {priority} incident",
            proposal=f"ITSM incident at {{priority}} ({{priority_basis}}), citing {E.SOP_PRIV_LOGON} §4.",
            tool="itsm",
            verb="incident",
            ticket_id=E.INCIDENT_R1,
            executed=f"Incident {E.INCIDENT_R1} opened ({{priority}})",
            verified="read back from ITSM",
        ),
        Action(
            id="ask_owner",
            title="Ask the account owner to confirm the login",
            proposal="Short email to the owner of adm_dba02, copied to the DBA team manager and the SOC Tier 2 lead.",
            tool="email",
            verb="email",
            email=Email(
                to="adm_dba02 account owner",
                mailbox="INCIDENT_OWNER",
                cc="DBA team manager, SOC Tier 2 lead",
                cc_mailbox="SOC_TIER2",
                subject="Please confirm your admin login to FIN-DB-02",
                body=(
                    f"You're receiving this because {E.SOP_PRIV_LOGON} requires us to confirm privileged logins "
                    "that succeed after repeated failures.\n\n"
                    f"What we saw: {E.ADM_DBA} failed to log in 14 times in 6 minutes on {E.FINANCE_DB}, then "
                    "succeeded at {D0 08:42}, all from workstation 10.30.2.18.\n\n"
                    "Please reply within 1 hour: was this you? If not, tell us immediately.\n\n"
                    "{tickets}\n\n"
                    "SOC Tier 2"
                ),
            ),
            executed="Sent to the account owner, cc DBA team manager and SOC Tier 2 lead",
            status_after="AWAITING_REPLY",
        ),
    ),
    final_state="OPEN — AWAITING OWNER CONFIRMATION",
    final_headline="Incident open; owner asked to confirm the login within 1 hour, as the SOP requires.",
    pending=("Account owner's confirmation (1 hour from the email)",),
    next_triggers=(
        "If the owner doesn't confirm, the SOC Tier 2 lead decides on disabling the account (SOP step 2)."
    ),
)
