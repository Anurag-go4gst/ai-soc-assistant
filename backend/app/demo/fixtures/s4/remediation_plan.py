"""S4 governed remediation plan — structured steps derived from investigation state."""

from __future__ import annotations

from typing import Any

from app.demo import ec_email_drafts
from app.demo.ec_siem_s4 import S4_ADVISORY_ID
from app.demo.fixtures.s4.investigation_findings import (
    S4_AFFECTED_ASSETS,
    S4_ANOMALOUS_AUTH_GATEWAYS,
)

S4_PLANNED_INCIDENT_ID = "INC-48219"
S4_PLANNED_CHANGE_ID = "CHG-29173"
S4_PLANNED_PATCH_ID = "EG-VPN-12.3.5-EMERG"
S4_PLANNED_AGILUS_JOB = "AGILUS-JOB-8842"

_REMEDIATION_CHANNELS: dict[str, dict[str, str]] = {
    "restrict_wan": {
        "channel": "email_escalation",
        "rationale": "No governed Network MCP write path — WAN listener change requires network ops change window.",
    },
    "enforce_mfa": {
        "channel": "email_escalation",
        "rationale": "Identity MCP is read-only in this tenant — step-up MFA requires IdP policy change via IAM.",
    },
    "create_incident": {"channel": "itsm", "rationale": "ITSM connector creates governed incident record."},
    "create_change": {"channel": "itsm", "rationale": "ITSM emergency change before Agilus patch submission."},
    "submit_patch": {"channel": "mcp", "rationale": "Agilus MCP submits emergency patch job after change approval."},
    "deploy_monitoring": {"channel": "splunk_mcp", "rationale": "Splunk MCP deploys governed detection supplement."},
    "notify_stakeholders": {
        "channel": "email",
        "rationale": "Stakeholder notification sent only after upstream remediation actions complete.",
    },
}


def _follow_up_executed(step_id: str, applied: list[str]) -> bool:
    mapping = {
        "restrict_wan": "apply_temporary_control",
        "enforce_mfa": "apply_access_controls",
        "create_incident": "create_emergency_incident",
        "create_change": "create_change_ticket",
        "submit_patch": "request_agilus_patch",
        "deploy_monitoring": "deploy_splunk_monitoring",
        "notify_stakeholders": "notify_network_team",
    }
    follow_up = mapping.get(step_id)
    return bool(follow_up and follow_up in applied)


def build_s4_remediation_summary(
    *,
    selected_count: int,
    total_count: int,
    validated_count: int = 0,
) -> dict[str, Any]:
    return {
        "title": "Remediation plan ready",
        "steps_completed": validated_count,
        "steps_total": selected_count,
        "metrics": [
            {"label": "Gateways", "value": len(S4_AFFECTED_ASSETS)},
            {"label": "Patch targets", "value": len(S4_AFFECTED_ASSETS)},
            {"label": "Email escalations", "value": 2},
            {"label": "MCP / ITSM actions", "value": 5},
        ],
        "plan_steps": f"{selected_count} / {total_count} actions queued",
    }


def build_s4_remediation_conclusion(*, normalized: dict[str, Any]) -> dict[str, Any]:
    assets = ", ".join(normalized.get("affected_asset_ids") or S4_AFFECTED_ASSETS)
    anomalous = ", ".join(normalized.get("anomalous_asset_ids") or S4_ANOMALOUS_AUTH_GATEWAYS)
    patch = normalized.get("patch_id") or S4_PLANNED_PATCH_ID
    return {
        "title": "Remediation approach",
        "headline": f"Contain {len(S4_AFFECTED_ASSETS)} vulnerable gateways, then deploy {patch} after approval.",
        "narrative_points": [
            f"Request WAN management restriction via network ops email (no direct Network MCP write in this tenant).",
            f"Escalate step-up MFA to Identity/IAM — typically 4–24h IdP policy push, not an instant toggle.",
            f"Open P1 incident {S4_PLANNED_INCIDENT_ID} and emergency change {S4_PLANNED_CHANGE_ID} via ITSM.",
            f"Submit {patch} to all four gateways via Agilus MCP after change approval (job {S4_PLANNED_AGILUS_JOB}).",
            f"Deploy temporary Splunk monitoring via Splunk MCP; notify network and SOC owners after upstream steps.",
            f"Prioritize deeper review on {anomalous} while compromise remains unconfirmed.",
        ],
    }


def _email_draft_preview(*, applied: list[str] | None = None) -> dict[str, Any]:
    envelope = ec_email_drafts.s4_network_team_email(
        applied=applied or [],
        advisory_id=S4_ADVISORY_ID,
    )
    preview = _email_preview_from_envelope(envelope, sent="notify_network_team" in (applied or []))
    return {**preview, "email_extra": envelope}


def _email_preview_from_envelope(envelope: dict[str, Any], *, sent: bool) -> dict[str, Any]:
    email = envelope.get("email") if isinstance(envelope.get("email"), dict) else envelope
    body = str(email.get("body") or "")
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    return {
        "to": email.get("to") or envelope.get("logical_recipient"),
        "subject": email.get("subject"),
        "body": body,
        "body_preview": "\n".join(lines[:16]),
        "status": "sent" if sent else "draft_pending_send",
        "send_note": (
            "Transmitted — awaiting acknowledgement."
            if sent
            else "Draft prepared — use Send in the email dialog after analyst review."
        ),
    }


def _headline_for_status(
    *,
    queued: str,
    running: str,
    complete: str,
    status: str,
    executed: bool,
) -> tuple[str, dict[str, str]]:
    token = status.upper()
    if token == "RUNNING":
        current = running
    elif token == "COMPLETE":
        current = complete if executed else queued.replace("Queued —", "Validated —")
    else:
        current = queued
    return current, {"QUEUED": queued, "RUNNING": running, "COMPLETE": complete}


def finding_for_remediation_step(
    step_id: str,
    *,
    status: str,
    normalized: dict[str, Any],
    applied: list[str] | None = None,
) -> dict[str, Any] | None:
    applied = applied or []
    executed = _follow_up_executed(step_id, applied)
    assets = list(normalized.get("affected_asset_ids") or S4_AFFECTED_ASSETS)
    anomalous = list(normalized.get("anomalous_asset_ids") or S4_ANOMALOUS_AUTH_GATEWAYS)
    patch = normalized.get("patch_id") or S4_PLANNED_PATCH_ID
    asset_label = ", ".join(assets)
    channel_meta = _REMEDIATION_CHANNELS.get(step_id, {})
    channel = channel_meta.get("channel", "email")

    if step_id == "restrict_wan":
        email_envelope = ec_email_drafts.s4_wan_restriction_escalation_email(
            assets=assets,
            advisory_id=S4_ADVISORY_ID,
            anomalous=anomalous,
        )
        email = _email_preview_from_envelope(email_envelope, sent=executed)
        headline, headlines_by_status = _headline_for_status(
            queued=f"Queued — network ops email drafted for WAN listener restriction on {len(assets)} gateways",
            running="Sending escalation — network change queue",
            complete=f"Escalation sent — WAN management restriction requested for {asset_label}",
            status=status,
            executed=executed,
        )
        return {
            "headline_finding": headline,
            "headlines_by_status": headlines_by_status,
            "key_evidence": [
                f"Advisory {S4_ADVISORY_ID} — internet-facing VPN gateways on affected firmware",
                "Compensating control: disable_wan_management_listener (network change window required)",
                f"Targets: {asset_label}",
                "No governed Network MCP write connector — SOAR/network email escalation required",
            ],
            "affected_entities": assets,
            "quantitative_summary": {"gateways": len(assets), "email_escalations": 1},
            "caveat": channel_meta.get("rationale", ""),
            "evidence_sources": [
                {"source": "Email · Network ops", "provenance": "governed_draft", "tool": "email_escalation"}
            ],
            "details": {
                "execution_channel": channel,
                "depends_on": "Investigation — vulnerable firmware confirmed",
                "email_draft": email,
                "email_extra": email_envelope,
            },
            "attention_state": "ATTENTION",
        }

    if step_id == "enforce_mfa":
        email_envelope = ec_email_drafts.s4_identity_mfa_escalation_email(
            assets=assets,
            advisory_id=S4_ADVISORY_ID,
            anomalous=anomalous,
        )
        email = _email_preview_from_envelope(email_envelope, sent=executed)
        headline, headlines_by_status = _headline_for_status(
            queued="Queued — IAM escalation drafted (step-up MFA is not an instant MCP toggle)",
            running="Sending escalation — Identity / IAM queue",
            complete="Escalation sent — IAM change window opened for step-up MFA policy",
            status=status,
            executed=executed,
        )
        return {
            "headline_finding": headline,
            "headlines_by_status": headlines_by_status,
            "key_evidence": [
                "Identity MCP is read-only for VPN IdP policies in this tenant",
                "Step-up MFA requires Azure AD / Okta conditional access change — typical SLA 4–24 hours",
                f"Scope: active and new sessions on {asset_label}",
                f"Correlate with auth anomalies on {', '.join(anomalous)}",
            ],
            "affected_entities": assets,
            "quantitative_summary": {"policy_scope_gateways": len(assets), "email_escalations": 1},
            "caveat": (
                "MFA enforcement is not executed from this console — IAM must publish IdP policy and "
                "users may need re-authentication on next session."
            ),
            "evidence_sources": [
                {"source": "Email · Identity / IAM", "provenance": "governed_draft", "tool": "email_escalation"}
            ],
            "details": {
                "execution_channel": channel,
                "depends_on": "restrict_wan",
                "email_draft": email,
                "email_extra": email_envelope,
                "iam_notes": [
                    "Emergency conditional-access policy draft attached",
                    "Requires CAB / IAM duty manager approval",
                    "Session re-auth expected — not silent for all users",
                ],
            },
            "attention_state": "ATTENTION",
        }

    if step_id == "create_incident":
        headline, headlines_by_status = _headline_for_status(
            queued=f"Queued — P1 incident {S4_PLANNED_INCIDENT_ID} prepared via ITSM",
            running=f"Creating incident {S4_PLANNED_INCIDENT_ID}",
            complete=f"Incident {S4_PLANNED_INCIDENT_ID} created · VPN zero-day response",
            status=status,
            executed=executed,
        )
        return {
            "headline_finding": headline,
            "headlines_by_status": headlines_by_status,
            "key_evidence": [
                f"Severity P1 · advisory {S4_ADVISORY_ID}",
                f"Assign VPN/network owners · link {len(assets)} vulnerable gateways",
                "Compromise status: not confirmed",
            ],
            "affected_entities": assets,
            "quantitative_summary": {"incidents": 1},
            "caveat": "ITSM connector — record created on batch approval.",
            "evidence_sources": [{"source": "ITSM", "provenance": "simulated_mcp", "tool": "itsm_create_incident"}],
            "details": {
                "execution_channel": channel,
                "ticket_id": S4_PLANNED_INCIDENT_ID,
                "depends_on": "enforce_mfa",
                "ticket_detail": {
                    "ticket_id": S4_PLANNED_INCIDENT_ID,
                    "ticket_type": "incident",
                    "priority": "P1",
                    "title": f"VPN zero-day response · advisory {S4_ADVISORY_ID}",
                    "status": "Draft — confirm to open in ITSM",
                    "assignee_group": "VPN / Network owners",
                    "linked_advisory": S4_ADVISORY_ID,
                },
            },
            "attention_state": "INFORMATIONAL",
        }

    if step_id == "create_change":
        headline, headlines_by_status = _headline_for_status(
            queued=f"Queued — emergency change {S4_PLANNED_CHANGE_ID} prepared",
            running=f"Submitting change {S4_PLANNED_CHANGE_ID}",
            complete=f"Change {S4_PLANNED_CHANGE_ID} opened · awaiting network approval",
            status=status,
            executed=executed,
        )
        return {
            "headline_finding": headline,
            "headlines_by_status": headlines_by_status,
            "key_evidence": [
                "Emergency change for VPN gateway patching",
                "Network team approval gate before Agilus submission",
                f"Linked incident {S4_PLANNED_INCIDENT_ID}",
            ],
            "affected_entities": assets,
            "quantitative_summary": {"change_tickets": 1},
            "caveat": "Patch job blocked until change approval completes.",
            "evidence_sources": [{"source": "ITSM", "provenance": "simulated_mcp", "tool": "itsm_create_change"}],
            "details": {
                "execution_channel": channel,
                "ticket_id": S4_PLANNED_CHANGE_ID,
                "depends_on": "create_incident",
                "ticket_detail": {
                    "ticket_id": S4_PLANNED_CHANGE_ID,
                    "ticket_type": "emergency_change",
                    "priority": "P1",
                    "title": "Emergency VPN gateway patching",
                    "status": "Draft — network approval required",
                    "assignee_group": "Network Change Management",
                    "linked_incident": S4_PLANNED_INCIDENT_ID,
                    "linked_advisory": S4_ADVISORY_ID,
                },
            },
            "attention_state": "ATTENTION",
        }

    if step_id == "submit_patch":
        headline, headlines_by_status = _headline_for_status(
            queued=f"Queued — Agilus job {S4_PLANNED_AGILUS_JOB} prepared for {patch}",
            running=f"Submitting {patch} via Agilus MCP",
            complete=f"Patch job submitted — {patch} on {asset_label} (awaiting change approval)",
            status=status,
            executed=executed,
        )
        return {
            "headline_finding": headline,
            "headlines_by_status": headlines_by_status,
            "key_evidence": [
                f"Emergency patch {patch} mapped to EdgeGate 12.3 / 12.4 builds",
                f"Prepared job {S4_PLANNED_AGILUS_JOB} · linked to {S4_PLANNED_CHANGE_ID}",
                "Agilus MCP — execution blocked until change approval completes",
            ],
            "affected_entities": assets,
            "quantitative_summary": {"patch_targets": len(assets), "patch_jobs": 1},
            "caveat": "Patch eligibility confirmed — does not prove prior compromise.",
            "evidence_sources": [{"source": "Agilus MCP", "provenance": "simulated_mcp", "tool": "agilus_submit_patch"}],
            "details": {
                "execution_channel": channel,
                "patch_id": patch,
                "job_id": S4_PLANNED_AGILUS_JOB,
                "change_id": S4_PLANNED_CHANGE_ID,
                "depends_on": "create_change",
            },
            "attention_state": "ATTENTION",
        }

    if step_id == "deploy_monitoring":
        headline, headlines_by_status = _headline_for_status(
            queued="Queued — Splunk MCP alert candidate prepared (not deployed)",
            running="Deploying Splunk detection via MCP",
            complete="Splunk alert deployed — exploitation attempts on vulnerable gateways",
            status=status,
            executed=executed,
        )
        return {
            "headline_finding": headline,
            "headlines_by_status": headlines_by_status,
            "key_evidence": [
                "Governed real-time search across VPN gateway telemetry",
                f"Scope: {asset_label}",
                "Splunk MCP — alert candidate validated against allowlisted indexes",
            ],
            "affected_entities": assets,
            "quantitative_summary": {"monitoring_rules": 1, "gateways_monitored": len(assets)},
            "caveat": "Detection supplement only — not a substitute for patching.",
            "evidence_sources": [{"source": "Splunk MCP", "provenance": "simulated_mcp", "tool": "splunk_deploy_alert"}],
            "details": {"execution_channel": channel, "depends_on": "submit_patch"},
            "attention_state": "INFORMATIONAL",
        }

    if step_id == "notify_stakeholders":
        email = _email_draft_preview(applied=applied)
        envelope = email.get("email_extra") or {}
        headline, headlines_by_status = _headline_for_status(
            queued="Queued — stakeholder notification draft (sends after upstream steps)",
            running="Preparing stakeholder notification",
            complete="Stakeholder notification sent — network and SOC owners",
            status=status,
            executed=executed,
        )
        return {
            "headline_finding": headline,
            "headlines_by_status": headlines_by_status,
            "key_evidence": [
                f"To: {email['to']}",
                f"Subject: {email['subject']}",
                f"References incident {S4_PLANNED_INCIDENT_ID} and advisory {S4_ADVISORY_ID}",
                f"High-attention assets: {', '.join(anomalous)}",
                email["send_note"],
            ],
            "affected_entities": anomalous,
            "quantitative_summary": {"email_drafts": 1, "stakeholder_groups": 2},
            "caveat": (
                "Notification is intentionally last — email status stays Queued until WAN, MFA escalations, "
                "ITSM, patch, and monitoring steps complete."
            ),
            "evidence_sources": [{"source": "Email · Teams", "provenance": "governed_draft", "tool": "email_send"}],
            "details": {
                "execution_channel": channel,
                "email_draft": email,
                "email_extra": envelope,
                "depends_on": "deploy_monitoring",
            },
            "attention_state": "INFORMATIONAL",
        }

    if status == "SKIPPED":
        return {
            "headline_finding": "Skipped — not included in approved remediation plan",
            "key_evidence": [],
            "caveat": "Deselected steps are not executed.",
            "evidence_sources": [],
            "details": {},
            "attention_state": "NORMAL",
        }

    return None


def enrich_remediation_steps(
    steps: list[dict[str, Any]],
    *,
    normalized: dict[str, Any],
    applied: list[str] | None = None,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for step in steps:
        step_status = str(step.get("status") or "QUEUED")
        finding = finding_for_remediation_step(
            step["id"],
            status=step_status,
            normalized=normalized,
            applied=applied,
        )
        if finding and not step.get("selected", True):
            finding = finding_for_remediation_step(step["id"], status="SKIPPED", normalized=normalized, applied=applied)
        channel = _REMEDIATION_CHANNELS.get(step["id"], {})
        headline = (finding or {}).get("headline_finding")
        enriched.append(
            {
                **step,
                "execution_channel": channel.get("channel"),
                "finding": finding,
                "result": headline or step.get("result"),
            }
        )
    return enriched
