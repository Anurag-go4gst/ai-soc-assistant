"""S2 — prompt-injection attempts against the customer-facing AI assistant."""

from __future__ import annotations

from app.demo import ec_environment as E
from app.demo.ec_agent.spec_engine import Action, Check, Email, ScenarioSpec

APP = E.AI_APP

S2 = ScenarioSpec(
    scenario_id="s2_ai_prompt_injection",
    family="s2_ai_security",
    label="S2 · AI assistant misuse",
    question=(
        "Our customer-facing AI assistant has been flagged for possible prompt-injection attempts. Check whether "
        "it is being targeted, and whether any attempt made it run a tool it shouldn't or reach customer data."
    ),
    legacy_phrasings=(
        'Investigate whether our customer-facing AI assistant is being targeted with prompt-injection attempts and whether any attempts resulted in unauthorized tool execution or restricted-data access.',
    ),
    demo_order=2,
    plan_title="AI assistant prompt-injection alert — plan ready",
    plan_intro=(
        "I'll look at what the assistant's guardrail blocked, whether any tool actually ran, and whether any "
        "customer data was touched. Nothing runs until you approve."
    ),
    checks=(
        Check(
            id="guardrail_blocks",
            title="What did the guardrail block?",
            plan=f"Search {E.AI_GATEWAY} logs for blocked prompts in the last 24 hours.",
            tool="splunk_mcp",
            spl=(
                'search index=aigw sourcetype=aigw:request app="customer-help-assistant" verdict=blocked '
                "earliest=-24h latest=now | stats count by session_id, src_ip, rule | head 100"
            ),
            result=(
                "37 prompts blocked in 2 hours from 4 chat sessions, all by the 'instruction override' rule. The "
                "sessions came from 2 addresses at a hosting provider, with no customer signed in."
            ),
            evidence=(
                "Blocked between {D0 01:10} and {D0 03:05}",
                "Sources 89.xx.xx.14 and 89.xx.xx.61 — hosting provider, not a consumer network",
                f"Threat intel: no match in {E.THREAT_INTEL_SOURCE}",
            ),
            attention="ATTENTION",
        ),
        Check(
            id="tool_calls",
            title="Did the assistant run any tool?",
            plan="Check the tool-call log for these sessions: requested, allowed, run.",
            tool="splunk_mcp",
            spl=(
                'search index=app sourcetype=app:toolcall app="customer-help-assistant" earliest=-24h latest=now '
                "| stats count by session_id, tool, decision, executed | head 100"
            ),
            result="1 tool request — export_customer_records — refused by the permission check. No tool ran.",
            evidence=(
                "Requested at {D0 02:47}; decision: deny (session not signed in)",
                "0 tool executions from the 4 sessions",
            ),
        ),
        Check(
            id="customer_data",
            title="Did any customer data leave?",
            plan="Check data-loss-prevention and data-access logs for the 4 sessions.",
            tool="splunk_mcp",
            spl=(
                'search index=dlp sourcetype=dlp:event app="customer-help-assistant" earliest=-24h latest=now '
                "| stats count by session_id, policy, action | head 100"
            ),
            result="No DLP events and no customer-data access linked to these sessions.",
            evidence=("Limitation: prompt text beyond 512 characters isn't logged",),
        ),
    ),
    added_check=Check(
        id="tool_permissions",
        title="Could that tool ever run from a chat like this?",
        plan="Check the AI tool permission register and our AI misuse SOP.",
        tool="soc_kb",
        operation=f"soc_kb.retrieve · AI tool permission register, {E.SOP_AI_MISUSE}",
        result=(
            "No. The export tool is allowed only for signed-in support agents; an anonymous chat can never run it."
        ),
        evidence=(
            "Register: export_customer_records — role support_agent, sign-in required",
            f"{E.SOP_AI_MISUSE}: attempted misuse with no data exposure → incident, notify AppSec, block the sources",
        ),
    ),
    added_after="tool_calls",
    added_when=("tool_calls",),
    conclusion_headline=(
        "Targeted, but contained: 37 injection attempts were blocked, the one tool request was refused, and no "
        "customer data left."
    ),
    points=(
        "Confirmed: these were deliberate instruction-override attempts, not normal customer questions.",
        "Confirmed: no tool ran and no customer data was accessed from these sessions.",
        "Inference: 2 hosting-provider addresses and no sign-in suggest one actor testing the assistant.",
    ),
    unresolved=(
        "Who is behind the two hosting-provider addresses.",
        "The full text of the longest prompts — only the first 512 characters are logged.",
    ),
    threat="Confirmed",
    asset_tier=1,
    evidence_state="attempted_misuse",
    subject=f"{APP} ({E.AI_GATEWAY})",
    decision=(
        f"Proposed: open a P3 incident, ask the AI platform team to block the 2 addresses at {E.AI_GATEWAY}, and "
        "tell AppSec. Rotating the export tool's credential is not proposed — it never ran."
    ),
    actions=(
        Action(
            id="open_incident",
            title="Open a P3 incident",
            proposal=f"ITSM incident at P3 ({E.PRIORITY_POLICY} rule 3: attempted misuse, nothing gained).",
            tool="itsm",
            verb="incident",
            ticket_id=E.INCIDENT_S2,
            executed=f"Incident {E.INCIDENT_S2} opened (P3)",
            verified="read back from ITSM",
        ),
        Action(
            id="block_sources",
            title=f"Ask the AI platform team to block the 2 addresses at {E.AI_GATEWAY}",
            proposal="ITSM request to the AI platform team, who own the gateway. The SOC has no write access to it.",
            tool="itsm",
            verb="request",
            ticket_id=E.TASK_S2_AI_PLATFORM,
            executed=f"Request {E.TASK_S2_AI_PLATFORM} raised with the AI platform team",
            status_after="REQUESTED",
        ),
        Action(
            id="tell_appsec",
            title="Tell AppSec",
            proposal="Short email to AppSec, copied to the AI platform owner.",
            tool="email",
            verb="email",
            email=Email(
                to="AppSec",
                mailbox="APPSEC_TEAM",
                cc="AI platform owner",
                subject=f"Prompt-injection attempts on the {APP} — contained",
                body=(
                    f"You're receiving this as owner of AI application security for the {APP}.\n\n"
                    "What we saw: 37 instruction-override prompts from 4 anonymous sessions (2 hosting-provider "
                    "addresses) between {D0 01:10} and {D0 03:05}. One session asked for export_customer_records; the "
                    "permission check refused it. No tool ran and no customer data was accessed.\n\n"
                    "Please review whether the guardrail rules need tuning, and whether you want the full prompt "
                    "text logged for longer prompts.\n\n"
                    "Incident: {incident}\n\n"
                    "SOC Tier 2"
                ),
            ),
            executed="Sent to AppSec, cc AI platform owner",
        ),
    ),
    not_proposed=("Rotate the export tool credential — not needed, the tool never ran",),
    final_state="OPEN — CONTAINMENT REQUESTED",
    final_headline="P3 incident open; the AI platform team has been asked to block the sources; AppSec informed.",
    pending=(f"AI platform team to apply the block at {E.AI_GATEWAY}",),
    next_triggers="Re-investigate if the same addresses return, a tool call is allowed, or DLP flags assistant traffic.",
)
