"""S4 — synthetic zero-day with no threat-specific SOAR playbook. EC fixture only."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.demo.ec_siem_s4 import (
    S4_ADVISORY_ID,
    S4_GAP_CANDIDATE_SPL,
    S4_LAYER2_PATH,
    S4_MONITOR_CANDIDATE_SPL,
    S4_MONITOR_SCHEDULE,
    S4_MONITOR_SEARCH_NAME,
    build_s4_action_readiness,
    build_s4_detection_opportunity,
    build_s4_evidence_findings,
    build_s4_investigation_scope,
    build_s4_siem_coverage,
    build_s4_tool_traces,
    s4_gap_spl_validation,
)
from app.demo.ec_journeys import journey_for
from app.demo import ec_email_drafts
from app.demo.fixtures import common as C

S4_SCENARIO_ID = "s4_zero_day_no_playbook"
S4_FAMILY = "s4_zero_day"
S4_QUERY = (
    "A critical zero-day affects our internet-facing VPN gateways. We have no detection rule or "
    "SOAR playbook yet for VPN detection. Determine whether we are exposed and what immediate "
    "controls we should apply."
)
S4_OPENING_BRIEFING = (
    "Addressing a zero-day vulnerability in internet-facing VPN gateways is a critical task that "
    "requires immediate attention and a structured approach. Here's a step-by-step guide to assess "
    "exposure and implement immediate controls using Splunk and other tools."
)
S4_PLAN_STEP_IDS = frozenset(
    {
        "run_network_assessment",
        "run_splunk_ioc_hunt",
        "run_vuln_scan",
        "request_agilus_patch",
        "apply_access_controls",
        "apply_temporary_control",
        "deploy_splunk_monitoring",
        "check_soar_playbooks",
        "show_incident_response_plan",
    }
)
S4_FOLLOWUPS = (
    C.chip("run_investigation", "Run investigation", action=True),
    C.chip("create_remediation_plan", "Yes, create remediation plan", action=True),
    C.chip("decline_remediation_plan", "Not now"),
    C.chip("run_remediation", "Approve remediation", action=True),
    C.chip("approve_investigation_vuln_scan", "Connect Agilus MCP", action=True),
    C.chip("skip_investigation_vuln_scan", "Continue without Agilus"),
    C.chip("update_investigation_plan", "Update investigation plan"),
    C.chip("update_remediation_plan", "Update remediation plan"),
    C.chip("run_network_assessment", "Run network assessment"),
    C.chip("run_splunk_ioc_hunt", "Run Splunk IOC hunt"),
    C.chip("run_vuln_scan", "Run vulnerability scan", action=True),
    C.chip("check_soar_playbooks", "Check SOAR playbooks"),
    C.chip("show_incident_response_plan", "Show IR plan (RAG)"),
    C.chip("apply_access_controls", "Apply access controls", action=True),
    C.chip("deploy_splunk_monitoring", "Prepare Splunk monitoring", action=True),
    C.chip("restrict_vpn_access", "Restrict VPN access", action=True),
    C.chip("enforce_mfa_vpn", "Enforce MFA on VPN", action=True),
    C.chip("request_agilus_patch", "Request patch via Agilus", action=True),
    C.chip("create_emergency_incident", "Create emergency incident", action=True),
    C.chip("create_change_ticket", "Create change ticket", action=True),
    C.chip("notify_network_team", "Notify network team", action=True),
    C.chip("apply_temporary_control", "Apply temporary control", action=True),
    C.chip("verify_temporary_control", "Verify temporary control", action=True),
    C.chip("generate_executive_summary", "Generate executive summary"),
)
S4_FOLLOWUP_IDS = frozenset(item.follow_up_id for item in S4_FOLLOWUPS)

# Plan-first: only open advisory on turn 0; analyst executes each plan step on approval.
S4_PLAN_PREREAD = ("show_advisory",)
S4_AUTO_VERIFY_ON_START: tuple[str, ...] = ()


def _base_outcome() -> dict[str, Any]:
    return {
        "disposition": "partial",
        "exposure": "PARTIAL",
        "exposure_validation": "REQUIRES_VALIDATION",
        "confirmed": [
            "A scenario advisory describes a critical condition in internet-facing VPN gateways",
            "No VPN-specific SOAR playbook is available for this advisory",
        ],
        "supported": ["Investigation can still assemble advisory, inventory, telemetry, and hardening knowledge"],
        "unconfirmed": [
            "Which gateways are running an affected version",
            "Whether any gateway is compromised",
            "Whether exploitation indicators are present",
        ],
        "missing_evidence": ["CMDB VPN inventory", "Device version evidence", "Splunk exploitation search", "Hardening KB"],
        "vulnerable_vs_compromised": "Vulnerable is not the same as compromised",
        "production_investigation_outcome_unused": True,
    }


def _base_state() -> list[dict[str, Any]]:
    return [
        C.state_item("advisory", "Zero-day advisory", "AVAILABLE_NOT_QUERIED", f"{S4_ADVISORY_ID} not opened", "experience_center_fixture"),
        C.state_item("cmdb", "VPN gateway inventory", "MISSING", "CMDB not queried"),
        C.state_item("versions", "Gateway versions", "MISSING", "Device evidence not collected"),
        C.state_item("splunk", "Exploitation indicators", "AVAILABLE_NOT_QUERIED", "Splunk search not run"),
        C.state_item("hardening", "Temporary hardening KB", "AVAILABLE_NOT_QUERIED", "Hardening guidance not opened", "ec_scenario_policy"),
        C.state_item("agilus", "Agilus patch catalog", "AVAILABLE_NOT_QUERIED", "Agilus MCP not queried"),
        C.state_item("soar", "SOAR playbook registry", "AVAILABLE_NOT_QUERIED", "VPN-specific playbook not checked yet"),
    ]


def _apply(applied: list[str], session_id: str, outcome: dict[str, Any], state: list[dict[str, Any]], extra: list[dict[str, Any]]) -> None:
    if "show_advisory" in applied:
        C.set_status(state, "advisory", "OBTAINED", f"{S4_ADVISORY_ID}: EdgeGate VPN 12.1-12.4 unauthenticated control-plane condition")
        extra.append(C.evidence("ev-s4-advisory", "advisory_fixture", "Scenario zero-day advisory", [{
            "advisory_id": S4_ADVISORY_ID,
            "vendor": "Northgate Access",
            "product_family": "EdgeGate VPN",
            "affected_versions": "12.1 through 12.4",
            "exploitation_condition": "Unauthenticated control-plane request to management listener",
            "ioc_or_behavior": "POST /api/v1/mgmt/session from untrusted WAN plus unexpected admin token mint",
            "temporary_mitigation": "Disable WAN management listener; restrict control plane to management VRF",
            "not_a_real_cve": True,
        }], provenance="experience_center_fixture"))
        outcome["missing_evidence"] = [item for item in outcome["missing_evidence"] if "advisory" not in item.lower()]

    if "run_vuln_scan" in applied:
        _s4_append_connected_evidence(extra)
        C.set_status(state, "versions", "OBTAINED", "Vulnerability scanner confirms advisory on VPN-GW-01/02")

    if "check_soar_playbooks" in applied:
        C.set_status(
            state,
            "soar",
            "PARTIAL",
            "VPN zero-day playbook not found; related emergency-response playbooks available",
        )
        extra.append(
            C.evidence(
                "ev-s4-soar-playbooks",
                "soar_fixture",
                "SOAR playbook registry",
                [
                    {
                        "vpn_zero_day_playbook": "not_found",
                        "related_playbooks": [
                            {"id": "PB-EMERG-VPN-MAINT", "name": "VPN maintenance window emergency change", "match": "partial"},
                            {"id": "PB-EDGE-PATCH", "name": "Edge appliance emergency patching", "match": "recommended"},
                            {"id": "PB-IR-SEV1", "name": "Severity-1 incident commander checklist", "match": "recommended"},
                        ],
                        "suggestion": "Adapt PB-EDGE-PATCH + PB-IR-SEV1 until a VPN zero-day playbook is published.",
                    }
                ],
                provenance="simulated_mcp",
                tool_name="soar_list_playbooks",
            )
        )
        outcome["confirmed"] = [
            *[
                item
                for item in outcome["confirmed"]
                if "SOAR playbook" not in item
            ],
            "No VPN-specific SOAR playbook — related emergency playbooks are available to adapt",
        ]

    if "apply_access_controls" in applied:
        C.ensure_hil_action(
            kind="notify",
            label="Restrict VPN access (emergency policy)",
            session_id=session_id,
            scenario_id=S4_SCENARIO_ID,
            extra={
                "control": "restrict_vpn_access",
                "scope": ["VPN-GW-01", "VPN-GW-02"],
                "policy": "Block new remote-access sessions except break-glass accounts pending patch",
            },
        )
        C.ensure_hil_action(
            kind="notify",
            label="Enforce MFA on VPN sessions",
            session_id=session_id,
            scenario_id=S4_SCENARIO_ID,
            extra={
                "control": "enforce_mfa_vpn",
                "scope": ["VPN-GW-01", "VPN-GW-02", "VPN-GW-03", "VPN-GW-04"],
                "policy": "Require step-up MFA for all active and new VPN sessions",
            },
        )

    if "deploy_splunk_monitoring" in applied:
        extra.append(
            C.evidence(
                "ev-s4-splunk-alert",
                "splunk_mcp_fixture",
                "Splunk monitoring alert (candidate)",
                [
                    {
                        "alert_name": S4_MONITOR_SEARCH_NAME,
                        "status": "candidate_prepared_not_deployed",
                        "search": S4_MONITOR_CANDIDATE_SPL,
                        "schedule": S4_MONITOR_SCHEDULE["cron"],
                        "window": S4_MONITOR_SCHEDULE["window"],
                        "trigger": S4_MONITOR_SCHEDULE["trigger"],
                        "throttle": S4_MONITOR_SCHEDULE["throttle"],
                    }
                ],
                provenance="simulated_mcp",
                tool_name="splunk_prepare_alert",
                summary="Scheduled monitoring search prepared (15-min window) — not deployed; deployment requires approval",
            )
        )

    if "list_affected_assets" in applied:
        from app.demo.fixtures.s4.investigation_findings import S4_INTERNET_FACING_GATEWAYS

        C.set_status(state, "cmdb", "OBTAINED", f"{len(S4_INTERNET_FACING_GATEWAYS)} internet-facing VPN gateways in inventory")
        extra.append(C.evidence("ev-s4-cmdb", "cmdb_fixture", "VPN gateway inventory", [
            {
                "asset": row["asset"],
                "role": row["role"],
                "site": row["site"],
                "internet_facing": True,
                "advisory_scope": bool(row["affected"]),
            }
            for row in S4_INTERNET_FACING_GATEWAYS
        ], provenance="simulated_mcp", tool_name="cmdb_list_assets"))
        outcome["missing_evidence"] = [item for item in outcome["missing_evidence"] if "CMDB" not in item]

    if "check_gateway_versions" in applied:
        from app.demo.fixtures.s4.investigation_findings import S4_AFFECTED_ASSETS, S4_INTERNET_FACING_GATEWAYS

        affected_label = "/".join(asset.replace("VPN-GW-", "GW-") for asset in S4_AFFECTED_ASSETS[:2])
        if len(S4_AFFECTED_ASSETS) > 2:
            affected_label = f"{len(S4_AFFECTED_ASSETS)} gateways including {', '.join(S4_AFFECTED_ASSETS)}"
        C.set_status(state, "versions", "OBTAINED", f"{affected_label} on affected firmware (12.3/12.4)")
        extra.append(C.evidence("ev-s4-versions", "device_fixture", "Gateway versions", [
            {
                "asset": row["asset"],
                "version": row["version"],
                "affected": bool(row["affected"]),
                "active_sessions": row["active_sessions"],
            }
            for row in S4_INTERNET_FACING_GATEWAYS
        ], provenance="simulated_mcp", tool_name="device_version_probe"))
        outcome["exposure"] = "PARTIAL"
        outcome["exposure_validation"] = "VERSION_EVIDENCE_APPLIED"
        outcome["confirmed"] = [
            *outcome["confirmed"],
            f"{len(S4_AFFECTED_ASSETS)} internet-facing VPN gateways run an affected firmware version (vulnerable)",
            f"{len(S4_INTERNET_FACING_GATEWAYS) - len(S4_AFFECTED_ASSETS)} gateways are not in the affected version range",
        ]
        outcome["unconfirmed"] = [item for item in outcome["unconfirmed"] if "affected version" not in item] + [
            "Compromise / active exploitation of vulnerable gateways",
        ]
        outcome["missing_evidence"] = [item for item in outcome["missing_evidence"] if "version" not in item.lower()]

    if "check_agilus_patch" in applied:
        C.set_status(
            state,
            "agilus",
            "OBTAINED",
            "Agilus matched emergency patch EG-VPN-12.3.5-EMERG for VPN-GW-01/02/05/08",
        )
        extra.append(
            C.evidence(
                "ev-s4-agilus-analysis",
                "agilus_mcp_fixture",
                "Agilus patch analysis",
                [
                    {
                        "product": "Northgate EdgeGate VPN",
                        "installed_version": "12.3",
                        "patch_id": "EG-VPN-12.3.5-EMERG",
                        "patch_title": "Emergency control-plane hardening for 12.1–12.4",
                        "targets": ["VPN-GW-01", "VPN-GW-02", "VPN-GW-05", "VPN-GW-08"],
                        "removes_vulnerabilities": [S4_ADVISORY_ID, "CVE-FIXTURE-EDGEGATE-CTRL"],
                        "method": "version_catalog_match",
                        "vendor_assets_checked": 4,
                    }
                ],
                provenance="simulated_mcp",
                tool_name="agilus_analyze_assets",
                summary="Agilus cross-referenced installed versions with vendor patch history",
            )
        )

    if "search_exploitation_indicators" in applied:
        from app.demo.fixtures.s4.investigation_findings import S4_ANOMALOUS_AUTH_GATEWAYS, S4_IOC_HUNT_WINDOW

        C.set_status(state, "splunk", "OBTAINED", "No confirmed exploitation telemetry; auth anomalies on 2 gateways")
        gap_validation = s4_gap_spl_validation()
        extra.append(C.evidence(
            "ev-s4-ioc-hunt",
            "splunk_mcp_fixture",
            "Governed IOC exploitation hunt",
            [{
                "query": "mgmt/session IOC",
                "hits": 0,
                "exploitation_confirmed": False,
                "window": S4_IOC_HUNT_WINDOW,
                "advisory_id": S4_ADVISORY_ID,
            }],
            provenance="simulated_mcp",
            tool_name="splunk_run_query",
            summary=f"gap_spl_validated={gap_validation.get('approved')}",
        ))
        extra.append(C.evidence("ev-s4-splunk", "splunk_mcp_fixture", "Exploitation indicator summary", [
            {"query": "mgmt/session from WAN", "hits": 0, "exploitation_confirmed": False, "window": S4_IOC_HUNT_WINDOW},
        ], provenance="simulated_mcp", tool_name="splunk_run_query"))
        extra.append(
            C.evidence(
                "ev-s4-auth-anomalies",
                "splunk_mcp_fixture",
                "Management authentication anomalies",
                [
                    {
                        "gateway": "VPN-GW-01",
                        "event_type": "privileged_mgmt_auth_spike",
                        "count": 4,
                        "src_sample": "203.0.113.14",
                        "window": S4_IOC_HUNT_WINDOW,
                    },
                    {
                        "gateway": "VPN-GW-02",
                        "event_type": "privileged_mgmt_auth_spike",
                        "count": 2,
                        "src_sample": "198.51.100.8",
                        "window": S4_IOC_HUNT_WINDOW,
                    },
                ],
                provenance="simulated_mcp",
                tool_name="splunk_run_query",
                summary=f"Anomalous privileged management auth on {', '.join(S4_ANOMALOUS_AUTH_GATEWAYS)}",
            )
        )
        if "Exploitation not confirmed" not in outcome["confirmed"]:
            outcome["confirmed"].append("Exploitation not confirmed in the reviewed Splunk window")
        outcome["disposition"] = "suspicious"
        outcome["unconfirmed"] = [
            item
            for item in outcome["unconfirmed"]
            if "exploitation indicators are present" not in item.lower()
            and "whether exploitation" not in item.lower()
        ] + [
            "Whether anomalous privileged management activity on VPN-GW-01 and VPN-GW-02 represents successful exploitation",
            "Whether exploitation occurred outside the reviewed Splunk telemetry window",
        ]
        outcome["missing_evidence"] = [item for item in outcome["missing_evidence"] if "Splunk" not in item]

    if "show_hardening_guidance" in applied:
        C.set_status(state, "hardening", "OBTAINED", "Disable WAN management listener; restrict control plane", "ec_scenario_policy")
        extra.append(C.evidence("ev-s4-hardening", "kb_fixture", "Temporary hardening guidance", [{
            "control": "disable_wan_management_listener",
            "second_control": "restrict_control_plane_to_mgmt_vrf",
            "not_production_vendor_guidance": True,
        }], provenance="ec_scenario_policy"))
        outcome["missing_evidence"] = [item for item in outcome["missing_evidence"] if "hardening" not in item.lower()]

    if "show_incident_response_plan" in applied:
        extra.append(
            C.evidence(
                "ev-s4-ir-plan",
                "kb_fixture",
                "Incident response plan (RAG)",
                [
                    {
                        "plan_name": "EdgeGate VPN zero-day — emergency IR checklist",
                        "source": "SOC-KB / governed RAG",
                        "threat_specific_playbook": False,
                        "key_steps": [
                            "Activate incident commander and network/VPN owners",
                            "Preserve VPN gateway logs and config snapshots",
                            "Apply emergency patch or compensating controls",
                            "Restrict remote access and enforce MFA",
                            "Monitor Splunk for exploitation attempts",
                            "Communicate status to leadership and affected users",
                        ],
                    }
                ],
                provenance="ec_scenario_policy",
                summary="No threat-specific SOAR playbook — governed IR checklist retrieved from RAG",
            )
        )

    if "restrict_vpn_access" in applied:
        C.ensure_hil_action(
            kind="notify",
            label="Restrict VPN access (emergency policy)",
            session_id=session_id,
            scenario_id=S4_SCENARIO_ID,
            extra={
                "control": "restrict_vpn_access",
                "scope": ["VPN-GW-01", "VPN-GW-02"],
                "policy": "Block new remote-access sessions except break-glass accounts pending patch",
            },
        )

    if "enforce_mfa_vpn" in applied:
        C.ensure_hil_action(
            kind="notify",
            label="Enforce MFA on VPN sessions",
            session_id=session_id,
            scenario_id=S4_SCENARIO_ID,
            extra={
                "control": "enforce_mfa_vpn",
                "scope": ["VPN-GW-01", "VPN-GW-02", "VPN-GW-03", "VPN-GW-04"],
                "policy": "Require step-up MFA for all active and new VPN sessions",
            },
        )

    if "create_emergency_incident" in applied:
        C.ensure_executed_action(kind="ticket_create", label="Create emergency incident", session_id=session_id, scenario_id=S4_SCENARIO_ID, extra={"ticket": {"id": "INC-48219", "priority": "P1"}})
    if "create_change_ticket" in applied:
        C.ensure_executed_action(kind="ticket_create", label="Create emergency change", session_id=session_id, scenario_id=S4_SCENARIO_ID, extra={"ticket": {"id": "CHG-ZD-001", "type": "emergency_change"}})
    if "request_agilus_patch" in applied:
        C.ensure_hil_action(
            kind="agilus_patch_submit",
            label="Submit emergency patch via Agilus MCP",
            session_id=session_id,
            scenario_id=S4_SCENARIO_ID,
            extra={
                "agilus_job_id": "AGILUS-JOB-8842",
                "patch_id": "EG-VPN-12.3.5-EMERG",
                "targets": ["VPN-GW-01", "VPN-GW-02", "VPN-GW-05", "VPN-GW-08"],
                "ticket": {
                    "id": "CHG-ZD-AGILUS-001",
                    "type": "emergency_change",
                    "linked_job": "AGILUS-JOB-8842",
                },
            },
        )
        C.set_status(
            state,
            "agilus",
            "AWAITING_EXTERNAL_RESPONSE",
            "Agilus patch job AGILUS-JOB-8842 submitted — awaiting completion callback",
        )
    if "notify_network_team" in applied:
        email_extra = ec_email_drafts.s4_network_team_email(applied=applied, advisory_id=S4_ADVISORY_ID)
        C.ensure_hil_action(
            kind="email_send",
            label="Email network/SOC team",
            session_id=session_id,
            scenario_id=S4_SCENARIO_ID,
            extra=email_extra,
        )
    if "apply_temporary_control" in applied:
        C.ensure_hil_action(
            kind="firewall_block",
            label="Apply temporary WAN management restriction",
            session_id=session_id,
            scenario_id=S4_SCENARIO_ID,
            extra={"control": "disable_wan_management_listener", "verify_payload": {"wan_mgmt_listener": "disabled"}},
        )
    if "verify_temporary_control" in applied:
        control = next((item for item in C.actions_for(session_id, S4_SCENARIO_ID) if item.kind == "firewall_block" and item.state == "EXECUTED"), None)
        if control is not None:
            from app.demo import ec_actions

            ec_actions.verify_action(control.action_id)
    if "generate_executive_summary" in applied:
        from app.demo.fixtures.s4.investigation_findings import (
            S4_AFFECTED_ASSETS,
            S4_INTERNET_FACING_GATEWAYS,
        )

        affected_n = len(S4_AFFECTED_ASSETS)
        total_n = len(S4_INTERNET_FACING_GATEWAYS)
        outcome["executive_summary"] = (
            f"{affected_n} of {total_n} internet-facing VPN gateways are running an affected fixture version. "
            "Exploitation is not confirmed. Temporary hardening is available and requires approval."
        )


def _s4_expand_applied(applied: list[str]) -> list[str]:
    expanded = list(applied)
    if "run_network_assessment" in expanded:
        for follow_up_id in ("list_affected_assets", "check_gateway_versions"):
            if follow_up_id not in expanded:
                expanded.append(follow_up_id)
    if "run_splunk_ioc_hunt" in expanded and "search_exploitation_indicators" not in expanded:
        expanded.append("search_exploitation_indicators")
    if "request_agilus_patch" in expanded and "check_agilus_patch" not in expanded:
        expanded.append("check_agilus_patch")
    if "apply_temporary_control" in expanded and "show_hardening_guidance" not in expanded:
        expanded.append("show_hardening_guidance")
    if "apply_access_controls" in expanded:
        for follow_up_id in ("restrict_vpn_access", "enforce_mfa_vpn"):
            if follow_up_id not in expanded:
                expanded.append(follow_up_id)
    return expanded


def _s4_network_assessed(applied: list[str]) -> bool:
    return "run_network_assessment" in applied or (
        "list_affected_assets" in applied and "check_gateway_versions" in applied
    )


def _s4_bootstrapped(applied: list[str]) -> bool:
    return _s4_network_assessed(applied)


def _s4_claim_verification(applied: list[str]) -> list[str]:
    if not _s4_bootstrapped(applied):
        return [
            "Critical zero-day on internet-facing VPN gateways — pending advisory open",
            "No detection rule — pending Splunk MCP knowledge-object check",
            "No SOAR playbook — pending playbook registry check",
        ]
    return [
        f"Critical zero-day on internet-facing VPN gateways — VERIFIED ({S4_ADVISORY_ID}, EdgeGate VPN 12.1–12.4)",
        "No threat-specific detection rule — VERIFIED (Splunk MCP splunk_get_knowledge_objects: 0 matches)",
        "No SOAR playbook — VERIFIED (not available; expected for new advisory, not an error)",
        "Internet-facing VPN gateways in scope — VERIFIED (4 assets in CMDB inventory)",
    ]


def _s4_agilus_action(actions: list[Any]) -> Any | None:
    return next((item for item in actions if getattr(item, "kind", None) == "agilus_patch_submit"), None)


def _s4_agilus_submitted(applied: list[str], actions: list[Any]) -> bool:
    if "request_agilus_patch" not in applied:
        return False
    agilus = _s4_agilus_action(actions)
    return agilus is not None and agilus.state == "AWAITING_EXTERNAL_RESPONSE"


def _s4_agilus_patch_status(applied: list[str], actions: list[Any]) -> dict[str, Any] | None:
    if "check_agilus_patch" not in applied:
        return None
    status: dict[str, Any] = {
        "product": "Agilus",
        "patch_id": "EG-VPN-12.3.5-EMERG",
        "patch_title": "Emergency control-plane hardening for EdgeGate 12.1–12.4",
        "targets": ["VPN-GW-01", "VPN-GW-02"],
        "status": "ANALYZED",
        "job_id": None,
        "ticket_id": None,
        "detail": (
            "Agilus cross-referenced installed EdgeGate 12.3 builds against vendor version history "
            "and identified emergency patch EG-VPN-12.3.5-EMERG for the vulnerable gateways."
        ),
    }
    agilus = _s4_agilus_action(actions)
    if agilus is None and "request_agilus_patch" not in applied:
        return status
    if agilus is not None and agilus.state == "AWAITING_EXTERNAL_RESPONSE":
        receipt = agilus.receipt if isinstance(agilus.receipt, dict) else {}
        status.update(
            {
                "status": "AWAITING_CALLBACK",
                "job_id": receipt.get("agilus_job_id") or "AGILUS-JOB-8842",
                "ticket_id": receipt.get("ticket_id") or "CHG-ZD-AGILUS-001",
                "detail": (
                    "Patch job submitted to Agilus via MCP. Change ticket created and linked. "
                    "This investigation will update when Agilus reports patch completion."
                ),
            }
        )
        return status
    if "request_agilus_patch" in applied or (agilus is not None and agilus.state in {"APPROVAL_REQUIRED", "APPROVED", "PREPARED"}):
        status.update(
            {
                "status": "READY_TO_SUBMIT",
                "detail": (
                    "Agilus identified the applicable emergency patch. "
                    "Approve the Agilus MCP patch request to submit the job and open the linked change ticket."
                ),
            }
        )
    return status


def _s4_action_plan(applied: list[str], actions: list[Any] | None = None) -> list[str]:
    actions = actions or []
    if not _s4_bootstrapped(applied):
        return _s4_recommended_next(applied)
    plan = [
        "DONE — Splunk MCP: knowledge-object search + governed IOC hunt (0 exploitation hits)",
        "DONE — CMDB MCP: inventoried 4 internet-facing VPN gateways with health and session counts",
        "DONE — Device MCP: version probe — VPN-GW-01/02 vulnerable (12.3), VPN-GW-03/04 not affected",
        "DONE — Vulnerability scanner MCP: confirmed critical condition on vulnerable gateways",
        "DONE — Agilus MCP: matched VPN-GW-01/02 to emergency patch EG-VPN-12.3.5-EMERG from version catalog",
        "DONE — Hardening KB (RAG): temporary mitigations retrieved",
    ]
    if _s4_agilus_submitted(applied, actions):
        plan.extend(
            [
                "DONE — Agilus MCP: patch job AGILUS-JOB-8842 submitted for VPN-GW-01/02 (awaiting Agilus callback)",
                "DONE — ITSM: emergency change ticket CHG-ZD-AGILUS-001 created and linked to Agilus job",
                "WAITING — Agilus completion callback — investigation will update when patch is applied",
                "NEXT — Apply temporary control on VPN-GW-01/02 if Agilus window is delayed",
            ]
        )
    else:
        plan.extend(
            [
                "NEXT — Request patch via Agilus MCP (emergency patch identified — requires approval)",
                "NEXT — Apply temporary control on VPN-GW-01/02 (disable WAN management listener)",
                "NEXT — ITSM + email: create emergency incident and notify network team",
            ]
        )
    plan.append("OPTIONAL — Deploy Splunk detection candidate (recommendation only)")
    return plan


def _s4_any_plan_step_executed(applied: list[str]) -> bool:
    return any(step_id in applied for step_id in S4_PLAN_STEP_IDS)


def _s4_executive_summary(applied: list[str], actions: list[Any] | None = None) -> list[str]:
    """Generated after plan steps run — reflects known connector outcomes, not upfront assumptions."""
    actions = actions or []
    if not _s4_any_plan_step_executed(applied):
        return []

    bullets: list[str] = []

    if _s4_network_assessed(applied):
        posture = _s4_vpn_gateway_posture(applied)
        vulnerable = sum(1 for row in posture if row.get("affected"))
        total = len(posture) or 4
        bullets.append(
            f"Exposure: PARTIAL — {vulnerable} of {total} internet-facing VPN gateways run an affected version; "
            "compromise is not confirmed from telemetry reviewed so far."
        )
    else:
        bullets.append("Exposure assessment not complete — run Phase 1 network assessment.")

    if "run_splunk_ioc_hunt" in applied:
        bullets.append(
            "Splunk MCP IOC hunt completed — no confirmed exploitation hits in the governed 7-day VPN window."
        )
    elif "run_network_assessment" in applied:
        bullets.append("Splunk IOC hunt not run yet — use Phase 1 Splunk step when ready.")

    if "run_vuln_scan" in applied:
        bullets.append("Vulnerability scanner MCP confirmed critical advisory condition on vulnerable gateways.")

    if _s4_agilus_submitted(applied, actions):
        bullets.append(
            "Agilus MCP: patch job AGILUS-JOB-8842 submitted; change ticket CHG-ZD-AGILUS-001 linked — awaiting callback."
        )
    elif "check_agilus_patch" in applied or "request_agilus_patch" in applied:
        bullets.append(
            "Agilus MCP: emergency patch EG-VPN-12.3.5-EMERG identified for VPN-GW-01/02 — approval pending to submit job."
        )
    elif "apply_access_controls" in applied or "apply_temporary_control" in applied:
        bullets.append("Compensating controls prepared — Agilus patch path not started yet.")
    else:
        bullets.append("Agilus patch orchestration not started — run Phase 2 when exposure assessment is complete.")

    if "check_soar_playbooks" in applied:
        bullets.append(
            "No VPN-specific SOAR playbook — adapt PB-EDGE-PATCH and PB-IR-SEV1 until a dedicated playbook is published."
        )

    if "show_incident_response_plan" in applied:
        bullets.append("Standard Sev-1 IR procedure loaded from RAG — incident commander checklist is available.")

    return bullets[:5]


def _s4_vpn_gateway_posture(applied: list[str]) -> list[dict[str, Any]]:
    if not _s4_bootstrapped(applied):
        return []
    from app.demo.fixtures.s4.investigation_findings import S4_INTERNET_FACING_GATEWAYS

    return [
        {
            "gateway": row["asset"],
            "site": row["site"],
            "version": row["version"],
            "affected": bool(row["affected"]),
            "health": "Healthy",
            "active_sessions": row["active_sessions"],
            "wan_mgmt_listener": "enabled" if row["affected"] else "disabled",
        }
        for row in S4_INTERNET_FACING_GATEWAYS
    ]


def _s4_capability_plan(applied: list[str], actions: list[Any] | None = None) -> list[dict[str, str]]:
    actions = actions or []
    agilus_submitted = _s4_agilus_submitted(applied, actions)
    agilus_detail = (
        "Patch job AGILUS-JOB-8842 submitted via Agilus MCP for VPN-GW-01/02; "
        "change ticket CHG-ZD-AGILUS-001 linked — awaiting Agilus completion callback."
        if agilus_submitted
        else (
            "Cross-referenced gateway versions with Agilus vendor catalog — emergency patch "
            "EG-VPN-12.3.5-EMERG applies to VPN-GW-01/02; submit via MCP on approval."
        )
    )
    return [
        {
            "integration": "Splunk MCP",
            "status": "EXECUTED",
            "detail": "Ran splunk_get_knowledge_objects (no threat-specific detection) and splunk_run_query IOC hunt (0 hits).",
        },
        {
            "integration": "CMDB MCP",
            "status": "EXECUTED",
            "detail": "Listed 4 internet-facing VPN gateways with site, role, and inventory health.",
        },
        {
            "integration": "Device / version MCP",
            "status": "EXECUTED",
            "detail": "Probed running software on all gateways — identified affected EdgeGate 12.3 on VPN-GW-01 and VPN-GW-02.",
        },
        {
            "integration": "Vulnerability scanner MCP",
            "status": "EXECUTED",
            "detail": "Authenticated scan confirms advisory condition; Agilus identified applicable emergency patch.",
        },
        {
            "integration": "Agilus patch MCP",
            "status": "AWAITING_CALLBACK" if agilus_submitted else "READY",
            "detail": agilus_detail,
        },
        {
            "integration": "Hardening knowledge (RAG)",
            "status": "EXECUTED",
            "detail": "Retrieved temporary mitigations: disable WAN management listener; restrict control plane to management VRF.",
        },
        {
            "integration": "Network control MCP",
            "status": "READY",
            "detail": "Can apply temporary WAN management restriction on affected gateways after analyst approval.",
        },
        {
            "integration": "ITSM + email",
            "status": "EXECUTED" if agilus_submitted else "READY",
            "detail": (
                "Emergency change ticket CHG-ZD-AGILUS-001 created and linked to Agilus job AGILUS-JOB-8842."
                if agilus_submitted
                else "Can create emergency incident (INC-ZD-001) and notify the network team using governed templates."
            ),
        },
        {
            "integration": "Threat-specific SOAR playbook",
            "status": "NOT_AVAILABLE",
            "detail": "No playbook exists for this advisory yet — not an error; Agilus MCP covers patch orchestration.",
        },
    ]


def _s4_append_connected_evidence(extra: list[dict[str, Any]]) -> None:
    if any(item.get("evidence_id") == "ev-s4-vuln-scan" for item in extra):
        return
    extra.append(
        C.evidence(
            "ev-s4-vuln-scan",
            "vuln_scanner_mcp_fixture",
            "Vulnerability scanner MCP",
            [
                {
                    "gateway": "VPN-GW-01",
                    "finding": "EdgeGate control-plane condition present",
                    "severity": "Critical",
                    "patch_available": True,
                    "agilus_patch_id": "EG-VPN-12.3.5-EMERG",
                },
                {
                    "gateway": "VPN-GW-02",
                    "finding": "EdgeGate control-plane condition present",
                    "severity": "Critical",
                    "patch_available": True,
                    "agilus_patch_id": "EG-VPN-12.3.5-EMERG",
                },
            ],
            provenance="simulated_mcp",
            tool_name="vuln_run_scan",
            summary="Authenticated scan confirms vulnerable build; Agilus identified applicable emergency patch",
        )
    )


def _s4_control_step_status(applied: list[str], actions: list[Any], *, follow_up_id: str, kind: str | None = None) -> str:
    if follow_up_id not in applied:
        return "NEXT"
    if kind:
        action = next((item for item in actions if getattr(item, "kind", None) == kind), None)
    else:
        action = next(
            (
                item
                for item in actions
                if follow_up_id.replace("_", " ") in getattr(item, "label", "").lower()
                or follow_up_id in getattr(item, "label", "").lower()
            ),
            None,
        )
    if action is None:
        return "NEXT"
    state = str(getattr(action, "state", "") or "")
    if state in {"EXECUTED", "VERIFIED", "AWAITING_EXTERNAL_RESPONSE"}:
        return "DONE"
    if state in {"APPROVAL_REQUIRED", "APPROVED", "PREPARED"}:
        return "READY"
    return "NEXT"


def _s4_plan_step(
    *,
    step_id: str,
    title: str,
    plan_summary: str,
    follow_up_id: str,
    action_label: str,
    connector_mode: str,
    connector_available: bool = True,
    fallback_label: str = "Open ITSM / email request",
    executed: bool = False,
    status: str = "PLANNED",
    detail: str | None = None,
    bullets: list[str] | None = None,
    spl_preview: str | None = None,
    hil_action: bool = False,
) -> dict[str, Any]:
    return {
        "id": step_id,
        "title": title,
        "plan_summary": plan_summary,
        "follow_up_id": follow_up_id,
        "action_label": action_label,
        "connector_mode": connector_mode,
        "connector_available": connector_available,
        "fallback_label": fallback_label,
        "executed": executed,
        "status": status,
        "detail": detail,
        "bullets": bullets or [],
        "spl_preview": spl_preview,
        "hil_action": hil_action,
    }


def _s4_investigation_phases(applied: list[str], actions: list[Any], outcome: dict[str, Any]) -> list[dict[str, Any]]:
    agilus_submitted = _s4_agilus_submitted(applied, actions)
    posture = _s4_vpn_gateway_posture(applied) if _s4_network_assessed(applied) else []
    internet_facing = len(posture) or 4
    vulnerable = sum(1 for row in posture if row.get("affected")) if posture else 0
    sessions = sum(int(row.get("active_sessions") or 0) for row in posture) if posture else 0

    network_done = "run_network_assessment" in applied
    splunk_done = "run_splunk_ioc_hunt" in applied
    vuln_done = "run_vuln_scan" in applied
    agilus_analyzed = "check_agilus_patch" in applied
    access_done = "apply_access_controls" in applied
    segment_done = "apply_temporary_control" in applied
    monitor_done = "deploy_splunk_monitoring" in applied
    ir_done = "show_incident_response_plan" in applied
    soar_done = "check_soar_playbooks" in applied

    ir_procedure = [
        "1. Declare Sev-1 and assign incident commander + VPN/network owner",
        "2. Preserve evidence — VPN logs, configs, Splunk timeline (last 7 days)",
        "3. Contain — restrict VPN access, enforce MFA, disable WAN management listener",
        "4. Eradicate — emergency patch via Agilus or vendor bulletin when available",
        "5. Recover — verify versions, lift restrictions after validation",
        "6. Communicate — leadership briefing + user notification template",
        "7. Close — link Agilus job / change ticket and document lessons learned",
    ]

    return [
        {
            "phase": "1",
            "title": "Assess exposure",
            "steps": [
                _s4_plan_step(
                    step_id="network_exposure",
                    title="Review internet-facing VPN exposure",
                    plan_summary="Inventory internet-facing VPN gateways via CMDB and probe software versions.",
                    follow_up_id="run_network_assessment",
                    action_label="Run assessment",
                    connector_mode="MCP",
                    connector_available=True,
                    fallback_label="Open CMDB onboarding ticket",
                    executed=network_done,
                    status="DONE" if network_done else "PLANNED",
                    detail=(
                        f"{internet_facing} internet-facing VPN gateways · {vulnerable} vulnerable · "
                        f"{sessions} active sessions · compromise not confirmed"
                        if network_done
                        else None
                    ),
                    bullets=[
                        "VPN-GW-01 / VPN-GW-02 — EdgeGate 12.3 (vulnerable)",
                        "VPN-GW-03 / VPN-GW-04 — EdgeGate 13.0 (not affected)",
                    ]
                    if network_done
                    else [],
                ),
                _s4_plan_step(
                    step_id="splunk_ioc_hunt",
                    title="Splunk — hunt known IoCs and exploitation patterns",
                    plan_summary="Run governed Splunk MCP search for exploitation attempts, auth anomalies, and suspicious management API traffic.",
                    follow_up_id="run_splunk_ioc_hunt",
                    action_label="Run Splunk hunt",
                    connector_mode="MCP",
                    connector_available=True,
                    fallback_label="Email SOC to run hunt manually",
                    executed=splunk_done,
                    status="DONE" if splunk_done else "PLANNED",
                    detail="Governed Splunk MCP hunt — 0 confirmed exploitation hits in the reviewed 7-day window."
                    if splunk_done
                    else None,
                    spl_preview=S4_GAP_CANDIDATE_SPL if splunk_done else None,
                    bullets=[
                        "WAN management-session POSTs to /api/v1/mgmt/session",
                        "Failed authentication spikes on internet-facing VPN gateways",
                        "Unexpected configuration changes on VPN servers",
                    ]
                    if splunk_done
                    else [],
                ),
                _s4_plan_step(
                    step_id="vuln_scan",
                    title="Vulnerability scanner",
                    plan_summary="Authenticated scan of VPN gateways against the zero-day advisory condition.",
                    follow_up_id="run_vuln_scan",
                    action_label="Run scan",
                    connector_mode="MCP",
                    connector_available=True,
                    fallback_label="Open vulnerability scanner onboarding ticket",
                    executed=vuln_done,
                    status="DONE" if vuln_done else "PLANNED",
                    detail="Critical advisory condition confirmed on VPN-GW-01 and VPN-GW-02."
                    if vuln_done
                    else None,
                    hil_action=True,
                ),
            ],
        },
        {
            "phase": "2",
            "title": "Implement immediate controls",
            "steps": [
                _s4_plan_step(
                    step_id="agilus_patch",
                    title="Patch management — Agilus MCP",
                    plan_summary="Cross-reference installed versions with Agilus vendor catalog, identify the emergency patch, and submit the patch job.",
                    follow_up_id="request_agilus_patch",
                    action_label="Run via Agilus MCP",
                    connector_mode="MCP",
                    connector_available=True,
                    fallback_label="Create emergency change ticket (manual patch)",
                    executed=agilus_analyzed or agilus_submitted,
                    status="AWAITING_CALLBACK" if agilus_submitted else ("DONE" if agilus_analyzed else "PLANNED"),
                    detail=(
                        "Patch job AGILUS-JOB-8842 submitted — awaiting Agilus callback (CHG-ZD-AGILUS-001)."
                        if agilus_submitted
                        else "Agilus identified emergency patch EG-VPN-12.3.5-EMERG for VPN-GW-01/02 — approve to submit patch job."
                        if agilus_analyzed
                        else None
                    ),
                    hil_action=True,
                ),
                _s4_plan_step(
                    step_id="access_control",
                    title="Access control — restrict VPN and enforce MFA",
                    plan_summary="Tighten remote-access policy — block new sessions except break-glass and require step-up MFA.",
                    follow_up_id="apply_access_controls",
                    action_label="Request access controls",
                    connector_mode="MCP",
                    connector_available=True,
                    fallback_label="Email identity team / open access ticket",
                    executed=access_done,
                    status="DONE" if access_done else "PLANNED",
                    detail="Emergency VPN access restriction and MFA enforcement prepared — approve in the action flow below."
                    if access_done
                    else None,
                    hil_action=True,
                ),
                _s4_plan_step(
                    step_id="network_segmentation",
                    title="Network segmentation — compensating controls",
                    plan_summary="Disable WAN management listener and restrict control plane to management VRF on affected gateways.",
                    follow_up_id="apply_temporary_control",
                    action_label="Apply compensating control",
                    connector_mode="MCP",
                    connector_available=True,
                    fallback_label="Open network change ticket",
                    executed=segment_done,
                    status="DONE" if segment_done else "PLANNED",
                    detail="Temporary WAN management restriction queued — requires analyst approval in the action flow."
                    if segment_done
                    else None,
                    hil_action=True,
                ),
                _s4_plan_step(
                    step_id="splunk_monitoring",
                    title="Monitor and detect — Splunk real-time alerts",
                    plan_summary="Prepare governed Splunk real-time alert for exploitation attempts (Splunk executes what we can automate).",
                    follow_up_id="deploy_splunk_monitoring",
                    action_label="Prepare Splunk alert",
                    connector_mode="MCP",
                    connector_available=True,
                    fallback_label="Request SOC detection engineering ticket",
                    executed=monitor_done,
                    status="DONE" if monitor_done else "PLANNED",
                    detail="Alert candidate EC_EdgeGate_VPN_ZeroDay_Monitor prepared — deployment requires approval."
                    if monitor_done
                    else None,
                    spl_preview=S4_GAP_CANDIDATE_SPL if monitor_done else None,
                ),
                _s4_plan_step(
                    step_id="soar_playbooks",
                    title="SOAR playbooks — check related runbooks",
                    plan_summary="No VPN zero-day playbook on file — check registry for related emergency playbooks to adapt.",
                    follow_up_id="check_soar_playbooks",
                    action_label="Check playbooks",
                    connector_mode="MCP",
                    connector_available=True,
                    fallback_label="Email SOC automation team",
                    executed=soar_done,
                    status="DONE" if soar_done else "PLANNED",
                    detail="Adapt PB-EDGE-PATCH + PB-IR-SEV1 until a VPN-specific zero-day playbook is published."
                    if soar_done
                    else None,
                    bullets=[
                        "PB-EDGE-PATCH — Edge appliance emergency patching (recommended)",
                        "PB-IR-SEV1 — Severity-1 incident commander checklist (recommended)",
                        "PB-EMERG-VPN-MAINT — VPN maintenance emergency change (partial match)",
                    ]
                    if soar_done
                    else [],
                ),
                _s4_plan_step(
                    step_id="ir_plan",
                    title="Incident response plan — RAG (standard procedure)",
                    plan_summary="Retrieve governed Sev-1 IR checklist from SOC-KB — standard procedure when no VPN-specific SOAR playbook exists.",
                    follow_up_id="show_incident_response_plan",
                    action_label="Load IR procedure",
                    connector_mode="RAG",
                    connector_available=True,
                    fallback_label="Email incident management lead",
                    executed=ir_done,
                    status="DONE" if ir_done else "PLANNED",
                    detail="Standard EdgeGate VPN zero-day emergency IR procedure (SOC-KB):"
                    if ir_done
                    else None,
                    bullets=ir_procedure if ir_done else [],
                ),
            ],
        },
        {
            "phase": "3",
            "title": "Post-incident analysis and improvements",
            "steps": [
                _s4_plan_step(
                    step_id="forensics",
                    title="Forensic analysis",
                    plan_summary="Preserve logs and configs for root-cause analysis after containment.",
                    follow_up_id="",
                    action_label="",
                    connector_mode="MANUAL",
                    connector_available=True,
                    executed=False,
                    status="OPTIONAL",
                    detail="Run after containment — export Splunk timeline and gateway config snapshots.",
                    bullets=[
                        "Splunk timeline for management-session and auth events",
                        "Config snapshot VPN-GW-01/02 before and after patch",
                    ],
                ),
                _s4_plan_step(
                    step_id="policy_review",
                    title="Review and update security policies",
                    plan_summary="Review patch SLA, MFA, and WAN management defaults for edge VPN.",
                    follow_up_id="",
                    action_label="",
                    connector_mode="MANUAL",
                    connector_available=True,
                    executed=False,
                    status="OPTIONAL",
                    detail="Document policy gaps found during this zero-day response.",
                ),
                _s4_plan_step(
                    step_id="detection_playbook",
                    title="Develop detection rules and playbooks",
                    plan_summary="Publish Splunk detection + SOAR playbook draft from this investigation.",
                    follow_up_id="",
                    action_label="",
                    connector_mode="MANUAL",
                    connector_available=True,
                    executed=False,
                    status="OPTIONAL",
                    detail="Draft playbook: isolate → Agilus patch → verify → lift restrictions → close.",
                    bullets=[
                        "Splunk: EdgeGate WAN management-session exploitation detection",
                        "SOAR: link Agilus job + CHG ticket on completion callback",
                    ],
                ),
            ],
        },
    ]


def _s4_status_table(applied: list[str], outcome: dict[str, Any]) -> list[dict[str, str]]:
    from app.demo.fixtures.s4.investigation_findings import S4_AFFECTED_ASSETS, S4_INTERNET_FACING_GATEWAYS

    exposure_status = str(outcome.get("exposure") or "PARTIAL")
    if _s4_network_assessed(applied):
        exposure_status = (
            f"PARTIAL — {len(S4_AFFECTED_ASSETS)} of {len(S4_INTERNET_FACING_GATEWAYS)} "
            "internet-facing gateways on affected firmware"
        )
    return [
        {"Question": "Splunk detection", "Status": "None found (valid)" if _s4_bootstrapped(applied) else "Checking"},
        {"Question": "Playbook", "Status": "No threat-specific SOAR playbook available"},
        {"Question": "Exposure", "Status": exposure_status},
        {"Question": "Compromise", "Status": "Not confirmed"},
    ]


def _s4_direct_answer(applied: list[str], outcome: dict[str, Any]) -> str:
    if not _s4_network_assessed(applied):
        return ""
    exposure = str(outcome.get("exposure") or "PARTIAL")
    posture = _s4_vpn_gateway_posture(applied)
    vulnerable = sum(1 for row in posture if row.get("affected"))
    total = len(posture) or 4
    return (
        f"Exposure: {exposure} — {vulnerable} of {total} internet-facing VPN gateways are vulnerable. "
        "Compromise is not confirmed."
    )


def _s4_assessment(applied: list[str], outcome: dict[str, Any]) -> str:
    return S4_OPENING_BRIEFING


def _s4_what_we_found(applied: list[str], outcome: dict[str, Any]) -> str:
    if not _s4_bootstrapped(applied):
        return (
            "Running governed verification: Splunk knowledge-object search, advisory lookup, CMDB inventory, "
            "gateway version probe, hardening KB, and IOC hunt where required."
        )
    return (
        "Structured investigation complete — see phased plan for assess exposure, immediate controls, and post-incident improvements."
    )


def _s4_recommended_next(applied: list[str]) -> list[str]:
    steps = [
        ("show_advisory", "Open zero-day advisory"),
        ("list_affected_assets", "List internet-facing VPN gateways (CMDB)"),
        ("check_gateway_versions", "Check gateway software versions"),
        ("search_exploitation_indicators", "Run governed exploitation-indicator hunt"),
        ("show_hardening_guidance", "Review temporary hardening guidance"),
        ("apply_temporary_control", "Apply temporary control (requires approval)"),
    ]
    return [label for follow_up_id, label in steps if follow_up_id not in applied]


def _siem_coverage_check_evidence() -> dict[str, Any]:
    return C.evidence(
        "ev-s4-siem-check",
        "splunk_mcp_fixture",
        "SIEM coverage discovery",
        [{
            "advisory_id": S4_ADVISORY_ID,
            "detections_found": 0,
            "saved_searches_found": 0,
            "outcome": "no_threat_specific_detection",
        }],
        provenance="simulated_mcp",
        tool_name="splunk_get_knowledge_objects",
        summary="No existing vendor/CVE/IOC Splunk content for this advisory",
    )


def build_s4_turn(*, session_id: str, turn: int, applied_follow_up_ids: list[str], pending_action_id: str | None = None, awaiting_external: bool = False, agent_state: dict[str, Any] | None = None):
    user_applied = list(applied_follow_up_ids)
    if turn == 0 and not user_applied:
        user_applied = list(S4_PLAN_PREREAD)
    applied = _s4_expand_applied(user_applied)
    outcome = deepcopy(_base_outcome())
    state = deepcopy(_base_state())
    extra: list[dict[str, Any]] = []
    _apply(applied, session_id, outcome, state, extra)
    from app.demo.ec_agent_lifecycle import (
        build_s4_agent_workflow,
        finalize_s4_remediation_after_apply,
        get_agent_state,
        s4_followups_for_agent_mode,
    )

    resolved_agent_state = dict(agent_state or get_agent_state(session_id, S4_FAMILY))
    if resolved_agent_state.get("remediation_execute_pending"):
        resolved_agent_state = finalize_s4_remediation_after_apply(
            session_id=session_id,
            family=S4_FAMILY,
            scenario_id=S4_SCENARIO_ID,
            agent_state=resolved_agent_state,
            applied=user_applied,
        )
        if "verify_temporary_control" not in user_applied and "apply_temporary_control" in user_applied:
            user_applied = list(user_applied) + ["verify_temporary_control"]
            applied = _s4_expand_applied(user_applied)

    actions = C.actions_for(session_id, S4_SCENARIO_ID)
    hunt_obtained = "search_exploitation_indicators" in applied
    gap_validation = s4_gap_spl_validation()
    normalized_spl = gap_validation.get("normalized_spl") if gap_validation.get("approved") else None
    siem_coverage = build_s4_siem_coverage(hunt_obtained=hunt_obtained)
    agilus_awaiting = _s4_agilus_submitted(user_applied, actions)
    exec_summary = _s4_executive_summary(user_applied, actions)
    agent_workflow = build_s4_agent_workflow(
        agent_state=resolved_agent_state,
        applied=applied,
        actions=actions,
        outcome=outcome,
        executive_summary=exec_summary,
    )
    use_agent_ui = True
    agent_chips = s4_followups_for_agent_mode(
        str(resolved_agent_state.get("lifecycle") or "PLAN_READY"),
        applied=user_applied,
    )
    source = [
        _siem_coverage_check_evidence(),
        *extra,
    ] if extra or applied else [
        _siem_coverage_check_evidence(),
        C.evidence("ev-s4-condition", "advisory_fixture", "Scenario condition", [{
            "advisory_id": S4_ADVISORY_ID,
            "soar_playbook": "not_available",
            "not_an_error": True,
        }], provenance="experience_center_fixture"),
    ]
    return C.envelope(
        scenario_id=S4_SCENARIO_ID,
        family=S4_FAMILY,
        session_id=session_id,
        turn=turn,
        applied=user_applied,
        chips=agent_chips,
        title="Zero-day exposure — VPN gateways",
        direct_line=_s4_direct_answer(user_applied, outcome) if not use_agent_ui else "",
        assessment=_s4_assessment(user_applied, outcome),
        found=_s4_what_we_found(user_applied, outcome),
        recommended=_s4_action_plan(user_applied, actions),
        important=_s4_claim_verification(user_applied),
        outcome=outcome,
        evidence_state=state,
        source_evidence=source,
        actions=actions,
        resources=[
            "Splunk SIEM coverage discovery",
            "advisory knowledge",
            "CMDB / asset inventory (not Splunk)",
            "device version evidence",
            "governed IOC hunt (gap only)",
            "hardening KB",
            "No threat-specific SOAR playbook available",
        ],
        severity="P1 Critical",
        controls=["HIL for temporary control", "verification after remediation", "detection candidate not deployed"],
        pending_action_id=pending_action_id,
        awaiting_external=awaiting_external or agilus_awaiting,
        understanding=(
            "Check existing Splunk detections first; generate governed IOC hunt only for the exploitation gap. "
            "Splunk does not replace CMDB or device inventory."
        ),
        layer2_path=list(S4_LAYER2_PATH),
        extra={
            "ec_soar_playbook": "not_available",
            "ec_advisory_id": S4_ADVISORY_ID,
            "ec_opening_briefing": S4_OPENING_BRIEFING if not use_agent_ui else None,
            "ec_executive_summary": exec_summary if not use_agent_ui else [],
            "ec_vpn_gateway_posture": _s4_vpn_gateway_posture(applied)
            if _s4_network_assessed(user_applied) and not use_agent_ui
            else [],
            "ec_capability_plan": _s4_capability_plan(user_applied, actions) if not use_agent_ui else [],
            "ec_agilus_patch": _s4_agilus_patch_status(applied, actions) if not use_agent_ui else None,
            "ec_investigation_phases": [] if use_agent_ui else _s4_investigation_phases(user_applied, actions, outcome),
            "ec_agent_workflow": agent_workflow,
            "ec_agent_lifecycle": str(resolved_agent_state.get("lifecycle") or "PLAN_READY"),
            "ec_workflow_state": str(resolved_agent_state.get("lifecycle") or "PLAN_READY"),
            "ec_exposure": {"status": outcome.get("exposure"), "validation": outcome.get("exposure_validation")},
            "ec_siem_coverage": siem_coverage.model_dump() if not use_agent_ui else None,
            "ec_siem_tool_traces": [item.model_dump() for item in build_s4_tool_traces(gap_validation)]
            if not use_agent_ui
            else [],
            "ec_evidence_findings": [item.model_dump() for item in build_s4_evidence_findings(hunt_obtained=hunt_obtained)]
            if not use_agent_ui
            else [],
            "ec_detection_opportunity": build_s4_detection_opportunity().model_dump() if not use_agent_ui else None,
            "ec_investigation_scope": build_s4_investigation_scope().model_dump() if not use_agent_ui else None,
            "ec_action_readiness": [row.model_dump() for row in build_s4_action_readiness(applied, actions, outcome)]
            if not use_agent_ui
            else [],
            "ec_status_summary": (
                None
                if use_agent_ui
                else (
                    f"P1 Critical · exposure={outcome.get('exposure')} · "
                    f"no threat-specific detection · compromise not confirmed"
                    + (" · awaiting Agilus patch callback" if agilus_awaiting else "")
                )
            ),
            "ec_gap_spl_notice": None if use_agent_ui else "Additional governed SIEM search was required to resolve the evidence gap.",
            "ec_gap_spl_layer2_only": False if use_agent_ui else True,
            "candidate_spl": {
                "candidate_spl": S4_GAP_CANDIDATE_SPL,
                "execution_eligible": False,
                "generation_mode": "ec_bounded_gap_search",
                "note": "IOC hunt only — no existing detection to reuse",
            },
            "spl_validation": {
                **gap_validation,
                "approved": bool(gap_validation.get("approved")),
                "execution_eligible": False,
                "provenance": "production_validator_read_only",
                "selected_candidate_spl_provider": "ec_bounded_gap_search",
            },
            "execution": {
                "status": "simulated_receipts_packaged",
                "production_mcp_executed": False,
                "executed_spl": normalized_spl if hunt_obtained and normalized_spl else None,
                "block_reason": "live_mcp_not_called",
                "exact_call_authorization": "APPROVED" if gap_validation.get("approved") else "BLOCKED",
                "candidate_spl_not_executed": True,
            },
            **(
                {
                    "ec_email": {
                        "to": "NETWORK_TEAM",
                        "logical_recipient": "NETWORK_TEAM",
                        "status": "draft_pending_send",
                        "not_transmitted": True,
                    }
                }
                if "notify_network_team" in applied
                else {}
            ),
        },
        journey=journey_for(S4_SCENARIO_ID, user_applied if user_applied else []),
        table=_s4_status_table(applied, outcome),
    )


def s4_analyst_override(scenario_id: str, base: dict[str, Any]) -> dict[str, Any] | None:
    if scenario_id != S4_SCENARIO_ID:
        return None
    env = build_s4_turn(session_id="s4-override", turn=0, applied_follow_up_ids=[])
    return {**base, **(env.analyst or {})}


def build_s4_demo_scenarios() -> dict[str, Any]:
    return {
        S4_SCENARIO_ID: C.demo_scenario(
            scenario_id=S4_SCENARIO_ID,
            label="S4 · Zero-day / no playbook",
            query=S4_QUERY,
            demo_order=4,
            family=S4_FAMILY,
            summary="No threat-specific SOAR playbook. Assemble advisory, inventory, versions, and hardening. Vulnerable ≠ compromised.",
        )
    }
