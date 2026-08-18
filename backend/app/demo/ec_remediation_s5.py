"""S5 multi-resource remediation projections — Experience Center only."""

from __future__ import annotations

from typing import Any

from app.demo.ec_response import EcActionReadinessRow, EcInvestigationScope, EcTelemetrySourceRow

S5_DEVICE = "R-17"

S5_LAYER2_PATH = [
    "Understanding",
    "Splunk breach evidence",
    "Hardening policy (knowledge)",
    "Cisco version probe",
    "Policy applicability",
    "Change ticket / approval",
    "HIL",
    "Simulated cisco.upgrade",
    "Receipt",
    "Version verification",
    "InvestigationOutcome",
    "Closure",
]


def build_s5_resource_composition() -> list[dict[str, str]]:
    return [
        {"resource": "Splunk", "role": "Breach / compromise indicators", "mode": "read", "note": "Security telemetry — not device management"},
        {"resource": "Knowledge base", "role": "Enterprise hardening policy", "mode": "read", "note": "EC scenario policy — not vendor production guidance"},
        {"resource": "Cisco MCP", "role": "cisco.get_version / cisco.upgrade", "mode": "read_write_simulated", "note": "Device version and upgrade only"},
        {"resource": "ITSM", "role": "Change ticket and maintenance window", "mode": "write_simulated", "note": "Rollback and verification required"},
        {"resource": "Email", "role": "Network-team approval", "mode": "HIL", "note": "Not transmitted until approved"},
    ]


def build_s5_investigation_scope() -> EcInvestigationScope:
    return EcInvestigationScope(
        time_range="Breach investigation window — device remediation is change-controlled",
        telemetry_queried=["Splunk compromise indicators on router"],
        telemetry_sources=[
            EcTelemetrySourceRow(
                source="Splunk security telemetry",
                status="OBTAINED",
                detail=f"Compromise indicators for {S5_DEVICE}",
            ),
            EcTelemetrySourceRow(
                source="Cisco device API",
                status="AVAILABLE",
                detail="Version probe and upgrade — not sourced from Splunk",
            ),
            EcTelemetrySourceRow(
                source="Hardening policy KB",
                status="AVAILABLE",
                detail="Version-gated remediation rule (EC scenario policy)",
            ),
        ],
        scope_note="Splunk establishes breach context; Cisco MCP performs version and upgrade — Splunk is not device inventory.",
    )


def build_s5_action_readiness(applied: list[str], actions: list[Any], version: int) -> list[EcActionReadinessRow]:
    upgrade = next((item for item in actions if getattr(item, "kind", None) == "cisco_upgrade"), None)
    upgrade_state = getattr(upgrade, "state", None) if upgrade else None
    rows = [
        EcActionReadinessRow(action="Review hardening policy", state="RECOMMENDED"),
        EcActionReadinessRow(action="Confirm current version (cisco.get_version)", state="RECOMMENDED"),
        EcActionReadinessRow(action="Create change ticket", state="READY"),
        EcActionReadinessRow(action="Request network approval", state="CONDITIONAL"),
        EcActionReadinessRow(action="Execute cisco.upgrade", state="NOT_RECOMMENDED_YET"),
        EcActionReadinessRow(action="Verify version 15", state="NOT_RECOMMENDED_YET"),
    ]
    if "show_hardening_policy" in applied:
        rows[0] = EcActionReadinessRow(action="Review hardening policy", state="OBTAINED")
    if "check_current_version" in applied or version:
        rows[1] = EcActionReadinessRow(action="Confirm current version (cisco.get_version)", state="OBTAINED")
    if "create_change_ticket" in applied:
        rows[2] = EcActionReadinessRow(action="Create change ticket", state="OBTAINED")
    if "request_network_approval" in applied:
        rows[3] = EcActionReadinessRow(action="Request network approval", state="AWAITING_APPROVAL")
    if "approve_upgrade" in applied:
        rows[4] = EcActionReadinessRow(action="Execute cisco.upgrade", state="READY_FOR_REVIEW")
    if upgrade_state == "APPROVED":
        rows[4] = EcActionReadinessRow(action="Execute cisco.upgrade", state="READY_FOR_REVIEW")
    if upgrade_state == "EXECUTED":
        rows[4] = EcActionReadinessRow(action="Execute cisco.upgrade", state="EXECUTED")
        rows[5] = EcActionReadinessRow(action="Verify version 15", state="RECOMMENDED")
    if upgrade_state == "VERIFIED" or version >= 15:
        rows[5] = EcActionReadinessRow(action="Verify version 15", state="VERIFIED")
    return rows


def build_s5_status_summary(version: int, remediation_status: str) -> str:
    return (
        f"P2 High · {S5_DEVICE} · current_version={version} · "
        f"policy requires 14→15 when compromised · remediation={remediation_status}"
    )
