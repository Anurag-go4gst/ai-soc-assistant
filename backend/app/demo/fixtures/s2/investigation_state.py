"""Normalized S2 investigation state — feeds remediation copy."""

from __future__ import annotations

from typing import Any

from app.demo.fixtures.s2.investigation_findings import BLOCKED_TOOL


def build_s2_normalized_investigation_state(
    *,
    applied: list[str],
    agent_state: dict[str, Any],
    outcome: dict[str, Any],
    investigation_steps: list[dict[str, Any]],
) -> dict[str, Any]:
    del agent_state
    dlp_done = "check_dlp" in applied
    data_done = "check_data_source" in applied
    tools_done = "check_tool_call_history" in applied
    identity_done = "check_identity" in applied
    detection_done = "review_existing_detection" in applied

    completed = sum(
        1
        for step in investigation_steps
        if step.get("selected", True) and str(step.get("status") or "").upper() == "COMPLETE"
    )
    total = sum(1 for step in investigation_steps if step.get("selected", True))

    unconfirmed = [
        "Successful unauthorized tool execution",
        "Restricted customer-data access",
        "Credential compromise",
        "Session hijack",
    ]
    missing: list[str] = []
    if not dlp_done:
        missing.append("DLP window")
    if not tools_done:
        missing.append("Broader tool-call history")
    if not identity_done:
        missing.append("Identity context")
    if not data_done:
        missing.append("Downstream data-source audit")

    return {
        "injection_attempt_count": 3 if detection_done else 0,
        "blocked_tool": BLOCKED_TOOL,
        "unauthorized_execution": "blocked",
        "restricted_data_access": "not_confirmed",
        "dlp_exfil_confirmed": False if dlp_done else None,
        "compromise_status": "not_confirmed",
        "session_hijack": False if identity_done else None,
        "investigation_summary": {
            "title": "Investigation complete",
            "steps_completed": completed,
            "steps_total": total,
            "metrics": [
                {"label": "Injection events", "value": 3 if detection_done else "—"},
                {"label": "Tool executed", "value": "No"},
                {"label": "DLP alerts", "value": 0 if dlp_done else "—"},
                {"label": "Data access", "value": "Not confirmed"},
            ],
        },
        "outstanding_uncertainty": unconfirmed,
        "missing_evidence": missing,
        "investigation_conclusion": {
            "headline": (
                "Prompt injection attempted; unauthorized tool execution blocked; "
                "restricted-data access not confirmed."
            ),
            "narrative_points": [
                "Existing Splunk detection was reused first — three instruction-override events on the customer-facing assistant.",
                f"{BLOCKED_TOOL} was requested and denied by tool authorization; no execution receipt was observed.",
                "DLP window shows no customer-record exfiltration; restricted-table reads are not attributed to the blocked tool.",
                "Credential compromise and session hijack remain unconfirmed — not the same as a breach.",
            ],
        },
        "outcome_confirmed": list(outcome.get("confirmed") or []),
    }


def enrich_finding_metadata(finding: dict[str, Any] | None, *, step_id: str) -> dict[str, Any] | None:
    if not finding:
        return None
    attention = finding.get("attention_state") or "NORMAL"
    if step_id in {"replay_detection", "gateway_events"}:
        attention = finding.get("attention_state") or "ATTENTION"
    elif step_id == "tool_authorization":
        attention = "RISK"
    elif step_id in {"dlp_window", "tool_history", "identity_session", "data_source_audit"}:
        attention = finding.get("attention_state") or "NO_MATCH"
    elif step_id == "ai_policy":
        attention = "INFORMATIONAL"
    return {**finding, "attention_state": attention}
