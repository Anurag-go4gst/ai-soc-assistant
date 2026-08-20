"""S7 remediation plan findings and artifact metadata."""

from __future__ import annotations

from typing import Any

from app.demo.ec_conflict_s7 import S7_DEVICE

_FOLLOW_UP_BY_STEP = {
    "ask_ot": "ask_ot_team",
    "ingest_ot": "ingest_ot_response",
    "create_incident": "create_incident_ticket",
    "cmdb_correction": "recommend_cmdb_correction",
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
        "ask_ot": (
            "Queued — email OT_TEAM (HIL)",
            "Drafting OT coordination email…",
            "OT team notification prepared / sent after approval",
        ),
        "ingest_ot": (
            "Queued — ingest OT team reply",
            "Ingesting fixture-backed OT reply…",
            "OT team confirms device is active; CMDB stale",
        ),
        "create_incident": (
            "Queued — create OT unauthorized-access incident",
            "Opening security incident…",
            "Incident INC-OT-14 opened — active device, stale CMDB",
        ),
        "cmdb_correction": (
            "Queued — open CMDB data-quality ticket",
            "Opening CMDB correction ticket…",
            "CMDB data-quality ticket CHG-CMDB-14 opened",
        ),
        "closure": (
            "Queued — generate closure summary",
            "Writing closure summary…",
            "Closed: real concern after conflict resolution — not Splunk-alone",
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
        "headlines_by_status": {
            "QUEUED": queued,
            "RUNNING": running,
            "COMPLETE": complete,
            "VALIDATED": queued.replace("Queued —", "Validated —"),
        },
        "attention_state": "NORMAL",
        "email_extra": {"logical_recipient": "OT_TEAM"} if step_id == "ask_ot" else None,
        "ticket_detail": {"id": "INC-OT-14"} if step_id == "create_incident" else (
            {"id": "CHG-CMDB-14"} if step_id == "cmdb_correction" else None
        ),
    }


def enrich_remediation_steps(
    steps: list[dict[str, Any]],
    *,
    normalized: dict[str, Any],
    applied: list[str],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for step in steps:
        finding = finding_for_remediation_step(
            str(step["id"]),
            status=str(step.get("status") or "QUEUED"),
            normalized=normalized,
            applied=applied,
        )
        enriched.append({**step, "finding": finding, "result": (finding or {}).get("headline_finding")})
    return enriched


def build_s7_remediation_summary(*, selected_count: int, total_count: int) -> dict[str, Any]:
    return {
        "title": "Remediation plan ready",
        "steps_completed": 0,
        "steps_total": selected_count,
        "plan_steps": f"{selected_count}/{total_count} selected",
        "metrics": [
            {"label": "Device", "value": S7_DEVICE},
            {"label": "HIL actions", "value": 1},
            {"label": "ITSM", "value": 2},
        ],
    }


def build_s7_remediation_conclusion(*, normalized: dict[str, Any]) -> dict[str, Any]:
    path_b = bool(normalized.get("recycled_identity"))
    if path_b:
        return {
            "title": "Remediation approach",
            "headline": "No security incident — correct identity reuse / CMDB process.",
            "narrative_points": [
                "Do not open a compromise incident for a recycled asset tag.",
                "Open a CMDB data-quality ticket so the retired identity cannot keep generating alerts.",
            ],
        }
    return {
        "title": "Remediation approach",
        "headline": (
            f"Treat {S7_DEVICE} as an active OT asset with a stale CMDB row — incident after OT confirmation, not from Splunk alone."
        ),
        "narrative_points": [
            "Ask OT_TEAM (HIL email) whether OT-RTU-14 was never decommissioned.",
            "Ingest the fixture-backed reply before minting the security incident.",
            "Open INC-OT-14 only because inventory shows the device active.",
            "Open a CMDB data-quality ticket so retirement cannot keep conflicting with live telemetry.",
        ],
    }
