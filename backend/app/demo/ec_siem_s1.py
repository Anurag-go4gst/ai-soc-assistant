"""S1 SIEM-first investigation projections — Experience Center only."""

from __future__ import annotations

from typing import Any

from app.demo.ec_mcp_lifecycle_fixture import PRIMARY_ATTACKER_IP
from app.demo.ec_response import (
    EcActionReadinessRow,
    EcInvestigationPivot,
    EcInvestigationScope,
    EcSiemCoverageAssessment,
    EcSiemCoverageRow,
    EcSiemExistingContent,
    EcSiemGeneratedSearch,
    EcSiemToolTrace,
    EcTelemetrySourceRow,
)

S1_DETECTION_NAME = "Suspicious External IP — Firewall Activity"
S1_SAVED_SEARCH_NAME = "EC_Suspicious_IP_Firewall_Activity"
_JUMP = "10.20.1.10"
_HOST_B = "10.20.4.55"
_HOST_C = "10.20.8.90"
_ACCOUNT = "svc_jump_ops"

S1_LAYER2_PATH = [
    "Understanding",
    "SIEM coverage discovery",
    "Existing detection/search found",
    "Coverage evaluation",
    "Existing evidence reused",
    "Communication telemetry scope",
    "Historical evidence gap identified",
    "Environment search governance",
    "Governed SPL generated for gaps",
    "SPL validation",
    "Splunk MCP execution (simulated)",
    "SourceEvidence",
    "Evidence sufficiency",
    "InvestigationOutcome",
]


def build_s1_siem_coverage() -> EcSiemCoverageAssessment:
    return EcSiemCoverageAssessment(
        siem="Splunk",
        coverage_status="PARTIAL",
        existing_content=[
            EcSiemExistingContent(
                object_type="saved_search",
                name=S1_DETECTION_NAME,
                status="existing",
                purpose="Existing IOC detection assessed; no alert — IP not present in the IOC list used by this detection",
                coverage="PARTIAL",
                reused=True,
                execution_ref=f"saved_search:{S1_SAVED_SEARCH_NAME}",
            ),
        ],
        required_evidence=[
            {
                "evidence_id": "q1_communication",
                "question": f"What communication involving {PRIMARY_ATTACKER_IP} is visible in the last 30 days?",
                "coverage": "PARTIAL",
                "source_status": "firewall_requested_window_plus_novelty",
                "resolution": "Existing notable did not fire; requested 30 days + prior novelty window",
            },
            {
                "evidence_id": "q2_affected_systems",
                "question": "Which internal systems are affected?",
                "coverage": "PARTIAL",
                "source_status": "reused_and_merged",
                "resolution": f"Three systems identified from firewall telemetry ({_JUMP}, {_HOST_B}, {_HOST_C})",
            },
            {
                "evidence_id": "q3_denied_vs_allowed",
                "question": "Which communications were denied vs allowed?",
                "coverage": "PARTIAL",
                "source_status": "firewall_only",
                "resolution": "Deny-heavy on all three; allows only on jump host",
            },
            {
                "evidence_id": "q4_auth",
                "question": "Is there evidence of successful authentication?",
                "coverage": "NONE",
                "source_status": "not_established",
                "resolution": "Identity association in firewall telemetry only; auth search is follow-up",
            },
            {
                "evidence_id": "q5_compromise",
                "question": "Does evidence confirm malicious use or attributable authentication?",
                "coverage": "NONE",
                "source_status": "unconfirmed",
                "resolution": "Requires identity, endpoint, and broader communication evidence",
            },
            {
                "evidence_id": "q6_all_communication",
                "question": "Are we seeing all communication or firewall-observed only?",
                "coverage": "PARTIAL",
                "source_status": "firewall_queried_other_available",
                "resolution": "Firewall evaluated; DNS/proxy/VPN/endpoint network not yet queried",
            },
        ],
        generated_searches=[
            EcSiemGeneratedSearch(
                evidence_requirement="Requested last 30 days plus prior 30-day novelty window",
                candidate_created=True,
                validator_status="PASS",
                normalized=True,
                execution_authorized=True,
                source_evidence_ids=["ev-s1-fw-search-1", "ev-s1-fw-search-2"],
            ),
        ],
        remaining_gaps=[
            "DNS / proxy / VPN communication not assessed",
            "Endpoint network telemetry not assessed",
            "Successful authentication not established",
            "Account compromise not confirmed",
        ],
        coverage_rows=[
            EcSiemCoverageRow(
                investigation_need="Newly observed IP / MCP identity",
                siem_status="Existing IOC notable did not fire",
                decision="Evaluated",
            ),
            EcSiemCoverageRow(
                investigation_need="Current affected systems",
                siem_status="Covered (partial)",
                decision="Correlated",
            ),
            EcSiemCoverageRow(
                investigation_need="Last 30 days plus novelty window",
                siem_status="Partial",
                decision="30+30 governed search",
            ),
            EcSiemCoverageRow(
                investigation_need="DNS communication",
                siem_status="Available, not queried",
                decision="Follow-up",
            ),
            EcSiemCoverageRow(
                investigation_need="Proxy communication",
                siem_status="Available, not queried",
                decision="Follow-up",
            ),
            EcSiemCoverageRow(
                investigation_need="Endpoint network activity",
                siem_status="Available (EDR)",
                decision="EDR follow-up",
            ),
            EcSiemCoverageRow(
                investigation_need="Authentication",
                siem_status="Not established",
                decision="Identity investigation",
            ),
        ],
    )


def build_s1_investigation_scope() -> EcInvestigationScope:
    return EcInvestigationScope(
        time_range="Last 30 days requested; prior 30-day window used only to confirm the IP is newly observed",
        telemetry_queried=["Firewall (pgcil_soc / pgcil:firewall)"],
        telemetry_sources=[
            EcTelemetrySourceRow(source="Firewall", status="OBTAINED", detail="Existing notable evaluated (did not fire) + last 30 days + novelty window"),
            EcTelemetrySourceRow(source="DNS", status="AVAILABLE_NOT_QUERIED", detail="pgcil:dns index available in environment KB"),
            EcTelemetrySourceRow(source="Proxy / web", status="AVAILABLE_NOT_QUERIED", detail="Not queried in initial investigation"),
            EcTelemetrySourceRow(source="VPN", status="AVAILABLE_NOT_QUERIED", detail="pgcil:vpn available; not queried"),
            EcTelemetrySourceRow(source="Endpoint network (EDR)", status="AVAILABLE_NOT_QUERIED", detail="EDR capability available as follow-up"),
            EcTelemetrySourceRow(source="Authentication", status="MISSING", detail="Dedicated auth evidence not yet retrieved"),
        ],
        scope_note=(
            "Firewall telemetry identifies three affected systems. Broader communication coverage remains "
            "incomplete until DNS, proxy, VPN, and endpoint network sources are assessed."
        ),
    )


def build_s1_investigation_pivot() -> EcInvestigationPivot:
    return EcInvestigationPivot(
        title="Why the jump host is prioritized",
        subject=_JUMP,
        summary=(
            f"{_HOST_B} and {_HOST_C} show deny-only activity. {_JUMP} is the only affected system with "
            f"observed allowed communication and a firewall identity association to {_ACCOUNT}. "
            "The immediate question is whether those allowed events represent legitimate service-account "
            "activity or successful malicious access."
        ),
    )


def build_s1_action_readiness(applied: list[str], actions: list[Any]) -> list[EcActionReadinessRow]:
    firewall = next((item for item in actions if getattr(item, "kind", None) == "firewall_block"), None)
    fw_state = getattr(firewall, "state", None) if firewall else None
    rows = [
        EcActionReadinessRow(action="Investigate jump host", state="RECOMMENDED"),
        EcActionReadinessRow(
            action="Raise MCP IP monitoring",
            state="READY_FOR_REVIEW" if "raise_mcp_monitoring" in applied else "READY",
        ),
        EcActionReadinessRow(action="Create incident ticket", state="READY"),
        EcActionReadinessRow(action="Notify firewall/security team", state="READY"),
        EcActionReadinessRow(
            action="Prepare IP block request",
            state="READY_FOR_REVIEW" if "prepare_firewall_block" in applied else "CONDITIONAL",
        ),
        EcActionReadinessRow(
            action="Execute IP block",
            state="APPROVAL_REQUIRED" if fw_state in {"PREPARED", "APPROVAL_REQUIRED"} else "CONDITIONAL",
        ),
        EcActionReadinessRow(action="Isolate jump host", state="NOT_RECOMMENDED_YET"),
        EcActionReadinessRow(action=f"Disable {_ACCOUNT}", state="NOT_RECOMMENDED_YET"),
    ]
    if fw_state == "EXECUTED":
        rows[5] = EcActionReadinessRow(action="Execute IP block", state="EXECUTED")
    return rows


def build_s1_tool_traces(search_1: dict[str, Any], search_2: dict[str, Any]) -> list[EcSiemToolTrace]:
    return [
        EcSiemToolTrace(
            purpose="Discover existing SOC content",
            capability="Splunk knowledge objects",
            mcp_tool="splunk_get_knowledge_objects",
            mode="READ",
            provenance="simulated_mcp",
        ),
        EcSiemToolTrace(
            purpose="Assess existing Splunk detection coverage",
            capability="Firewall activity saved search",
            mcp_tool="splunk_run_saved_search",
            mode="READ",
            detail=f"saved_search={S1_SAVED_SEARCH_NAME}",
            provenance="simulated_mcp",
        ),
        EcSiemToolTrace(
            purpose="Prior 30-day novelty window (is this IP new?)",
            capability="Governed SPL search",
            mcp_tool="splunk_run_query",
            mode="READ",
            candidate_spl=search_1.get("candidate_spl") or None,
            normalized_spl=search_1.get("normalized_spl"),
            validator_status="PASS" if search_1.get("approved") else "FAIL",
            exact_call_authorization="APPROVED" if search_1.get("approved") else "BLOCKED",
            provenance="simulated_mcp",
        ),
        EcSiemToolTrace(
            purpose="Requested last 30 days of firewall communication",
            capability="Governed SPL search",
            mcp_tool="splunk_run_query",
            mode="READ",
            candidate_spl=search_2.get("candidate_spl") or None,
            normalized_spl=search_2.get("normalized_spl"),
            validator_status="PASS" if search_2.get("approved") else "FAIL",
            exact_call_authorization="APPROVED" if search_2.get("approved") else "BLOCKED",
            provenance="simulated_mcp",
        ),
    ]
