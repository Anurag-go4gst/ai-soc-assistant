"""S2 investigation step findings — derived from EC fixture evidence only."""

from __future__ import annotations

from typing import Any

from app.demo.ec_siem import S2_DETECTION_NAME, S2_GAP_CANDIDATE_SPL, S2_SAVED_SEARCH_NAME

INJECTION_REQUESTS = (
    {"request_id": "ai-8841", "pattern": "ignore previous instructions", "action": "blocked_prompt"},
    {"request_id": "ai-8842", "pattern": "export all customer records", "action": "tool_denied"},
    {"request_id": "ai-8843", "pattern": "ignore previous instructions", "action": "blocked_prompt"},
)
BLOCKED_TOOL = "export_customer_records"
ALLOWED_TOOL = "search_kb"


def _complete(applied: list[str], follow_up_id: str) -> bool:
    return follow_up_id in applied


def finding_for_investigation_step(
    step_id: str,
    *,
    status: str,
    applied: list[str] | None = None,
    agent_state: dict[str, Any] | None = None,
    outcome: dict[str, Any] | None = None,
    selected: bool = True,
) -> dict[str, Any] | None:
    del agent_state, outcome
    applied = list(applied or [])
    token = status.upper()
    if not selected or token == "SKIPPED":
        return {
            "headline_finding": "Skipped — not included in the approved investigation plan.",
            "headlines_by_status": {
                "QUEUED": "Queued",
                "RUNNING": "Running…",
                "COMPLETE": "Skipped",
            },
            "attention_state": "INFORMATIONAL",
            "evidence_sources": [],
            "caveat": "Skipped steps do not produce attributable findings.",
        }
    if token == "RUNNING":
        return {
            "headline_finding": "Running…",
            "headlines_by_status": {
                "QUEUED": "Queued",
                "RUNNING": "Running…",
                "COMPLETE": "Complete",
            },
            "attention_state": "NORMAL",
            "evidence_sources": [],
        }
    if token not in {"COMPLETE"}:
        return {
            "headline_finding": "Queued — waiting for investigation run",
            "headlines_by_status": {
                "QUEUED": "Queued — waiting for investigation run",
                "RUNNING": "Running…",
                "COMPLETE": "Complete",
            },
            "attention_state": "NORMAL",
            "evidence_sources": [],
        }

    if step_id == "replay_detection":
        return {
            "headline_finding": (
                f"3 injection-pattern events on {S2_DETECTION_NAME} — partial coverage, reused first"
            ),
            "headlines_by_status": {
                "QUEUED": f"Queued — replay {S2_SAVED_SEARCH_NAME}",
                "RUNNING": f"Replaying saved search {S2_SAVED_SEARCH_NAME}…",
                "COMPLETE": "3 injection-pattern events — existing detection reused",
            },
            "key_evidence": [
                f"saved_search={S2_SAVED_SEARCH_NAME}",
                "ai-8841 ignore previous instructions → blocked_prompt",
                "ai-8842 export all customer records → tool_denied",
            ],
            "quantitative_summary": {"injection_events": 3, "new_spl_generated": False},
            "confidence": "high",
            "attention_state": "ATTENTION",
            "caveat": "Existing detection coverage is partial; tool execution still needs the gap search.",
            "evidence_sources": [
                {
                    "source": "Splunk MCP",
                    "evidence_id": "ev-s2-detection",
                    "provenance": "simulated_mcp",
                    "tool": "splunk_run_saved_search",
                },
            ],
        }

    if step_id == "gateway_events":
        return {
            "headline_finding": "Instruction-override prompts confirmed on the customer-facing assistant",
            "headlines_by_status": {
                "QUEUED": "Queued — review AI gateway events",
                "RUNNING": "Reading AI gateway / guardrail events…",
                "COMPLETE": "Instruction-override prompts confirmed",
            },
            "key_evidence": [
                "Gateway blocked ai-8841 (ignore previous instructions)",
                "Jailbreak / instruction-override pattern in assistant API logs",
            ],
            "confidence": "high",
            "attention_state": "ATTENTION",
            "evidence_sources": [
                {
                    "source": "Splunk MCP",
                    "evidence_id": "ev-s2-gateway",
                    "provenance": "simulated_mcp",
                    "tool": "splunk_run_saved_search",
                },
            ],
        }

    if step_id == "tool_authorization":
        return {
            "headline_finding": (
                f"{BLOCKED_TOOL} requested and denied — no execution receipt"
            ),
            "headlines_by_status": {
                "QUEUED": "Queued — review tool-call authorization",
                "RUNNING": "Checking tool-call audit…",
                "COMPLETE": f"{BLOCKED_TOOL} denied — not executed",
            },
            "key_evidence": [
                f"tool={BLOCKED_TOOL} authorized=false executed=false",
                "reason=tool_authorization_denied",
                f"Bounded gap SPL used only for this tool path (execution_eligible=false): {S2_GAP_CANDIDATE_SPL[:48]}…",
            ],
            "quantitative_summary": {"unauthorized_tools_executed": 0, "blocked_attempts": 1},
            "confidence": "high",
            "attention_state": "RISK",
            "caveat": "A blocked tool request is not a breach and is not successful execution.",
            "evidence_sources": [
                {
                    "source": "Splunk MCP",
                    "evidence_id": "ev-s2-tool",
                    "provenance": "simulated_mcp",
                    "tool": "splunk_run_query",
                },
            ],
        }

    if step_id == "dlp_window":
        done = _complete(applied, "check_dlp")
        return {
            "headline_finding": (
                "No customer-record exfiltration in the DLP window"
                if done
                else "DLP window not yet queried"
            ),
            "headlines_by_status": {
                "QUEUED": "Queued — check DLP window",
                "RUNNING": "Reviewing DLP alerts for the assistant channel…",
                "COMPLETE": "No DLP exfiltration in the reviewed window",
            },
            "key_evidence": ["channel=ai_assistant", "exfil_confirmed=false", "alerts=0"],
            "confidence": "high",
            "attention_state": "NO_MATCH",
            "evidence_sources": [
                {
                    "source": "Splunk MCP",
                    "evidence_id": "ev-s2-dlp",
                    "provenance": "simulated_mcp",
                    "tool": "splunk_run_saved_search",
                },
            ],
        }

    if step_id == "tool_history":
        return {
            "headline_finding": "No other unauthorized tools executed in the reviewed history",
            "headlines_by_status": {
                "QUEUED": "Queued — inspect broader tool-call history",
                "RUNNING": "Scanning tool-call history…",
                "COMPLETE": "No other unauthorized tools executed",
            },
            "key_evidence": [
                f"{BLOCKED_TOOL} blocked by tool_authorization",
                f"{ALLOWED_TOOL} allowed (12 calls)",
            ],
            "confidence": "high",
            "attention_state": "NO_MATCH",
            "evidence_sources": [
                {
                    "source": "Splunk MCP",
                    "evidence_id": "ev-s2-tools",
                    "provenance": "simulated_mcp",
                    "tool": "splunk_run_saved_search",
                },
            ],
        }

    if step_id == "identity_session":
        return {
            "headline_finding": "Interactive user session intact — no hijack indicators",
            "headlines_by_status": {
                "QUEUED": "Queued — check identity / session",
                "RUNNING": "Retrieving session context…",
                "COMPLETE": "Session intact — hijack not confirmed",
            },
            "key_evidence": ["user=ext-assistant-gw", "session_hijack=false"],
            "confidence": "high",
            "attention_state": "NO_MATCH",
            "evidence_sources": [
                {
                    "source": "Splunk MCP",
                    "evidence_id": "ev-s2-iam",
                    "provenance": "simulated_mcp",
                    "tool": "splunk_run_saved_search",
                },
            ],
        }

    if step_id == "data_source_audit":
        return {
            "headline_finding": "No unauthorized restricted-table reads attributed to the blocked tool",
            "headlines_by_status": {
                "QUEUED": "Queued — audit restricted-data access logs",
                "RUNNING": "Reading customer_records access logs…",
                "COMPLETE": "Restricted-data access not confirmed",
            },
            "key_evidence": ["store=customer_records", "unauthorized_read=false"],
            "confidence": "high",
            "attention_state": "NO_MATCH",
            "caveat": "Absence of attributed reads is not a proof of zero access outside this store.",
            "evidence_sources": [
                {
                    "source": "Splunk MCP",
                    "evidence_id": "ev-s2-data",
                    "provenance": "simulated_mcp",
                    "tool": "splunk_run_saved_search",
                },
            ],
        }

    if step_id == "ai_policy":
        return {
            "headline_finding": "Policy in force: tool authorization required; restricted-data export denied",
            "headlines_by_status": {
                "QUEUED": "Queued — open AI security policy",
                "RUNNING": "Opening enterprise AI security policy…",
                "COMPLETE": "Restricted-data export denied by policy",
            },
            "key_evidence": [
                "allowed_tools=search_kb,summarize_case",
                f"denied_tools={BLOCKED_TOOL}",
                "restricted_data_export=deny",
                "not_production_policy=true",
            ],
            "confidence": "high",
            "attention_state": "INFORMATIONAL",
            "evidence_sources": [
                {
                    "source": "SOC-KB",
                    "evidence_id": "ev-s2-policy",
                    "provenance": "ec_scenario_policy",
                    "tool": None,
                },
            ],
        }

    return None
