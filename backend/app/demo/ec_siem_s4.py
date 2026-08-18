"""S4 SIEM-first zero-day projections — Experience Center only."""

from __future__ import annotations

from typing import Any

from app.demo.ec_response import (
    EcActionReadinessRow,
    EcDetectionOpportunity,
    EcEvidenceFindingRow,
    EcInvestigationScope,
    EcSiemCoverageAssessment,
    EcSiemCoverageRow,
    EcSiemExistingContent,
    EcSiemGeneratedSearch,
    EcSiemToolTrace,
    EcTelemetrySourceRow,
)
from app.safeguards.spl_validator import validate_spl

S4_ADVISORY_ID = "ZD-FIXTURE-VPN-2026-001"

S4_DETECTION_SEARCH_NAME = "EC_EdgeGate_VPN_ZeroDay_IOC"
S4_GAP_CANDIDATE_SPL = (
    "search index=pgcil_soc sourcetype=pgcil:vpn earliest=-7d latest=now "
    "(uri=\"*/api/v1/mgmt/session*\" OR url=\"*/mgmt/session*\") "
    "| stats count values(src) as src values(dest) as dest by uri action "
    "| head 100"
)

S4_LAYER2_PATH = [
    "Understanding",
    "Advisory context",
    "SIEM coverage discovery",
    "No threat-specific detection",
    "SOAR playbook check (not an error)",
    "Asset/version evidence",
    "Hardening knowledge",
    "Exposure assessment",
    "Governed IOC hunt (gap only)",
    "SPL validation",
    "Splunk MCP execution (simulated)",
    "InvestigationOutcome",
    "Temporary controls (HIL)",
    "Verification",
]


def _s4_spl_profile() -> dict[str, Any]:
    return {
        "allowed_commands": ["search", "stats", "values", "head"],
        "allowed_indexes": ["pgcil_soc"],
        "allowed_sourcetypes": ["pgcil:vpn"],
    }


def s4_gap_spl_validation() -> dict[str, Any]:
    return validate_spl(S4_GAP_CANDIDATE_SPL, template_profile=_s4_spl_profile())


def build_s4_siem_coverage(*, hunt_obtained: bool = False) -> EcSiemCoverageAssessment:
    gap_validation = s4_gap_spl_validation()
    return EcSiemCoverageAssessment(
        siem="Splunk",
        coverage_status="PARTIAL",
        existing_content=[
            EcSiemExistingContent(
                object_type="detection",
                name=f"Vendor/CVE detection for {S4_ADVISORY_ID}",
                status="none",
                purpose="Threat-specific EdgeGate VPN zero-day exploitation",
                coverage="NONE",
                reused=False,
                execution_ref=None,
            ),
            EcSiemExistingContent(
                object_type="saved_search",
                name=S4_DETECTION_SEARCH_NAME,
                status="none",
                purpose="IOC hunt for WAN management-session exploitation",
                coverage="NONE",
                reused=False,
                execution_ref=None,
            ),
        ],
        required_evidence=[
            {
                "evidence_id": "q1_exploitation",
                "question": "Is exploitation telemetry present for the advisory IOC/behavior?",
                "coverage": "OBTAINED" if hunt_obtained else "GAP",
                "source_status": "ioc_hunt" if hunt_obtained else "gap_search_required",
                "resolution": "Governed VPN IOC hunt — no existing detection to reuse",
            },
        ],
        generated_searches=[
            EcSiemGeneratedSearch(
                evidence_requirement="EdgeGate VPN management-session exploitation IOC",
                candidate_created=True,
                validator_status="PASS" if gap_validation.get("approved") else "FAIL",
                normalized=bool(gap_validation.get("normalized_spl")),
                execution_authorized=bool(gap_validation.get("approved")),
                source_evidence_ids=["ev-s4-ioc-hunt"] if hunt_obtained else [],
            ),
        ],
        remaining_gaps=[
            "No vendor/CVE-specific Splunk detection exists yet",
            "CMDB inventory is separate from Splunk — not inferred from SIEM",
        ],
        coverage_rows=[
            EcSiemCoverageRow(
                investigation_need="Threat-specific detection",
                siem_status="None found",
                decision="Valid outcome",
            ),
            EcSiemCoverageRow(
                investigation_need="IOC exploitation telemetry",
                siem_status="Gap" if not hunt_obtained else "Governed hunt",
                decision="Governed search" if not hunt_obtained else "Reviewed",
            ),
            EcSiemCoverageRow(
                investigation_need="VPN gateway inventory",
                siem_status="Not Splunk CMDB",
                decision="CMDB follow-up",
            ),
            EcSiemCoverageRow(
                investigation_need="Device versions",
                siem_status="Device evidence",
                decision="Version probe",
            ),
        ],
    )


def build_s4_tool_traces(gap_validation: dict[str, Any] | None = None) -> list[EcSiemToolTrace]:
    gap_validation = gap_validation or s4_gap_spl_validation()
    normalized = gap_validation.get("normalized_spl")
    return [
        EcSiemToolTrace(
            purpose="Discover CVE/vendor/IOC Splunk content",
            capability="Splunk knowledge objects",
            mcp_tool="splunk_get_knowledge_objects",
            mode="READ",
            detail=f"no_match_for={S4_ADVISORY_ID}",
            provenance="simulated_mcp",
        ),
        EcSiemToolTrace(
            purpose="Resolve exploitation-indicator gap",
            capability="Governed IOC hunt",
            mcp_tool="splunk_run_query",
            mode="READ",
            candidate_spl=S4_GAP_CANDIDATE_SPL,
            normalized_spl=normalized,
            validator_status="PASS" if gap_validation.get("approved") else "FAIL",
            exact_call_authorization="APPROVED" if gap_validation.get("approved") else "BLOCKED",
            provenance="simulated_mcp",
        ),
    ]


def build_s4_evidence_findings(*, hunt_obtained: bool) -> list[EcEvidenceFindingRow]:
    rows = [
        EcEvidenceFindingRow(
            investigation_point="Threat-specific Splunk detection",
            finding="None found",
            evidence_basis="Knowledge-object search — valid outcome",
        ),
        EcEvidenceFindingRow(
            investigation_point="SOAR playbook",
            finding="Not available",
            evidence_basis="Scenario condition — not an error",
        ),
    ]
    if hunt_obtained:
        rows.append(
            EcEvidenceFindingRow(
                investigation_point="Exploitation indicators",
                finding="Not confirmed",
                evidence_basis="Governed IOC hunt — zero hits in reviewed window",
            )
        )
    return rows


def build_s4_detection_opportunity() -> EcDetectionOpportunity:
    return EcDetectionOpportunity(
        status="PREPARED",
        title="Detection opportunity identified",
        summary=(
            "No approved Splunk detection correlates EdgeGate VPN WAN management-session exploitation "
            f"for advisory {S4_ADVISORY_ID}."
        ),
        recommended_action="Create detection candidate",
        deploy_status="not_deployed",
        notes="Recommendation only — Experience Center does not deploy detections to Splunk.",
    )


def build_s4_investigation_scope() -> EcInvestigationScope:
    return EcInvestigationScope(
        time_range="Advisory-driven — exploitation hunt uses 7-day VPN window when run",
        telemetry_queried=["Splunk VPN telemetry (IOC hunt only when gap identified)"],
        telemetry_sources=[
            EcTelemetrySourceRow(
                source="Splunk detections/saved searches",
                status="CHECKED_NONE",
                detail="No threat-specific content for this advisory",
            ),
            EcTelemetrySourceRow(
                source="CMDB VPN inventory",
                status="SEPARATE_RESOURCE",
                detail="Splunk is not CMDB — inventory via CMDB follow-up",
            ),
            EcTelemetrySourceRow(
                source="Device version evidence",
                status="SEPARATE_RESOURCE",
                detail="Gateway version via device/version probe — not Splunk inventory",
            ),
        ],
        scope_note="Vulnerable gateway versions are not the same as confirmed compromise.",
    )


def build_s4_action_readiness(applied: list[str], actions: list[Any], outcome: dict[str, Any]) -> list[EcActionReadinessRow]:
    control = next((item for item in actions if getattr(item, "kind", None) == "firewall_block"), None)
    control_state = getattr(control, "state", None) if control else None
    rows = [
        EcActionReadinessRow(action="Open advisory", state="RECOMMENDED"),
        EcActionReadinessRow(action="Inventory VPN gateways (CMDB)", state="RECOMMENDED"),
        EcActionReadinessRow(action="Check gateway versions", state="RECOMMENDED"),
        EcActionReadinessRow(action="Run governed IOC hunt", state="CONDITIONAL"),
        EcActionReadinessRow(action="Apply temporary control", state="NOT_RECOMMENDED_YET"),
        EcActionReadinessRow(action="Close as compromised", state="NOT_RECOMMENDED_YET"),
    ]
    if "show_advisory" in applied:
        rows[0] = EcActionReadinessRow(action="Open advisory", state="OBTAINED")
    if "list_affected_assets" in applied:
        rows[1] = EcActionReadinessRow(action="Inventory VPN gateways (CMDB)", state="OBTAINED")
    if "check_gateway_versions" in applied:
        rows[2] = EcActionReadinessRow(action="Check gateway versions", state="OBTAINED")
        rows[5] = EcActionReadinessRow(action="Close as compromised", state="NOT_RECOMMENDED_YET")
    if "search_exploitation_indicators" in applied:
        rows[3] = EcActionReadinessRow(action="Run governed IOC hunt", state="OBTAINED")
    if "show_hardening_guidance" in applied:
        rows[4] = EcActionReadinessRow(action="Apply temporary control", state="READY_FOR_REVIEW")
    if control_state in {"PREPARED", "APPROVAL_REQUIRED"}:
        rows[4] = EcActionReadinessRow(action="Apply temporary control", state="APPROVAL_REQUIRED")
    if control_state == "EXECUTED":
        rows[4] = EcActionReadinessRow(action="Apply temporary control", state="EXECUTED")
    if outcome.get("exposure_validation") == "VERSION_EVIDENCE_APPLIED":
        rows.append(EcActionReadinessRow(action="Treat vulnerable as compromised", state="NOT_RECOMMENDED_YET"))
    return rows

