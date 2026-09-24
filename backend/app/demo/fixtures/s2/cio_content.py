"""S2 CIO layer — prompt injection against the customer-facing AI assistant."""

from __future__ import annotations

from app.demo.ec_agent.cio_content import CioContent, register_cio_content
from app.demo.fixtures.s2.agent_config import S2_SCENARIO_ID

S2_CIO_CONTENT = CioContent(
    scenario_id=S2_SCENARIO_ID,
    opening_narrative=(
        "My plan answers three questions about the customer-facing AI assistant: were prompt-injection "
        "attempts made, did any unauthorized tool actually run, and was restricted customer data "
        "touched? Eight checks, starting from the detection we already have and ending with the AI "
        "security policy. Nothing runs until you approve."
    ),
    step_summary={
        "tool_authorization": "Governed Splunk search of AI-gateway tool-call logs: was export_customer_records authorized or executed?",
        "dlp_window": "Re-run the DLP saved search in Splunk for the same time window.",
        "identity_session": "Check the user session in Splunk identity telemetry for signs of hijack.",
        "data_source_audit": "Check datastore audit logs (forwarded to Splunk) for reads of the customer_records table.",
        "ai_policy": "Retrieve the enterprise AI security policy from SOC-KB, with a citation.",
    },
    step_why={
        "replay_detection": {
            "rationale": "Reuse the detection we already own before writing anything new — it is tuned and trusted.",
            "decides": "Whether attempts happened at all (question 1).",
            "if_skipped": "We would rebuild what already exists and lose the detection's history.",
        },
        "gateway_events": {
            "rationale": "The AI gateway sees the actual prompts; it confirms these were instruction-override attempts, not noisy false positives.",
            "decides": "Question 1: attempts confirmed or not.",
            "if_skipped": "A detection hit could be a false positive.",
        },
        "tool_authorization": {
            "rationale": "The damage from prompt injection comes from tools the assistant can call; export_customer_records is the dangerous one.",
            "decides": "Question 2: did an unauthorized tool run?",
            "if_skipped": "We could not say whether the attack succeeded.",
        },
        "dlp_window": {
            "rationale": "Independent control: even if a tool ran, DLP would show customer records leaving.",
            "decides": "Question 3: was data exfiltrated?",
            "if_skipped": "Exfiltration would rest on one source of evidence.",
        },
        "tool_history": {
            "rationale": "Attackers try several tools; one blocked call does not mean nothing else ran.",
            "decides": "Question 2: whether any other unauthorized tool executed.",
            "if_skipped": "A second successful tool call could be missed.",
        },
        "identity_session": {
            "rationale": "A hijacked session would mean a credential problem, not just a prompt problem.",
            "decides": "Whether the incident is limited to the AI layer.",
            "if_skipped": "Credential compromise stays open.",
        },
        "data_source_audit": {
            "rationale": "The database is the final record of what was read, regardless of which path was used.",
            "decides": "Question 3: were restricted records read?",
            "if_skipped": "Data access rests on DLP alone.",
        },
        "ai_policy": {
            "rationale": "Remediation must follow the AI security policy; the policy also defines what counts as a breach.",
            "decides": "Which containment steps are mandatory.",
            "if_skipped": "Remediation would not be policy-backed.",
        },
        "create_incident": {
            "rationale": "An attempted abuse of a customer-facing AI system is reportable internally even when blocked.",
            "reversible": "Yes — incidents can be downgraded or closed.",
            "approver": "SOC analyst",
            "risk_if_skipped": "No record for trend analysis or audit.",
        },
        "disable_credential": {
            "rationale": "Precautionary: the attacker reached the tool-authorization layer, and this connector can export customer records. Rotating and scoping it down removes the prize while AppSec reviews.",
            "reversible": "Yes — the credential can be re-issued in about 15 minutes.",
            "approver": "IAM owner (approval required)",
            "risk_if_skipped": "A future bypass of tool authorization would reach a live export credential.",
        },
        "block_session": {
            "rationale": "Containment at the source: stop the offending session and rate-limit its user while the investigation closes.",
            "reversible": "Yes — the block expires after 24 hours or can be lifted.",
            "approver": "AI platform owner (approval required)",
            "risk_if_skipped": "The same actor can keep probing the assistant.",
        },
        "extend_detection": {
            "rationale": "Investigation step 1 showed the existing detection has only partial coverage; this closes the gap for next time.",
            "reversible": "Yes — detection content is versioned.",
            "approver": "Detection engineering",
            "risk_if_skipped": "Variants of the same attack would go undetected.",
        },
        "notify_appsec": {
            "rationale": "AppSec owns the assistant's guardrails and must decide on hardening.",
            "reversible": "No — once sent, an email cannot be recalled.",
            "approver": "SOC analyst (explicit Send)",
            "risk_if_skipped": "The owners of the fix would not know.",
        },
        "verify_credential": {
            "rationale": "Proves the credential change took effect instead of assuming it.",
            "reversible": "Yes — read-only check.",
            "approver": "SOC analyst",
            "risk_if_skipped": "A failed rotation would go unnoticed.",
        },
        "update_ticket": {
            "rationale": "Records the honest outcome: attempted, blocked, breach not confirmed.",
            "reversible": "Yes — the ticket can be updated.",
            "approver": "SOC analyst",
            "risk_if_skipped": "The record would overstate or understate impact.",
        },
        "closure": {
            "rationale": "A closure summary that a regulator or customer could read without correction.",
            "reversible": "Yes — can be reopened.",
            "approver": "SOC lead",
            "risk_if_skipped": "The incident stays open with no owner.",
        },
    },
    executive_brief={
        "investigation": {
            "verdict": "Attack attempted and blocked. No customer data left, and no unauthorized tool ran.",
            "business_impact": "The customer-facing AI assistant was targeted directly. Our tool-authorization control worked; had it failed, export_customer_records could have exposed customer records.",
            "risk_from": "HIGH",
            "risk_to": "MEDIUM",
            "confidence": "High — detection, gateway, tool-authorization, DLP and datastore audit all agree.",
            "would_change_if": "Any execution receipt for export_customer_records, or DLP hits in a wider window → treat as a data breach.",
            "decision_needed": "Approve containment: rotate the export connector credential, block the offending session, and extend the detection.",
            "will_not_do": "Take the assistant offline — the control held and customers are unaffected.",
        },
        "complete": {
            "verdict": "Contained: session blocked, export credential rotated, detection extended. Breach not confirmed.",
            "business_impact": "The assistant stays in service. The one high-value tool is now behind a fresh, narrower credential.",
            "risk_from": "HIGH",
            "risk_to": "MEDIUM",
            "confidence": "High.",
            "would_change_if": "AppSec finds a guardrail bypass in the prompt logs.",
            "decision_needed": "None now. AppSec to report guardrail hardening within 5 working days.",
            "will_not_do": "Close as 'breach' — no evidence supports it.",
        },
    },
)

register_cio_content(S2_CIO_CONTENT)
