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
        "Whether the three permitted sessions are expected MCP business traffic",
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
                {"label": "Identity", "value": "Registered MCP endpoint" if identity_done else "Pending"},
                {"label": "Malicious use", "value": "Not confirmed"},
                {"label": "SOP", "value": "14-day monitoring" if sop_done else "—"},
            ],
        },
        "outstanding_uncertainty": unconfirmed,
        "missing_evidence": [],
        "llm_advisory": advisory,
        "investigation_conclusion": {
            "headline": (
                "Newly observed registered MCP endpoint · 3 permitted jump-host sessions remain "
                "unexplained · malicious use not confirmed"
            ),
            "narrative_points": [
                (
                    "What happened: Firewall communication with three internal systems in the last 30 days. "
                    f"Only jump host {_JUMP} permitted traffic (3 allowed / 922 denied, ports 443/8443); "
                    "the other two hosts are deny-only. Prior 30-day window is empty."
                ),
                (
                    "Authentication: Successful svc_jump_ops logons exist, but available evidence does not "
                    "attribute them to this source IP. Firewall allow is not authenticated compromise."
                ),
                (
                    "Threat intelligence: Not present in local IOC / threat-intelligence evidence. "
                    "Unlisted does not mean benign."
                ),
                (
                    "Detection: Current IOC-based Splunk content did not cover this IP "
                    "(Existing IOC detection: No alert — IP not present in the IOC list used by this detection). "
                    "No alert is not proof the IP is safe."
                ),
                "Identity: inventory confirms a registered/new MCP endpoint.",
                (
                    "SOP: targeted monitoring for 14 days. Blocking threshold is currently not met "
                    "(requires attributable auth, confirmed malice, or policy exception plus Network/SOC HIL)."
                ),
                f"Agent assessment: {advisory['interpretation']}",
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
