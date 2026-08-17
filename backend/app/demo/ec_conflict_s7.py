"""S7 conflicting evidence projections — Experience Center only."""

from __future__ import annotations

from app.demo.ec_response import EcActionReadinessRow, EcInvestigationPivot

S7_LAYER2_PATH = [
    "Understanding",
    "Splunk OT telemetry",
    "CMDB retirement record",
    "Conflict detected",
    "OT inventory",
    "Firewall / ARP evidence",
    "OT team input",
    "Conflict resolution",
    "InvestigationOutcome",
    "Path-specific actions",
]

S7_DEVICE = "OT-RTU-14"


def build_s7_investigation_pivot() -> EcInvestigationPivot:
    return EcInvestigationPivot(
        title="Why Splunk alone cannot close this",
        subject=S7_DEVICE,
        summary=(
            "Splunk shows unauthorized-access telemetry while CMDB lists the asset as retired. "
            "Neither source alone is sufficient — OT inventory, network evidence, and OT-team "
            "confirmation are required before incident or data-quality actions."
        ),
    )


def build_s7_action_readiness(applied: list[str], outcome: dict[str, Any]) -> list[EcActionReadinessRow]:
    path = outcome.get("path")
    disposition = outcome.get("disposition", "unresolved_conflict")
    rows = [
        EcActionReadinessRow(action="Resolve Splunk vs CMDB conflict", state="RECOMMENDED"),
        EcActionReadinessRow(action="Check OT inventory", state="RECOMMENDED"),
        EcActionReadinessRow(action="Gather firewall / ARP evidence", state="CONDITIONAL"),
        EcActionReadinessRow(action="Ask OT team", state="CONDITIONAL"),
        EcActionReadinessRow(action="Create security incident", state="BLOCKED_UNTIL_RESOLVED"),
        EcActionReadinessRow(action="Open CMDB correction ticket", state="BLOCKED_UNTIL_RESOLVED"),
        EcActionReadinessRow(action="Force incident from Splunk alone", state="NOT_RECOMMENDED_YET"),
    ]
    if "check_ot_inventory" in applied:
        rows[1] = EcActionReadinessRow(action="Check OT inventory", state="OBTAINED")
    if "check_firewall_activity" in applied or "check_arp_mac" in applied:
        rows[2] = EcActionReadinessRow(action="Gather firewall / ARP evidence", state="OBTAINED")
    if "ask_ot_team" in applied:
        rows[3] = EcActionReadinessRow(action="Ask OT team", state="AWAITING_RESPONSE")
    if "ingest_ot_response" in applied or "confirm_stale_identity" in applied:
        rows[0] = EcActionReadinessRow(action="Resolve Splunk vs CMDB conflict", state="RESOLVED")
        rows[3] = EcActionReadinessRow(action="Ask OT team", state="OBTAINED")
    if path == "A" and disposition in {"suspicious", "confirmed"}:
        rows[4] = EcActionReadinessRow(action="Create security incident", state="READY")
        rows[5] = EcActionReadinessRow(action="Open CMDB correction ticket", state="CONDITIONAL")
    if path == "B" and disposition == "not_an_incident":
        rows[4] = EcActionReadinessRow(action="Create security incident", state="NOT_RECOMMENDED_YET")
        rows[5] = EcActionReadinessRow(action="Open CMDB correction ticket", state="RECOMMENDED")
    if "create_incident_ticket" in applied:
        rows[4] = EcActionReadinessRow(action="Create security incident", state="EXECUTED")
    if "recommend_cmdb_correction" in applied:
        rows[5] = EcActionReadinessRow(action="Open CMDB correction ticket", state="EXECUTED")
    return rows


def build_s7_status_summary(outcome: dict[str, Any]) -> str:
    disposition = outcome.get("disposition", "unresolved_conflict")
    path = outcome.get("path") or "unresolved"
    return f"Conflict · {S7_DEVICE} · disposition={disposition} · path={path} · Splunk alone insufficient"
