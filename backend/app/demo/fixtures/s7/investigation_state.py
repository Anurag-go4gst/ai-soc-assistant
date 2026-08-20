"""Normalized S7 investigation state — feeds remediation copy."""

from __future__ import annotations

from typing import Any

from app.demo.ec_conflict_s7 import S7_DEVICE


def build_s7_normalized_investigation_state(
    *,
    applied: list[str],
    agent_state: dict[str, Any],
    outcome: dict[str, Any],
    investigation_steps: list[dict[str, Any]],
) -> dict[str, Any]:
    del agent_state
    path = outcome.get("path")
    inventory_done = "check_ot_inventory" in applied
    fw_done = "check_firewall_activity" in applied
    arp_done = "check_arp_mac" in applied
    stale_done = "confirm_stale_identity" in applied
    path_b = path == "B" or (stale_done and not inventory_done)
    device_active = bool(inventory_done and not path_b)

    completed = sum(
        1
        for step in investigation_steps
        if step.get("selected", True) and str(step.get("status") or "").upper() == "COMPLETE"
    )
    total = sum(1 for step in investigation_steps if step.get("selected", True))

    if path_b:
        headline = (
            f"Not an incident: {S7_DEVICE} identity was recycled. Splunk telemetry is not a live-device compromise."
        )
        narrative = [
            "Splunk unauthorized-access telemetry exists, but it is tied to a recycled asset tag.",
            "CMDB retirement is consistent with the recycled identity.",
            "No active compromise on a live OT device — data-quality correction is the right ticket, not a security incident.",
        ]
        unconfirmed: list[str] = []
    elif device_active:
        headline = (
            f"Real concern: {S7_DEVICE} is active and CMDB is stale. Splunk unauthorized access is not a retired-asset false alarm."
        )
        narrative = [
            "Splunk unauthorized-access telemetry for OT-RTU-14 / 10.80.4.14 is confirmed.",
            "CMDB still lists the device as retired — that record is stale, not proof the asset is gone.",
            "OT inventory shows the device active on cell 4; firewall allow and ARP/MAC still answer in the same window.",
            "Do not skip OT confirmation, but Splunk-alone was already the wrong close — this is not a false alarm from a retired box.",
        ]
        unconfirmed = ["Whether unauthorized access is malicious vs mis-documented maintenance"]
    else:
        headline = (
            "Unresolved conflict: Splunk shows activity, CMDB says retired. Splunk alone does not make this an incident."
        )
        narrative = [
            "Splunk unauthorized-access telemetry and the CMDB retirement record currently conflict.",
            "Independent OT inventory and network evidence are required before incident or data-quality actions.",
        ]
        unconfirmed = [
            "Whether the device is actually active",
            "Whether telemetry belongs to a recycled identity",
            "Whether this is a real incident",
        ]

    missing: list[str] = []
    if not inventory_done and not stale_done:
        missing.append("OT inventory")
    if not fw_done:
        missing.append("Firewall segmentation")
    if not arp_done:
        missing.append("Switch ARP/MAC")

    return {
        "device": S7_DEVICE,
        "path": path or ("B" if path_b else "A" if device_active else None),
        "device_active": device_active,
        "cmdb_stale": device_active,
        "recycled_identity": path_b,
        "forced_incident": False,
        "disposition": outcome.get("disposition") or "unresolved_conflict",
        "investigation_summary": {
            "title": "Investigation complete",
            "steps_completed": completed,
            "steps_total": total,
            "metrics": [
                {"label": "Splunk telemetry", "value": "Present"},
                {"label": "CMDB", "value": "Retired" if not path_b else "Retired (consistent)"},
                {"label": "OT inventory", "value": "Active" if device_active else ("Recycled" if path_b else "—")},
                {"label": "Incident from Splunk alone", "value": "Blocked"},
            ],
        },
        "outstanding_uncertainty": unconfirmed,
        "missing_evidence": missing,
        "investigation_conclusion": {
            "headline": headline,
            "narrative_points": narrative,
        },
        "outcome_confirmed": list(outcome.get("confirmed") or []),
    }


def enrich_finding_metadata(finding: dict[str, Any] | None, *, step_id: str) -> dict[str, Any] | None:
    if not finding:
        return None
    return finding
