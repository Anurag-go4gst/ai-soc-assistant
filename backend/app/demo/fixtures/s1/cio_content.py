"""S1 CIO layer — why each step exists, and what the executive needs to decide."""

from __future__ import annotations

from app.demo.ec_agent.cio_content import CioContent, register_cio_content
from app.demo.fixtures.s1.agent_config import S1_SCENARIO_ID

S1_CIO_CONTENT = CioContent(
    scenario_id=S1_SCENARIO_ID,
    opening_narrative=(
        "My plan for 198.51.100.42: six checks across Splunk firewall logs, the asset inventory "
        "and the SOC knowledge base — who owns this IP, what it reached in the last 30 days, "
        "whether it is new or known-bad, whether our detections would have caught it, and what "
        "our SOP requires. Nothing runs until you approve. If any traffic was allowed through, "
        "I will add a step to follow those sessions."
    ),
    step_summary={
        "mcp_identity": "Look up the IP in the asset inventory and SOC-KB to find its owner and expected role.",
        "requested_30d": "Governed Splunk search of firewall traffic to and from the IP for the 30 days you asked about.",
        "threat_intel": "Check the IP against our local threat-intelligence and IOC lists.",
        "retrieve_sop": "Retrieve the enterprise SOP for newly observed external endpoints.",
        "privileged_accounts": "Optional: pull privileged-account context for svc_jump_ops from IAM.",
        "endpoint_activity": "Optional: review process and session activity on the jump host from EDR.",
        "previous_incidents": "Optional: look for earlier tickets that mention this IP or the jump host.",
    },
    step_why={
        # Investigation
        "mcp_identity": {
            "rationale": "An IP we own or contracted changes the question from 'attacker?' to 'is this expected business traffic?'.",
            "decides": "Whether to treat the traffic as a partner integration or an unknown external actor.",
            "if_skipped": "We would judge the traffic without knowing whether it was supposed to happen.",
        },
        "requested_30d": {
            "rationale": "This is the question asked: what did the IP actually do in the last 30 days?",
            "decides": "Which internal hosts were reached and whether anything was allowed, not just denied.",
            "if_skipped": "No factual basis for any verdict.",
        },
        "novelty_window": {
            "rationale": "A brand-new source behaves differently from a long-standing one; the SOP treats them differently.",
            "decides": "Whether the 'newly observed' SOP path applies.",
            "if_skipped": "We could mistake an old, known integration for a new threat.",
        },
        "threat_intel": {
            "rationale": "A match in our IOC lists would justify immediate escalation.",
            "decides": "Known-bad (escalate now) vs unknown (continue evidence-led).",
            "if_skipped": "We could miss a known campaign indicator.",
        },
        "evaluate_notable": {
            "rationale": "Tells leadership whether existing detection content would have caught this at all.",
            "decides": "Whether a detection gap needs fixing, independent of this IP's verdict.",
            "if_skipped": "'No alert' would be mistaken for 'safe'.",
        },
        "retrieve_sop": {
            "rationale": "The response must follow the approved enterprise SOP, not ad-hoc judgement.",
            "decides": "Monitor vs block, and who must approve a block.",
            "if_skipped": "Remediation would not be defensible in an audit.",
        },
        "permitted_sessions": {
            "rationale": "Three connections were allowed to the jump host — the admin path into production. Allowed traffic matters more than 922 denies.",
            "decides": "Whether authentication can be tied to this IP (compromise) or not (unexplained, monitor).",
            "if_skipped": "The only traffic that got through would go unexamined.",
        },
        "privileged_accounts": {
            "rationale": "Adds certainty on whether svc_jump_ops behaved unusually.",
            "decides": "Strengthens or weakens the compromise hypothesis; not required for the SOP decision.",
            "if_skipped": "Verdict still stands on firewall and auth evidence.",
        },
        "endpoint_activity": {
            "rationale": "Would show what ran on the jump host during the allowed sessions.",
            "decides": "Adds certainty; not required for the SOP decision.",
            "if_skipped": "Verdict still stands on firewall and auth evidence.",
        },
        "previous_incidents": {
            "rationale": "Links this IP to earlier incidents if any exist.",
            "decides": "Whether this is part of a known campaign; not required for the SOP decision.",
            "if_skipped": "Campaign linkage stays unknown.",
        },
        # Remediation
        "generate_spl": {
            "rationale": "SOP step 1 is targeted monitoring of exactly the traffic that got through (IP → jump host 443/8443) plus svc_jump_ops logons.",
            "reversible": "Yes — it is a read-only search definition.",
            "approver": "SOC analyst",
            "risk_if_skipped": "A repeat session would go unnoticed.",
        },
        "validate_spl": {
            "rationale": "Every query must pass the deterministic SPL validator (scope, time bounds, no risky commands) before it touches Splunk.",
            "reversible": "Yes — validation changes nothing.",
            "approver": "Automatic policy check",
            "risk_if_skipped": "An unsafe or unbounded search could run against production Splunk.",
        },
        "deploy_monitoring": {
            "rationale": "Backtests the watch over the last 14 days so we know what 'normal' looks like before it starts alerting.",
            "reversible": "Yes — read-only search.",
            "approver": "SOC analyst",
            "risk_if_skipped": "The watch could fire on known traffic and create noise.",
        },
        "verify_monitoring": {
            "rationale": "Confirms the backtest returns the 3 known sessions, which proves the watch sees the right traffic.",
            "reversible": "Yes — read-only search.",
            "approver": "SOC analyst",
            "risk_if_skipped": "A mis-scoped watch could stay silent when it should fire.",
        },
        "monitor_14d": {
            "rationale": "The SOP's 14-day window: long enough to see repeat behaviour, short enough to force a decision.",
            "reversible": "Yes — the watch expires after 14 days.",
            "approver": "SOC analyst",
            "risk_if_skipped": "No trigger for escalation if the IP returns.",
        },
        "create_incident": {
            "rationale": "Unexplained access to a privileged host must be on record, even when not confirmed malicious.",
            "reversible": "Yes — incidents can be downgraded or closed.",
            "approver": "SOC analyst",
            "risk_if_skipped": "No audit trail if the IP later turns out hostile.",
        },
        "notify_firewall": {
            "rationale": "The SOC shift owns the watch; the firewall team is copied because an exception may explain the allowed sessions.",
            "reversible": "No — once sent, an email cannot be recalled.",
            "approver": "SOC analyst (explicit Send)",
            "risk_if_skipped": "The next shift would not know a watch is running.",
        },
        "confirm_owner": {
            "rationale": "Only the integration owner can say whether the 3 sessions were expected — it is the one question evidence cannot answer.",
            "reversible": "No — once sent, an email cannot be recalled.",
            "approver": "SOC analyst (explicit Send)",
            "risk_if_skipped": "The sessions stay 'unexplained' indefinitely.",
        },
        "prepare_block": {
            "rationale": "Shown so the decision is explicit: the SOP block threshold (attributable auth, confirmed malice, or policy exception) is not met.",
            "reversible": "Not executed.",
            "approver": "Network + SOC lead (only if the threshold is met)",
            "risk_if_skipped": "Blocking now could break a legitimate partner integration.",
        },
        "update_ticket": {
            "rationale": "Records the final state: monitoring active, malicious use unconfirmed, block not required.",
            "reversible": "Yes — the ticket can be updated.",
            "approver": "SOC analyst",
            "risk_if_skipped": "The incident would not reflect what was actually done.",
        },
    },
    executive_brief={
        "investigation": {
            "verdict": "Not confirmed malicious — but a brand-new external IP had 3 sessions allowed to the jump host, and they are unexplained.",
            "business_impact": "Jump host 10.20.1.10 is the admin path into production servers, and svc_jump_ops is a privileged account. If the sessions are hostile, an attacker is one hop from critical systems.",
            "risk_from": "UNKNOWN",
            "risk_to": "MEDIUM",
            "confidence": "Medium — 30 days of firewall and authentication logs; no endpoint data from the jump host.",
            "would_change_if": "A logon by svc_jump_ops is attributed to 198.51.100.42, or the integration owner cannot explain the sessions → escalate to P1 and block.",
            "decision_needed": "Approve SOP monitoring: a 14-day watch, an incident record, and a question to the integration owner. Blocking is not recommended yet.",
            "will_not_do": "Block the IP or disable the account before the SOP threshold is met and Network/SOC approve.",
        },
        "complete": {
            "verdict": "Watch in place for 14 days; IP left unblocked under monitoring; integration owner asked to explain the 3 sessions.",
            "business_impact": "No service disruption. Any repeat access to the jump host now raises an alert within 15 minutes.",
            "risk_from": "MEDIUM",
            "risk_to": "MEDIUM",
            "confidence": "Medium — unchanged until the owner replies or the watch fires.",
            "would_change_if": "The watch fires or the owner cannot account for the sessions → escalate to P1 and request a block.",
            "decision_needed": "None now. Review the owner's reply within 48 hours.",
            "will_not_do": "Close the incident before the 14-day window ends.",
        },
    },
)

register_cio_content(S1_CIO_CONTENT)
