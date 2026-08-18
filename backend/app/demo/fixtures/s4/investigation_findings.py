"""S4 investigation step findings — derived from EC fixture evidence only."""

from __future__ import annotations

from typing import Any

from app.demo.ec_siem_s4 import S4_ADVISORY_ID, S4_DETECTION_SEARCH_NAME, S4_GAP_CANDIDATE_SPL

# Canonical inventory — all internet-facing EdgeGate VPN gateways in the fixture estate.
S4_INTERNET_FACING_GATEWAYS: tuple[dict[str, Any], ...] = (
    {"asset": "VPN-GW-01", "site": "DC-A", "role": "internet-facing", "version": "12.3", "affected": True, "active_sessions": 142},
    {"asset": "VPN-GW-02", "site": "DC-B", "role": "internet-facing", "version": "12.3", "affected": True, "active_sessions": 98},
    {"asset": "VPN-GW-03", "site": "DR", "role": "internet-facing", "version": "13.0", "affected": False, "active_sessions": 61},
    {"asset": "VPN-GW-04", "site": "branch-hub", "role": "internet-facing", "version": "13.0", "affected": False, "active_sessions": 37},
    {"asset": "VPN-GW-05", "site": "DC-A", "role": "internet-facing", "version": "12.3", "affected": True, "active_sessions": 88},
    {"asset": "VPN-GW-06", "site": "branch-east", "role": "internet-facing", "version": "13.1", "affected": False, "active_sessions": 44},
    {"asset": "VPN-GW-07", "site": "DR", "role": "internet-facing", "version": "13.0", "affected": False, "active_sessions": 29},
    {"asset": "VPN-GW-08", "site": "DC-B", "role": "internet-facing", "version": "12.4", "affected": True, "active_sessions": 76},
    {"asset": "VPN-GW-09", "site": "branch-west", "role": "internet-facing", "version": "13.0", "affected": False, "active_sessions": 33},
    {"asset": "VPN-GW-10", "site": "branch-north", "role": "internet-facing", "version": "12.5", "affected": False, "active_sessions": 21},
    {"asset": "VPN-GW-11", "site": "DR", "role": "internet-facing", "version": "13.0", "affected": False, "active_sessions": 18},
    {"asset": "VPN-GW-12", "site": "branch-south", "role": "internet-facing", "version": "13.0", "affected": False, "active_sessions": 25},
)

S4_AFFECTED_ASSETS = [row["asset"] for row in S4_INTERNET_FACING_GATEWAYS if row["affected"]]
S4_ANOMALOUS_AUTH_GATEWAYS = ("VPN-GW-01", "VPN-GW-02")

S4_REUSABLE_SPLUNK_ANALYTIC = {
    "name": "VPN_Mgmt_Plane_Anomaly_Baseline",
    "object_type": "saved_search",
    "purpose": "Management-plane authentication baseline (not advisory-specific)",
    "coverage": "PARTIAL",
}

S4_SOAR_RELATED_PLAYBOOKS = (
    {"id": "PB-EMERG-VPN-MAINT", "name": "VPN maintenance window emergency change"},
    {"id": "PB-EDGE-PATCH", "name": "Edge appliance emergency patching"},
)

S4_IR_CONTROLS = (
    "Disable WAN management listener on affected gateways",
    "Restrict control plane to management VRF",
    "Require step-up MFA for active and new VPN sessions",
)

S4_IOC_HUNT_WINDOW = "last 7 days"


def _network_assessed(applied: list[str]) -> bool:
    return "run_network_assessment" in applied or (
        "list_affected_assets" in applied and "check_gateway_versions" in applied
    )


def _splunk_hunt_done(applied: list[str]) -> bool:
    return "run_splunk_ioc_hunt" in applied and "search_exploitation_indicators" in applied


def _step_prerequisite_met(step_id: str, applied: list[str]) -> bool:
    if step_id == "identify_gateways":
        return _network_assessed(applied)
    if step_id == "check_versions":
        return _network_assessed(applied)
    if step_id in {"hunt_iocs", "auth_anomalies", "auth_deep_dive"}:
        return _splunk_hunt_done(applied)
    if step_id == "splunk_detections":
        return "show_advisory" in applied
    if step_id == "soar_playbooks":
        return "check_soar_playbooks" in applied
    if step_id == "ir_guidance":
        return "show_incident_response_plan" in applied and "show_hardening_guidance" in applied
    if step_id == "agilus_patch_analysis":
        return "check_agilus_patch" in applied
    return False


def _skipped_reason(step_id: str, *, status: str, selected: bool, agent_state: dict[str, Any]) -> str | None:
    if status != "SKIPPED":
        return None
    if not selected:
        return "Not included in the approved investigation plan."
    if step_id == "agilus_patch_analysis":
        decision = agent_state.get("agilus_analysis_decision") or agent_state.get("vuln_scan_decision")
        if decision == "skipped":
            return "Analyst continued without Agilus MCP version/patch cross-reference."
        return "Optional Agilus MCP analysis was not approved."
    if step_id == "auth_deep_dive" and not agent_state.get("adaptation_added"):
        return "Agent adaptation not triggered — baseline Splunk hunt did not require a follow-on search."
    if step_id == "auth_anomalies" and agent_state.get("adaptation_added"):
        return "Superseded by agent-added privileged management correlation step."
    return "Prerequisite evidence for this step was not collected."


def finding_for_investigation_step(
    step_id: str,
    *,
    status: str,
    applied: list[str],
    agent_state: dict[str, Any],
    outcome: dict[str, Any],
    selected: bool,
) -> dict[str, Any] | None:
    """Return structured finding for a step, or skip metadata only — never fabricate COMPLETE findings."""
    if status == "FAILED":
        return {
            "headline_finding": "Step failed — findings not produced",
            "key_evidence": [],
            "affected_entities": [],
            "quantitative_summary": {},
            "confidence": "none",
            "caveat": "Failed steps cannot be treated as successfully investigated.",
            "evidence_sources": [],
            "details": {"failure_note": "Execution did not complete; no findings attributed to this step."},
        }

    if status == "SKIPPED":
        reason = _skipped_reason(step_id, status=status, selected=selected, agent_state=agent_state)
        if step_id == "auth_anomalies" and agent_state.get("adaptation_added"):
            reason = "Superseded by agent-added privileged management correlation step."
        return {
            "headline_finding": f"Skipped — {reason}",
            "key_evidence": [],
            "affected_entities": [],
            "quantitative_summary": {},
            "confidence": "none",
            "caveat": "Skipped steps do not produce attributable findings.",
            "evidence_sources": [],
            "details": {"skip_reason": reason},
        }

    if status not in {"COMPLETE", "RUNNING"}:
        return None

    if status == "RUNNING":
        return {
            "headline_finding": "Running…",
            "key_evidence": [],
            "affected_entities": [],
            "quantitative_summary": {},
            "confidence": "pending",
            "caveat": "Finding summary will be available when the step completes.",
            "evidence_sources": [],
            "details": {},
        }

    if not _step_prerequisite_met(step_id, applied):
        return None

    total = len(S4_INTERNET_FACING_GATEWAYS)
    affected = len(S4_AFFECTED_ASSETS)

    if step_id == "identify_gateways":
        return {
            "headline_finding": f"{total} internet-facing gateways found · {affected} in affected scope",
            "key_evidence": [
                f"CMDB returned {total} internet-facing EdgeGate VPN assets",
                f"{affected} gateways tagged in-scope for advisory {S4_ADVISORY_ID}",
            ],
            "affected_entities": list(S4_AFFECTED_ASSETS),
            "quantitative_summary": {
                "internet_facing_total": total,
                "in_advisory_scope": affected,
                "active_sessions": sum(int(row["active_sessions"]) for row in S4_INTERNET_FACING_GATEWAYS),
            },
            "confidence": "high",
            "caveat": "Inventory scope is internet-facing VPN gateways only; internal-only appliances are out of scope.",
            "evidence_sources": [
                {"source": "CMDB MCP", "evidence_id": "ev-s4-cmdb", "provenance": "simulated_mcp", "tool": "cmdb_list_assets"},
            ],
            "details": {
                "affected_assets": [dict(row) for row in S4_INTERNET_FACING_GATEWAYS],
                "investigation_window": "point-in-time inventory snapshot",
            },
        }

    if step_id == "check_versions":
        affected_list = ", ".join(S4_AFFECTED_ASSETS)
        return {
            "headline_finding": f"{affected} affected · {affected_list}",
            "key_evidence": [
                "EdgeGate 12.3 on VPN-GW-01, VPN-GW-02, VPN-GW-05",
                "EdgeGate 12.4 on VPN-GW-08 (within advisory affected range 12.1–12.4)",
                "Remaining gateways on 12.5+ or 13.x — not in affected range",
            ],
            "affected_entities": list(S4_AFFECTED_ASSETS),
            "quantitative_summary": {
                "version_probes": total,
                "affected_firmware": affected,
                "not_affected": total - affected,
            },
            "confidence": "high",
            "caveat": "Vulnerable firmware is not the same as confirmed compromise.",
            "evidence_sources": [
                {"source": "Device MCP", "evidence_id": "ev-s4-versions", "provenance": "simulated_mcp", "tool": "device_version_probe"},
            ],
            "details": {
                "relevant_values": {row["asset"]: row["version"] for row in S4_INTERNET_FACING_GATEWAYS},
                "affected_assets": [row["asset"] for row in S4_INTERNET_FACING_GATEWAYS if row["affected"]],
            },
        }

    if step_id == "hunt_iocs":
        return {
            "headline_finding": (
                "No known exploitation IoCs matched in the governed 7-day window · "
                "management-plane activity triggered deeper review"
            ),
            "key_evidence": [
                "0 matches for advisory WAN management-session IOC pattern",
                "0 confirmed exploitation telemetry events in reviewed window",
                "Governed gap SPL validated and executed via Splunk MCP",
            ],
            "affected_entities": [],
            "quantitative_summary": {
                "ioc_hits": 0,
                "exploitation_events": 0,
                "search_window_days": 7,
            },
            "confidence": "medium",
            "caveat": (
                "No IoCs found means no matches within the searched evidence and time window — "
                "not proof of no compromise."
            ),
            "evidence_sources": [
                {"source": "Splunk MCP", "evidence_id": "ev-s4-ioc-hunt", "provenance": "simulated_mcp", "tool": "splunk_run_query"},
            ],
            "details": {
                "investigation_window": S4_IOC_HUNT_WINDOW,
                "important_events": [],
                "spl_reference": S4_GAP_CANDIDATE_SPL,
            },
        }

    if step_id == "auth_anomalies":
        return {
            "headline_finding": (
                "2 gateways anomalous · VPN-GW-01 and VPN-GW-02 · "
                "privileged management activity requires deeper compromise review"
            ),
            "key_evidence": [
                "6 privileged management-auth events exceed baseline on VPN-GW-01 and VPN-GW-02",
                "Events cluster around WAN-originated management-session attempts",
                "No successful exploitation chain confirmed in the same window",
            ],
            "affected_entities": list(S4_ANOMALOUS_AUTH_GATEWAYS),
            "quantitative_summary": {
                "anomalous_gateways": len(S4_ANOMALOUS_AUTH_GATEWAYS),
                "privileged_auth_events": 6,
                "search_window_days": 7,
            },
            "confidence": "medium",
            "caveat": "Anomalous authentication warrants deeper review; it is not confirmed compromise.",
            "evidence_sources": [
                {"source": "Splunk MCP", "evidence_id": "ev-s4-auth-anomalies", "provenance": "simulated_mcp", "tool": "splunk_run_query"},
            ],
            "details": {
                "investigation_window": S4_IOC_HUNT_WINDOW,
                "important_events": [
                    {"gateway": "VPN-GW-01", "event": "privileged_mgmt_auth_spike", "count": 4, "src_sample": "203.0.113.14"},
                    {"gateway": "VPN-GW-02", "event": "privileged_mgmt_auth_spike", "count": 2, "src_sample": "198.51.100.8"},
                ],
            },
        }

    if step_id == "auth_deep_dive":
        reason = agent_state.get("adaptation_added")
        return {
            "headline_finding": "6 anomalous events across 2 gateways · deeper compromise review recommended",
            "key_evidence": [
                "Agent added step because IOC hunt surfaced management-plane auth anomalies",
                "Correlated 6 events to privileged admin tokens minted outside change window",
            ],
            "affected_entities": list(S4_ANOMALOUS_AUTH_GATEWAYS),
            "quantitative_summary": {"correlated_events": 6, "gateways": 2},
            "confidence": "medium",
            "caveat": reason and "Added by agent after Splunk hunt — not part of the original seven-step plan.",
            "evidence_sources": [
                {"source": "Splunk MCP", "evidence_id": "ev-s4-auth-anomalies", "provenance": "simulated_mcp", "tool": "splunk_run_query"},
            ],
            "details": {
                "agent_reason": "Splunk hunt surfaced unusual management authentication on VPN-GW-01 and VPN-GW-02.",
                "investigation_window": S4_IOC_HUNT_WINDOW,
            },
        }

    if step_id == "splunk_detections":
        return {
            "headline_finding": "No advisory-specific detection · 1 reusable management-plane analytic found",
            "key_evidence": [
                f"No Splunk detection or saved search maps to {S4_ADVISORY_ID}",
                f"Reusable analytic: {S4_REUSABLE_SPLUNK_ANALYTIC['name']} (management-plane baseline)",
            ],
            "affected_entities": [],
            "quantitative_summary": {
                "advisory_specific_detections": 0,
                "reusable_analytics": 1,
            },
            "confidence": "high",
            "caveat": "Absence of threat-specific content is a valid outcome for a new zero-day advisory.",
            "evidence_sources": [
                {"source": "Splunk MCP", "evidence_id": "ev-s4-siem-check", "provenance": "simulated_mcp", "tool": "splunk_get_knowledge_objects"},
            ],
            "details": {
                "reusable_analytics": [S4_REUSABLE_SPLUNK_ANALYTIC],
                "missing_detection": S4_DETECTION_SEARCH_NAME,
            },
        }

    if step_id == "soar_playbooks":
        names = " · ".join(pb["name"] for pb in S4_SOAR_RELATED_PLAYBOOKS)
        return {
            "headline_finding": f"No VPN zero-day playbook · {len(S4_SOAR_RELATED_PLAYBOOKS)} related emergency runbooks available",
            "key_evidence": [
                "VPN zero-day playbook: not found in registry",
                f"Related runbooks: {names}",
            ],
            "affected_entities": [],
            "quantitative_summary": {
                "vpn_zero_day_playbooks": 0,
                "related_emergency_runbooks": len(S4_SOAR_RELATED_PLAYBOOKS),
            },
            "confidence": "high",
            "caveat": "Missing playbook is expected for a new advisory — adapt related emergency runbooks.",
            "evidence_sources": [
                {"source": "SOAR registry", "evidence_id": "ev-s4-soar-playbooks", "provenance": "simulated_mcp", "tool": "soar_list_playbooks"},
            ],
            "details": {"related_playbooks": list(S4_SOAR_RELATED_PLAYBOOKS)},
        }

    if step_id == "ir_guidance":
        return {
            "headline_finding": "Sev-1 IR procedure + 3 temporary containment controls retrieved",
            "key_evidence": [
                "Governed Sev-1 IR checklist retrieved from SOC-KB",
                "Three temporary compensating controls identified for affected gateways",
            ],
            "affected_entities": list(S4_AFFECTED_ASSETS),
            "quantitative_summary": {
                "ir_procedures": 1,
                "temporary_controls": len(S4_IR_CONTROLS),
            },
            "confidence": "high",
            "caveat": "Guidance is fixture SOC-KB content — not vendor-signed production runbooks.",
            "evidence_sources": [
                {"source": "SOC-KB RAG", "evidence_id": "ev-s4-ir-plan", "provenance": "ec_scenario_policy"},
                {"source": "SOC-KB RAG", "evidence_id": "ev-s4-hardening", "provenance": "ec_scenario_policy"},
            ],
            "details": {
                "temporary_controls": list(S4_IR_CONTROLS),
                "ir_plan": "EdgeGate VPN zero-day — emergency IR checklist",
            },
        }

    if step_id == "agilus_patch_analysis":
        return {
            "headline_finding": "Outdated builds confirmed · emergency patch EG-VPN-12.3.5-EMERG applies to VPN-GW-01/02/05/08",
            "key_evidence": [
                "Agilus matched EdgeGate 12.3/12.4 builds to emergency bulletin EG-VPN-12.3.5-EMERG",
                "Installed versions on four in-scope gateways are behind vendor-recommended emergency fix",
                "Patch job not submitted — governed approval still required for Agilus execution",
            ],
            "affected_entities": list(S4_AFFECTED_ASSETS),
            "quantitative_summary": {
                "assets_checked": 4,
                "outdated_builds": 4,
                "emergency_patches_matched": 1,
            },
            "confidence": "high",
            "caveat": "Agilus confirms patch eligibility — it does not prove compromise or exploitation.",
            "evidence_sources": [
                {"source": "Agilus MCP", "evidence_id": "ev-s4-agilus-analysis", "provenance": "simulated_mcp", "tool": "agilus_analyze_assets"},
            ],
            "details": {
                "patch_id": "EG-VPN-12.3.5-EMERG",
                "patch_title": "Emergency control-plane hardening for EdgeGate 12.1–12.4",
                "affected_assets": list(S4_AFFECTED_ASSETS),
            },
        }

    return None


def build_s4_investigation_conclusion(
    *,
    applied: list[str],
    agent_state: dict[str, Any],
    outcome: dict[str, Any],
    investigation_steps: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Synthesize investigation conclusion from completed step findings only."""
    complete_steps = [
        step
        for step in investigation_steps
        if step.get("selected", True)
        and str(step.get("status") or "").upper() == "COMPLETE"
        and isinstance(step.get("finding"), dict)
        and step["finding"].get("headline_finding")
        and not str(step["finding"]["headline_finding"]).startswith("Skipped")
    ]
    if not complete_steps:
        return None

    affected = len(S4_AFFECTED_ASSETS)
    anomalous = len(S4_ANOMALOUS_AUTH_GATEWAYS)
    total = len(S4_INTERNET_FACING_GATEWAYS)

    headline = f"{affected} gateways are vulnerable; {anomalous} require deeper compromise review."
    narrative_points = [
        (
            f"Four of {total} internet-facing VPN gateways run affected firmware "
            f"({', '.join(S4_AFFECTED_ASSETS)})."
        ),
        "No known IoCs matched within the reviewed 7-day Splunk telemetry.",
        f"{', '.join(S4_ANOMALOUS_AUTH_GATEWAYS)} show anomalous privileged management activity.",
        "Compromise is not confirmed; immediate containment and patching of the four vulnerable gateways is recommended.",
    ]

    findings = [str(step["finding"]["headline_finding"]) for step in complete_steps if step.get("finding")]

    return {
        "title": "Investigation conclusion",
        "headline": headline,
        "narrative_points": narrative_points,
        "exposure": str(outcome.get("exposure") or "PARTIAL"),
        "compromise": "NOT CONFIRMED",
        "confidence": 82,
        "findings": findings,
        "evidence_summary": [
            {
                "source": src["source"],
                "detail": src.get("evidence_id") or src.get("tool") or "",
                "provenance": src.get("provenance") or "SIMULATED",
            }
            for step in complete_steps
            for src in (step.get("finding") or {}).get("evidence_sources") or []
        ][:8],
    }
