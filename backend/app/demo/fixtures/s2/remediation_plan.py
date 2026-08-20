"""S2 remediation plan findings and artifact metadata."""

from __future__ import annotations

from typing import Any

from app.demo.fixtures.s2.investigation_findings import BLOCKED_TOOL

_FOLLOW_UP_BY_STEP = {
    "create_incident": "create_ai_incident_ticket",
    "disable_credential": "disable_integration_credential",
    "notify_appsec": "notify_app_security",
    "verify_credential": "verify_credential_state",
    "update_ticket": "update_incident",
    "closure": "generate_closure_summary",
}


def _executed(step_id: str, applied: list[str]) -> bool:
    follow_up = _FOLLOW_UP_BY_STEP.get(step_id)
    return bool(follow_up and follow_up in applied)


def finding_for_remediation_step(
    step_id: str,
    *,
    status: str,
    normalized: dict[str, Any],
    applied: list[str] | None = None,
) -> dict[str, Any] | None:
    del normalized
    applied = applied or []
    executed = _executed(step_id, applied)
    token = status.upper()
    copy = {
        "create_incident": (
            "Queued — open AI security incident",
            "Creating AI security incident…",
            "AI security incident opened — impact attempted_blocked",
        ),
        "disable_credential": (
            "Queued — disable ai-assistant-export-connector (HIL)",
            "Preparing credential disable for analyst approval…",
            "Export connector credential disable executed (simulated)",
        ),
        "notify_appsec": (
            "Queued — email AppSec / AI platform team (HIL)",
            "Drafting APPSEC_TEAM notification…",
            "AppSec notification prepared / sent after approval",
        ),
        "verify_credential": (
            "Queued — verify credential state",
            "Verifying export connector credential…",
            "Simulated credential state is disabled",
        ),
        "update_ticket": (
            "Queued — update incident with blocked-not-breached outcome",
            "Updating incident ticket…",
            "Incident updated — breach not confirmed",
        ),
        "closure": (
            "Queued — generate closure summary",
            "Writing closure summary…",
            "Closed: attempted, blocked, breach not confirmed",
        ),
    }.get(step_id, ("Queued", "Running…", "Complete"))
    queued, running, complete = copy
    if token == "RUNNING":
        current = running
    elif token == "COMPLETE":
        current = complete if executed else queued.replace("Queued —", "Validated —")
    else:
        current = queued
    return {
        "headline_finding": current,
        "headlines_by_status": {"QUEUED": queued, "RUNNING": running, "COMPLETE": complete, "VALIDATED": queued.replace("Queued —", "Validated —")},
        "attention_state": "NORMAL",
    }


def enrich_remediation_steps(
    steps: list[dict[str, Any]],
    *,
    normalized: dict[str, Any],
    applied: list[str],
) -> list[dict[str, Any]]:
    del normalized
    enriched: list[dict[str, Any]] = []
    for step in steps:
        finding = finding_for_remediation_step(
            str(step["id"]),
            status=str(step.get("status") or "QUEUED"),
            normalized={},
            applied=applied,
        )
        enriched.append({**step, "finding": finding, "result": (finding or {}).get("headline_finding")})
    return enriched


def build_s2_remediation_summary(*, selected_count: int, total_count: int) -> dict[str, Any]:
    return {
        "title": "Remediation plan ready",
        "steps_completed": 0,
        "steps_total": selected_count,
        "plan_steps": f"{selected_count}/{total_count} selected",
        "metrics": [
            {"label": "Blocked tool", "value": BLOCKED_TOOL},
            {"label": "HIL actions", "value": 2},
            {"label": "ITSM", "value": 2},
        ],
    }


def build_s2_remediation_conclusion(*, normalized: dict[str, Any]) -> dict[str, Any]:
    del normalized
    return {
        "title": "Remediation approach",
        "headline": (
            f"Contain the blocked {BLOCKED_TOOL} path without treating a denied tool call as a breach."
        ),
        "narrative_points": [
            "Open an AI security incident with impact=attempted_blocked.",
            "HIL-disable the export connector credential — not an auto-executed IAM write.",
            "Notify AppSec / AI platform (logical APPSEC_TEAM) after send approval.",
            "Verify credential state, update the ticket, and close with breach not confirmed.",
        ],
    }
