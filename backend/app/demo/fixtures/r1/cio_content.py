"""R1 CIO layer — a policy question answered from governed knowledge, then acted on."""

from __future__ import annotations

from app.demo.ec_agent.cio_content import CioContent, register_cio_content
from app.demo.fixtures.r1.pack import R1_ACCOUNT, R1_HOST, R1_INCIDENT_ID, R1_SCENARIO_ID

R1_CIO_CONTENT = CioContent(
    scenario_id=R1_SCENARIO_ID,
    opening_narrative=(
        "This is a policy question, so I will answer it from our approved SOC knowledge rather than "
        "from general knowledge. My plan: search the SOC SOPs and the escalation matrix, drop anything "
        "that is not approved for use, rank what is left, and cite a source for every sentence. If the "
        "sources don't say something, I will tell you instead of guessing. Nothing runs until you approve."
    ),
    step_why={
        "rewrite_query": {
            "rationale": "A question written for people is not a good search query; extracting the concepts finds the right passages.",
            "decides": "What the retrieval searches for.",
            "if_skipped": "Retrieval could miss the escalation matrix — which is exactly what happens with vaguer wording.",
        },
        "select_collections": {
            "rationale": "Searching only the collections that can answer a policy question keeps unrelated content out of the answer.",
            "decides": "Where the answer may come from.",
            "if_skipped": "Threat-intel or case-study passages could crowd out the SOP.",
        },
        "policy_filter": {
            "rationale": "Our knowledge base keeps draft, rejected, superseded and expired SOPs for audit. None of them may shape an answer.",
            "decides": "Which documents are even eligible.",
            "if_skipped": "An outdated SOP could be quoted as current policy.",
        },
        "retrieve_rank": {
            "rationale": "Ranking puts the most specific passage first and shows how confident the match is.",
            "decides": "Which passages the answer is built from.",
            "if_skipped": "The answer would rest on arbitrary passages.",
        },
        "grounding_check": {
            "rationale": "A policy answer is only useful if every statement can be traced to approved text.",
            "decides": "Which statements appear, and which are reported as gaps.",
            "if_skipped": "Unsupported statements could look like policy.",
        },
        "compose_answer": {
            "rationale": "The answer keeps the SOP's own wording limits — for example, it must not call this a compromise yet.",
            "decides": "The final answer text.",
            "if_skipped": "No answer to act on.",
        },
        "create_incident": {
            "rationale": "The SOP requires escalating privileged accounts; the incident is the record that escalation happened and why.",
            "reversible": "Yes — incidents can be downgraded or closed.",
            "approver": "SOC analyst",
            "risk_if_skipped": "The escalation would have no record for audit.",
        },
        "email_tier2": {
            "rationale": "The escalation matrix (ESC-AUTH-001) names the Tier 2 SOC analyst for this exact case.",
            "reversible": "No — once sent, an email cannot be recalled.",
            "approver": "SOC analyst (reviews the draft, then sends)",
            "risk_if_skipped": "The review the SOP requires would have no owner.",
        },
    },
    executive_brief={
        "investigation": {
            "verdict": "Our SOP says: escalate to a Tier 2 SOC analyst and review the account, source and session — without calling it a compromise yet.",
            "business_impact": f"{R1_ACCOUNT} is a privileged account on {R1_HOST}. Following the SOP gets the right person reviewing it now, without disrupting a possibly legitimate user.",
            "risk_from": "MEDIUM",
            "risk_to": "MEDIUM",
            "confidence": "High — three approved passages agree (AUTH-003, AUTH-001, ESC-AUTH-001); four non-approved versions were excluded.",
            "would_change_if": "The Tier 2 review finds the session did something the user should not → escalate to a confirmed account compromise.",
            "decision_needed": f"Approve: open {R1_INCIDENT_ID} and send the escalation email to the Tier 2 SOC analyst.",
            "will_not_do": "Disable or reset the account — the SOP leaves that to a human decision after review.",
        },
        "complete": {
            "verdict": f"Escalated as the SOP requires: {R1_INCIDENT_ID} is open and the Tier 2 SOC analyst has the review checklist.",
            "business_impact": "No disruption to the user; the account is now under an owned, time-boxed review.",
            "risk_from": "MEDIUM",
            "risk_to": "MEDIUM",
            "confidence": "High — every action traces to an approved passage.",
            "would_change_if": "Tier 2 finds suspicious session activity.",
            "decision_needed": "None now. Tier 2 reports back by the end of the shift.",
            "will_not_do": "Close the incident before Tier 2 completes the review.",
        },
    },
)

register_cio_content(R1_CIO_CONTENT)
