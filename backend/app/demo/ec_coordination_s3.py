"""S3 team-coordination projections — Experience Center only."""

from __future__ import annotations

from typing import Any

from app.demo.ec_mcp_lifecycle_fixture import INCIDENT_ID, PRIMARY_ATTACKER_IP
from app.demo.ec_response import EcActionReadinessRow, EcEvidenceReuseRow

_JUMP = "10.20.1.10"
_HOST_B = "10.20.4.55"
_HOST_C = "10.20.8.90"

S3_LAYER2_PATH = [
    "Understanding",
    "Reused SIEM evidence",
    "Process knowledge",
    "Mandatory request fields",
    "Team email coordination",
    "Awaiting response",
    "Inbound evidence ingested",
    "Whitelist reassessment",
    "InvestigationOutcome",
    "Governed remediation",
    "Verification",
]

S3_PRIOR_S1_REFERENCE = (
    f"Governed suspicious-IP investigation ({INCIDENT_ID}) — firewall telemetry confirmed"
)


def build_s3_evidence_reuse() -> list[EcEvidenceReuseRow]:
    return [
        EcEvidenceReuseRow(
            evidence_id="ev-s3-prior-siem",
            label="S1-class SIEM investigation",
            origin=f"Incident {INCIDENT_ID}",
            status="REUSED",
            detail=(
                f"Confirmed malicious-pattern traffic from {PRIMARY_ATTACKER_IP} against "
                f"{_JUMP}, {_HOST_B}, and {_HOST_C} — no new Splunk search required"
            ),
        ),
        EcEvidenceReuseRow(
            evidence_id="ev-s3-prior-compact",
            label="Compact investigation state",
            origin="Experience Center prior-evidence fixture",
            status="REUSED",
            detail="Deny/allow mix and affected-system list carried into coordination workflow",
        ),
    ]


def build_s3_action_readiness(
    applied: list[str],
    actions: list[Any],
    outcome: dict[str, Any],
) -> list[EcActionReadinessRow]:
    firewall = next((item for item in actions if getattr(item, "kind", None) == "firewall_block"), None)
    fw_state = getattr(firewall, "state", None) if firewall else None
    whitelist_remove = next(
        (item for item in actions if getattr(item, "kind", None) == "firewall_remove_whitelist"),
        None,
    )
    remove_state = getattr(whitelist_remove, "state", None) if whitelist_remove else None

    if "ingest_firewall_reply" in applied:
        rows = [
            EcActionReadinessRow(action="Review vendor whitelist exception", state="RECOMMENDED"),
            EcActionReadinessRow(action="Confirm business-owner approval", state="RECOMMENDED"),
            EcActionReadinessRow(action="Close as benign (whitelist explains all)", state="NOT_RECOMMENDED_YET"),
            EcActionReadinessRow(
                action="Remove vendor whitelist",
                state="CONDITIONAL" if remove_state not in {"EXECUTED", "VERIFIED"} else "READY_FOR_REVIEW",
            ),
            EcActionReadinessRow(
                action="Request IP block",
                state=(
                    "READY_FOR_REVIEW"
                    if fw_state in {"PREPARED", "APPROVAL_REQUIRED"}
                    else "CONDITIONAL"
                ),
            ),
            EcActionReadinessRow(action="Block immediately without exception review", state="NOT_RECOMMENDED_YET"),
        ]
        if fw_state == "EXECUTED":
            rows[4] = EcActionReadinessRow(action="Request IP block", state="EXECUTED")
        if remove_state == "EXECUTED":
            rows[3] = EcActionReadinessRow(action="Remove vendor whitelist", state="EXECUTED")
        return rows

    rows = [
        EcActionReadinessRow(action="Retrieve firewall-block process", state="RECOMMENDED"),
        EcActionReadinessRow(action="Prepare firewall-team email", state="READY"),
        EcActionReadinessRow(action="Send request to firewall team", state="READY"),
        EcActionReadinessRow(action="Request IP block immediately", state="NOT_RECOMMENDED_YET"),
        EcActionReadinessRow(action="Close investigation", state="NOT_RECOMMENDED_YET"),
    ]
    if "show_firewall_process" in applied:
        rows[0] = EcActionReadinessRow(action="Retrieve firewall-block process", state="OBTAINED")
    if "prepare_firewall_email" in applied:
        rows[1] = EcActionReadinessRow(action="Prepare firewall-team email", state="READY_FOR_REVIEW")
    if "send_firewall_email" in applied:
        rows[2] = EcActionReadinessRow(action="Send request to firewall team", state="AWAITING_RESPONSE")
    return rows


def build_s3_recommended_coordination(applied: list[str]) -> list[str]:
    if "ingest_firewall_reply" in applied:
        return [
            "Review the vendor whitelist exception with the business owner",
            "Do not close as benign — exception does not explain the full evidence window",
            "Remove the whitelist only with documented approval if malicious overlap is confirmed",
            "Request an IP block only after exception review — not automatic on malicious indicator",
        ]
    if "show_firewall_process" in applied:
        return [
            "Prepare the mandatory-field firewall-team request",
            "Send the request and wait for team confirmation",
            "Treat any inbound reply as new evidence before remediation",
        ]
    return [
        "Retrieve the company firewall-block process",
        "Reuse confirmed SIEM evidence — no new Splunk search is required for coordination",
        "Send mandatory-field request to the firewall team",
    ]


def build_s3_status_summary(applied: list[str], workflow: str, outcome: dict[str, Any]) -> str:
    disposition = outcome.get("disposition", "suspicious")
    if "generate_closure_summary" in applied:
        return f"Closed · {PRIMARY_ATTACKER_IP} · coordination complete (fixture)"
    if "ingest_firewall_reply" in applied:
        return (
            f"Reassessment · Whitelist exception reported · disposition={disposition} · "
            "benign close not recommended"
        )
    if workflow == "AWAITING_FIREWALL_TEAM_CONFIRMATION":
        return f"Awaiting firewall team · {PRIMARY_ATTACKER_IP} · SIEM evidence reused · no SPL generated"
    return (
        f"Coordination · {PRIMARY_ATTACKER_IP} · SIEM evidence reused · "
        "process-driven team request pending"
    )
