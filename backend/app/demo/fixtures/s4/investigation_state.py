"""Normalized S4 investigation state — single source of truth for EC agent UI."""

from __future__ import annotations

from typing import Any

from app.demo.fixtures.s4.investigation_findings import (
    S4_AFFECTED_ASSETS,
    S4_ANOMALOUS_AUTH_GATEWAYS,
    S4_INTERNET_FACING_GATEWAYS,
    S4_IOC_HUNT_WINDOW,
    build_s4_investigation_conclusion,
)

S4_PATCH_ID = "EG-VPN-12.3.5-EMERG"
S4_INTERNET_FACING_COUNT = len(S4_INTERNET_FACING_GATEWAYS)
S4_AFFECTED_COUNT = len(S4_AFFECTED_ASSETS)
S4_ANOMALOUS_COUNT = len(S4_ANOMALOUS_AUTH_GATEWAYS)


def _splunk_hunt_done(applied: list[str]) -> bool:
    return "run_splunk_ioc_hunt" in applied and "search_exploitation_indicators" in applied


def build_s4_normalized_investigation_state(
    *,
    applied: list[str],
    agent_state: dict[str, Any],
    outcome: dict[str, Any],
    investigation_steps: list[dict[str, Any]],
) -> dict[str, Any]:
    hunt_done = _splunk_hunt_done(applied)
    agilus_done = "check_agilus_patch" in applied

    vulnerable_sessions = sum(
        int(row["active_sessions"])
        for row in S4_INTERNET_FACING_GATEWAYS
        if row["affected"]
    )

    unconfirmed: list[str] = []
    if hunt_done:
        unconfirmed.append(
            "Whether anomalous privileged management activity on VPN-GW-01 and VPN-GW-02 "
            "represents successful exploitation."
        )
        unconfirmed.append(
            "Whether exploitation occurred outside the reviewed Splunk telemetry window."
        )
    else:
        unconfirmed.extend(
            item
            for item in (outcome.get("unconfirmed") or [])
            if "exploitation" in str(item).lower() or "compromise" in str(item).lower()
        )

    missing: list[str] = []
    if not agilus_done:
        missing.append("Agilus MCP patch-catalog cross-reference (optional)")
    if not hunt_done:
        missing.append("Governed Splunk exploitation-indicator hunt")

    conclusion = build_s4_investigation_conclusion(
        applied=applied,
        agent_state=agent_state,
        outcome=outcome,
        investigation_steps=investigation_steps,
    )

    return {
        "internet_facing_count": S4_INTERNET_FACING_COUNT,
        "affected_version_count": S4_AFFECTED_COUNT,
        "anomalous_gateway_count": S4_ANOMALOUS_COUNT if hunt_done else 0,
        "known_ioc_match_count": 0 if hunt_done else None,
        "affected_asset_ids": list(S4_AFFECTED_ASSETS),
        "anomalous_asset_ids": list(S4_ANOMALOUS_AUTH_GATEWAYS) if hunt_done else [],
        "patch_id": S4_PATCH_ID,
        "patch_scope_asset_ids": list(S4_AFFECTED_ASSETS) if agilus_done else [],
        "compromise_status": "not_confirmed",
        "exposure_status": "partial",
        "splunk_window": S4_IOC_HUNT_WINDOW if hunt_done else None,
        "vulnerable_active_sessions": vulnerable_sessions if hunt_done else None,
        "investigation_summary": {
            "title": "Investigation complete",
            "steps_completed": sum(
                1
                for step in investigation_steps
                if step.get("selected", True) and str(step.get("status") or "").upper() == "COMPLETE"
            ),
            "steps_total": sum(1 for step in investigation_steps if step.get("selected", True)),
            "metrics": [
                {"label": "Internet-facing", "value": S4_INTERNET_FACING_COUNT},
                {"label": "Vulnerable", "value": S4_AFFECTED_COUNT},
                {"label": "Anomalous", "value": S4_ANOMALOUS_COUNT if hunt_done else 0},
                {"label": "Known IoCs", "value": 0 if hunt_done else "—"},
            ],
        },
        "outstanding_uncertainty": unconfirmed,
        "missing_evidence": missing,
        "investigation_conclusion": conclusion,
    }


def enrich_finding_metadata(finding: dict[str, Any] | None, *, step_id: str) -> dict[str, Any] | None:
    if not finding:
        return None
    attention = "NORMAL"
    if step_id in {"auth_anomalies", "auth_deep_dive"}:
        attention = "ATTENTION"
    elif step_id == "hunt_iocs":
        attention = "NO_MATCH"
    elif step_id in {"splunk_detections", "soar_playbooks", "ir_guidance"}:
        attention = "INFORMATIONAL"
    elif step_id == "agilus_patch_analysis":
        attention = "INFORMATIONAL"
    finding = {**finding, "attention_state": attention}
    return finding
