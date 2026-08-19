"""S2 agent step definitions — prompt-injection / tool / data-access investigation."""

from __future__ import annotations

from typing import Any

S2_SCENARIO_ID = "s2_ai_prompt_injection"
S2_FAMILY = "s2_ai_security"

INVESTIGATION_STEP_DEFS: tuple[dict[str, Any], ...] = (
    {
        "id": "replay_detection",
        "title": "Replay existing Splunk prompt-injection detection",
        "summary": "Reuse EC_AI_Prompt_Injection_Detection before generating any new SPL.",
        "follow_up_id": "review_existing_detection",
        "tools": ["Splunk MCP"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "gateway_events",
        "title": "Review AI gateway / guardrail events",
        "summary": "Confirm instruction-override patterns from AI gateway events already indexed in Splunk.",
        "follow_up_id": None,
        "bundle_with": "review_existing_detection",
        "tools": ["Splunk MCP"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "tool_authorization",
        "title": "Review unauthorized tool-call attempts",
        "summary": "Governed Splunk gap search: whether export_customer_records was authorized or executed.",
        "follow_up_id": None,
        "bundle_with": "review_existing_detection",
        "tools": ["Splunk MCP"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "dlp_window",
        "title": "Check DLP window for customer-record exfiltration",
        "summary": "Reuse a Splunk DLP saved search for the same window — there is no DLP MCP.",
        "follow_up_id": "check_dlp",
        "tools": ["Splunk MCP"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "tool_history",
        "title": "Inspect broader tool-call history",
        "summary": "Look for other unauthorized tools besides the blocked export.",
        "follow_up_id": "check_tool_call_history",
        "tools": ["Splunk MCP"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "identity_session",
        "title": "Check identity / session context",
        "summary": "Confirm the interactive session was not hijacked using Splunk identity/session telemetry — no IAM MCP is onboarded.",
        "follow_up_id": "check_identity",
        "tools": ["Splunk MCP"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "data_source_audit",
        "title": "Audit restricted-data access logs",
        "summary": "Confirm no unauthorized customer_records reads from datastore audit forwarded to Splunk — no database MCP is onboarded.",
        "follow_up_id": "check_data_source",
        "tools": ["Splunk MCP"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "ai_policy",
        "title": "Open enterprise AI security policy",
        "summary": "Retrieve the AI security policy from governed SOC-KB (RAG), not MCP.",
        "follow_up_id": "show_ai_security_policy",
        "tools": ["SOC-KB"],
        "default_selected": True,
        "phase": "investigation",
    },
)

REMEDIATION_STEP_DEFS: tuple[dict[str, Any], ...] = (
    {
        "id": "create_incident",
        "title": "Create AI security incident",
        "summary": "Open a ticket for the blocked prompt-injection attempt.",
        "follow_up_id": "create_ai_incident_ticket",
        "tools": ["ITSM (simulated)"],
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "disable_credential",
        "title": "Disable integration credential",
        "summary": "HIL-gated IAM action. No IAM MCP is implemented — simulated disable only.",
        "follow_up_id": "disable_integration_credential",
        "tools": ["IAM (HIL, simulated)"],
        "hil_required": True,
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "notify_appsec",
        "title": "Email AppSec / AI platform team",
        "summary": "Notify APPSEC_TEAM via Experience Center allowlisted email (SMTP), not MCP.",
        "follow_up_id": "notify_app_security",
        "tools": ["Email (allowlisted SMTP)"],
        "hil_required": True,
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "verify_credential",
        "title": "Verify credential state",
        "summary": "Confirm the export connector credential is disabled.",
        "follow_up_id": "verify_credential_state",
        "tools": ["IAM (HIL, simulated)"],
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "update_ticket",
        "title": "Update incident ticket",
        "summary": "Record blocked execution and unconfirmed breach on the ticket.",
        "follow_up_id": "update_incident",
        "tools": ["ITSM (simulated)"],
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "closure",
        "title": "Generate closure summary",
        "summary": "Close with honest impact: attempted, blocked, breach not confirmed.",
        "follow_up_id": "generate_closure_summary",
        "tools": [],
        "default_selected": True,
        "phase": "remediation",
    },
)

INVESTIGATION_PLAN_SUMMARY = (
    "Eight governed read-only steps to answer three questions: prompt-injection attempts, "
    "unauthorized tool execution, and restricted-data access — reuse before generate."
)
ACTION_PLAN_SUMMARY = (
    "Reuse the existing Splunk detection first, close the tool-execution gap, then confirm "
    "DLP, identity, and datastore logs before any containment action."
)
CONVERSATIONAL_FOLLOWUPS = frozenset({"generate_executive_summary"})

OPENING_NARRATIVE = (
    "To investigate potential prompt-injection attempts and unauthorized tool execution or "
    "restricted-data access targeting your customer-facing AI assistant, you can follow these "
    "steps using Splunk and MCP Tools and RAG Guidelines.\n\n"
    "This investigation would typically involve collecting and analyzing logs from the AI system, "
    "user interactions, and any system-level activities that could indicate unauthorized access "
    "or misuse."
)
BRIEF = {
    "what_i_know": [
        "Customer-facing AI assistant is in scope",
        "Existing Splunk detection AI Assistant — Prompt Injection Attempt (partial coverage)",
        "Tool authorization is required for restricted-data export",
        "No live MCP or live LLM on this Experience Center path",
    ],
    "objective": [
        "Were prompt-injection attempts observed?",
        "Did any unauthorized tool execute?",
        "Was restricted customer data accessed?",
    ],
}
ACTION_PLAN_STEPS = [
    "Replay the existing prompt-injection saved search and gateway events",
    "Confirm whether export_customer_records was authorized or executed",
    "Check DLP, broader tool history, identity, and restricted-data logs",
    "Open AI security policy, then propose HIL-gated containment",
]

PLAN_PREREAD: tuple[str, ...] = ()
