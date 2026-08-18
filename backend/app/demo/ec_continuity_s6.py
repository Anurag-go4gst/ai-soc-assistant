"""S6 investigation continuity projections — Experience Center only."""

from __future__ import annotations

from typing import Any

from app.demo.ec_response import EcActionReadinessRow, EcEvidenceReuseRow

S6_LAYER2_PATH = [
    "Understanding",
    "Initial scope evidence",
    "Scope change",
    "Evidence applicability reassessment",
    "Historical incident context",
    "Ticket fetch/update",
    "Owner notification",
    "Updated InvestigationOutcome",
]

S6_CONTINUITY_POLICY = {
    "identical_siem_rerun_for_animation": False,
    "scope_change_requires_applicability_review": True,
    "destructive_remediation": False,
}


def build_s6_evidence_reuse(outcome: dict[str, Any], applied: list[str]) -> list[EcEvidenceReuseRow]:
    scope = outcome.get("scope", "privileged_admin_vpn_germany_yesterday")
    admin_status = "OUT_OF_SCOPE" if scope != "privileged_admin_vpn_germany_yesterday" else "OBTAINED"
    hist_status = "STALE" if "check_last_month_incident" in applied else "AVAILABLE"
    return [
        EcEvidenceReuseRow(
            evidence_id="ev-s6-admin",
            label="Privileged admin VPN failures (Germany)",
            origin="Initial Splunk VPN auth search",
            status=admin_status,
            detail=(
                "Administrator-account evidence from turn 0 — not rerun on scope change; "
                "applicability re-evaluated only"
            ),
        ),
        EcEvidenceReuseRow(
            evidence_id="INC-VPN-0712",
            label="Last month's incident",
            origin="Investigation archive",
            status=hist_status,
            detail="Reusable as geo/VPN-failure context — not identical scope",
        ),
    ]


def build_s6_action_readiness(applied: list[str]) -> list[EcActionReadinessRow]:
    rows = [
        EcActionReadinessRow(action="Clarify scope (service accounts / build servers)", state="RECOMMENDED"),
        EcActionReadinessRow(action="Compare historical incident", state="CONDITIONAL"),
        EcActionReadinessRow(action="Update historical ticket", state="CONDITIONAL"),
        EcActionReadinessRow(action="Notify incident owner", state="CONDITIONAL"),
        EcActionReadinessRow(action="Disable accounts / isolate hosts", state="NOT_RECOMMENDED_YET"),
    ]
    if "scope_service_accounts" in applied or "scope_build_servers" in applied:
        rows[0] = EcActionReadinessRow(action="Clarify scope (service accounts / build servers)", state="OBTAINED")
    if "check_last_month_incident" in applied:
        rows[1] = EcActionReadinessRow(action="Compare historical incident", state="REUSABLE_CONTEXT")
    if "fetch_old_incident_ticket" in applied:
        rows[2] = EcActionReadinessRow(action="Update historical ticket", state="READY")
    if "update_incident_ticket" in applied:
        rows[2] = EcActionReadinessRow(action="Update historical ticket", state="EXECUTED")
    if "notify_incident_owner" in applied:
        rows[3] = EcActionReadinessRow(action="Notify incident owner", state="READY_FOR_REVIEW")
    return rows


def build_s6_status_summary(scope: str) -> str:
    return f"Continuity · scope={scope} · applicability tracked · no destructive remediation"
