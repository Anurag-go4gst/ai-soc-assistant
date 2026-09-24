"""Normalized S1 investigation state — feeds remediation copy."""

from __future__ import annotations

from typing import Any

from app.demo.ec_mcp_lifecycle_fixture import PRIMARY_ATTACKER_IP
from app.demo.fixtures.s1.llm_advisory import advisory_payload

_JUMP = "10.20.1.10"


def build_s1_normalized_investigation_state(
    *,
    applied: list[str],
    agent_state: dict[str, Any],
    outcome: dict[str, Any],
    investigation_steps: list[dict[str, Any]],
) -> dict[str, Any]:
    notable_done = "review_existing_notable" in applied
    ti_done = "check_threat_intel" in applied
    sop_done = "retrieve_sop" in applied
    identity_done = "lookup_inventory_identity" in applied or notable_done
    permitted_done = bool(agent_state.get("adaptation_added")) or "investigate_permitted_sessions" in applied

    completed = sum(
        1
        for step in investigation_steps
        if step.get("selected", True) and str(step.get("status") or "").upper() == "COMPLETE"
    )
    total = sum(1 for step in investigation_steps if step.get("selected", True) or step.get("added_by_agent"))

    unconfirmed = [
        "Whether the three permitted sessions are expected partner business traffic",
        "Whether successful authentication can be attributed to this IP",
        "Whether malicious use is occurring",
    ]

    advisory = advisory_payload()
    block_threshold_met = False

    return {
        "indicator": PRIMARY_ATTACKER_IP,
        "notable_fired": False,
        "newly_observed": True,
        "mcp_endpoint": identity_done,
        "malicious_confirmed": False,
        "block_threshold_met": block_threshold_met,
        "jump_host": _JUMP,
        "investigation_summary": {
            "title": "Investigation complete",
            "steps_completed": completed,
            "steps_total": total,
            "metrics": [
                {"label": "Existing IOC detection", "value": "No alert" if notable_done else "—"},
                {"label": "Permitted sessions", "value": "3 on jump host"},
                {"label": "Local TI", "value": "Unlisted" if ti_done else "—"},
                {"label": "Identity", "value": "Registered partner integration endpoint" if identity_done else "Pending"},
                {"label": "Malicious use", "value": "Not confirmed"},
                {"label": "SOP", "value": "14-day monitoring" if sop_done else "—"},
            ],
        },
        "outstanding_uncertainty": unconfirmed,
        "missing_evidence": [],
        "llm_advisory": advisory,
        "investigation_conclusion": {
            "headline": (
                "Not confirmed malicious. The IP is a registered partner integration endpoint, but the firewall "
                "allowed 3 of its sessions to the jump host, and they remain unexplained."
            ),
            "narrative_points": [
                f"What happened: new in the last 30 days — 3 allowed and 922 denied by the firewall, the allowed ones all to jump host {_JUMP} on 443/8443.",
                "Logons: svc_jump_ops logged on to the jump host in the same period, but we can't tie those logons to this IP.",
                "Threat intel: not listed, and our IOC detection didn't fire — it only knows listed IPs.",
                "SOP: watch it for 14 days. Blocking needs attributable logons or confirmed malice, plus Network/SOC approval.",
            ],
        },
        "outcome_confirmed": list(outcome.get("confirmed") or []),
        "permitted_done": permitted_done,
    }


def enrich_finding_metadata(finding: dict[str, Any] | None, *, step_id: str) -> dict[str, Any] | None:
    if not finding:
        return None
    attention = finding.get("attention_state") or "NORMAL"
    if step_id == "mcp_identity":
        attention = "RISK"
    elif step_id in {"requested_30d", "novelty_window", "permitted_sessions"}:
        attention = finding.get("attention_state") or "ATTENTION"
    elif step_id in {"evaluate_notable", "threat_intel", "retrieve_sop"}:
        attention = finding.get("attention_state") or "INFORMATIONAL"
    return {**finding, "attention_state": attention}
