"""Experience Center agent lifecycle — EC-only orchestration simulation.

Not imported by production /chat. S4 zero-day is the reference implementation.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.demo import ec_actions, ec_fsm_store

S4_SCENARIO_ID = "s4_zero_day_no_playbook"
S4_FAMILY = "s4_zero_day"

# Lifecycle states (closed set for EC agent showcase).
LIFECYCLE_PLAN_READY = "PLAN_READY"
LIFECYCLE_INVESTIGATING = "INVESTIGATING"
LIFECYCLE_INVESTIGATION_NEEDS_APPROVAL = "INVESTIGATION_NEEDS_APPROVAL"
LIFECYCLE_INVESTIGATION_COMPLETE = "INVESTIGATION_COMPLETE"
LIFECYCLE_REMEDIATION_PLAN_READY = "REMEDIATION_PLAN_READY"
LIFECYCLE_REMEDIATION_APPROVED = "REMEDIATION_APPROVED"
LIFECYCLE_REMEDIATING = "REMEDIATING"
LIFECYCLE_VERIFYING = "VERIFYING"
LIFECYCLE_COMPLETE = "COMPLETE"
LIFECYCLE_BLOCKED = "BLOCKED"
LIFECYCLE_PARTIAL = "PARTIAL"
LIFECYCLE_FAILED = "FAILED"
LIFECYCLE_CANCELLED = "CANCELLED"

S4_INVESTIGATION_STEP_DEFS: tuple[dict[str, Any], ...] = (
    {
        "id": "identify_gateways",
        "title": "Identify internet-facing VPN gateways",
        "summary": "Inventory internet-facing EdgeGate VPN gateways and session posture via CMDB.",
        "follow_up_id": "run_network_assessment",
        "tools": ["CMDB"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "check_versions",
        "title": "Check installed versions against advisory",
        "summary": "Compare installed firmware to the zero-day advisory affected range.",
        "follow_up_id": None,
        "bundle_with": "run_network_assessment",
        "tools": ["CMDB", "Device MCP"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "hunt_iocs",
        "title": "Hunt Splunk for exploitation indicators",
        "summary": "Run governed Splunk MCP search for exploitation and management-plane abuse.",
        "follow_up_id": "run_splunk_ioc_hunt",
        "tools": ["Splunk MCP"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "auth_anomalies",
        "title": "Check authentication / management-plane anomalies",
        "summary": "Correlate unusual management authentication on internet-facing gateways.",
        "follow_up_id": None,
        "bundle_with": "run_splunk_ioc_hunt",
        "tools": ["Splunk MCP"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "splunk_detections",
        "title": "Check existing Splunk detections",
        "summary": "Confirm whether threat-specific Splunk content already exists for this advisory.",
        "follow_up_id": None,
        "bundle_with": "show_advisory",
        "tools": ["Splunk MCP"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "soar_playbooks",
        "title": "Check SOAR/emergency playbooks",
        "summary": "Search for a VPN zero-day playbook and list related emergency runbooks to adapt.",
        "follow_up_id": "check_soar_playbooks",
        "tools": ["Playbook registry"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "ir_guidance",
        "title": "Retrieve IR and hardening guidance",
        "summary": "Pull governed Sev-1 IR checklist and temporary hardening guidance from SOC-KB.",
        "follow_up_id": "show_incident_response_plan",
        "tools": ["SOC-KB"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "agilus_patch_analysis",
        "title": "Agilus MCP — version and patch eligibility",
        "summary": "Cross-reference installed gateway versions with Agilus vendor catalog and emergency patch mapping.",
        "follow_up_id": "check_agilus_patch",
        "tools": ["Agilus MCP"],
        "default_selected": False,
        "optional": True,
        "phase": "investigation",
        "hil_required": True,
    },
)

S4_REMEDIATION_STEP_DEFS: tuple[dict[str, Any], ...] = (
    {
        "id": "restrict_wan",
        "title": "Restrict WAN management on affected gateways",
        "summary": "Escalate network ops to disable WAN management listener (no Network MCP write path).",
        "follow_up_id": "apply_temporary_control",
        "tools": ["Email · Network ops"],
        "hil_required": True,
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "enforce_mfa",
        "title": "Request step-up MFA via IAM",
        "summary": "Escalate Identity/IAM for conditional-access policy — not an instant MCP toggle.",
        "follow_up_id": "apply_access_controls",
        "tools": ["Email · Identity / IAM"],
        "hil_required": True,
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "create_incident",
        "title": "Create emergency P1 incident",
        "summary": "Open a P1 incident and assign VPN/network owners.",
        "follow_up_id": "create_emergency_incident",
        "tools": ["ITSM"],
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "create_change",
        "title": "Create emergency change ticket",
        "summary": "Open CHG-29173 and route network approval before Agilus patch submission.",
        "follow_up_id": "create_change_ticket",
        "tools": ["ITSM"],
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "submit_patch",
        "title": "Submit emergency patch request",
        "summary": "Submit Agilus emergency patch job and link the change ticket.",
        "follow_up_id": "request_agilus_patch",
        "tools": ["Agilus MCP"],
        "hil_required": True,
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "deploy_monitoring",
        "title": "Prepare temporary Splunk monitoring candidate",
        "summary": "Prepare governed real-time Splunk alert for exploitation attempts.",
        "follow_up_id": "deploy_splunk_monitoring",
        "tools": ["Splunk MCP"],
        "hil_required": True,
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "notify_stakeholders",
        "title": "Notify Network + SOC owners",
        "summary": "Send governed notification to network and SOC stakeholders.",
        "follow_up_id": "notify_network_team",
        "tools": ["Email / Teams"],
        "hil_required": True,
        "default_selected": True,
        "phase": "remediation",
    },
)

S4_AGENT_CONVERSATIONAL_FOLLOWUPS = frozenset(
    {
        "generate_executive_summary",
    }
)

S4_INVESTIGATION_PLAN_SUMMARY = (
    "Seven governed read-only steps to establish exposure, telemetry coverage, and IR guidance "
    "before proposing containment."
)

S4_ACTION_PLAN_SUMMARY = (
    "Establish exposure and telemetry first, confirm playbook gaps, then propose governed "
    "containment and patch orchestration for analyst approval."
)

S4_AGENT_ADAPTATION_STEP = {
    "id": "auth_deep_dive",
    "title": "Correlate anomalous privileged management activity",
    "added_by_agent": True,
    "reason": (
        "Added because the initial exploitation hunt identified unusual management-plane activity "
        "on VPN-GW-01 and VPN-GW-02."
    ),
    "tools": ["Splunk MCP"],
    "bundle_with": "run_splunk_ioc_hunt",
}


def _default_agent_state() -> dict[str, Any]:
    return {
        "lifecycle": LIFECYCLE_PLAN_READY,
        "investigation_selected": [
            step["id"] for step in S4_INVESTIGATION_STEP_DEFS if step.get("default_selected", True)
        ],
        "remediation_selected": [step["id"] for step in S4_REMEDIATION_STEP_DEFS],
        "vuln_scan_decision": None,
        "agilus_analysis_decision": None,
        "adaptation_added": False,
        "investigation_progress": [],
        "remediation_progress": [],
        "verification": [],
    }


def get_agent_state(session_id: str | None, family: str) -> dict[str, Any]:
    session = ec_fsm_store.get_ec_session(session_id, family) if session_id else None
    state = dict((session or {}).get("agent_state") or _default_agent_state())
    if "lifecycle" not in state:
        state["lifecycle"] = LIFECYCLE_PLAN_READY
    return state


def save_agent_state(
    session_id: str,
    family: str,
    *,
    scenario_id: str,
    agent_state: dict[str, Any],
) -> dict[str, Any]:
    return ec_fsm_store.upsert_ec_session(
        session_id,
        family,
        scenario_id=scenario_id,
        agent_state=agent_state,
    )


def _selected_investigation_follow_ups(selected_ids: list[str]) -> list[str]:
    ordered: list[str] = []
    for step in S4_INVESTIGATION_STEP_DEFS:
        if step["id"] not in selected_ids:
            continue
        follow_up_id = step.get("follow_up_id")
        if follow_up_id and follow_up_id not in ordered:
            ordered.append(follow_up_id)
    return ordered


def _selected_remediation_follow_ups(selected_ids: list[str]) -> list[str]:
    ordered: list[str] = []
    for step in S4_REMEDIATION_STEP_DEFS:
        if step["id"] not in selected_ids:
            continue
        follow_up_id = step.get("follow_up_id")
        if follow_up_id and follow_up_id not in ordered:
            ordered.append(follow_up_id)
    return ordered


def _apply_follow_ups(
    session_id: str,
    family: str,
    scenario_id: str,
    follow_up_ids: list[str],
) -> dict[str, Any]:
    record = ec_fsm_store.get_ec_session(session_id, family) or {}
    for follow_up_id in follow_up_ids:
        record = ec_fsm_store.apply_follow_up(
            session_id,
            family,
            scenario_id=scenario_id,
            follow_up_id=follow_up_id,
        )
    return record


def _auto_execute_remediation_actions(session_id: str, scenario_id: str) -> int:
    """Approve and execute all pending remediation actions after envelope minted them."""
    executed = 0
    for _ in range(12):
        pending = [
            item
            for item in ec_actions.list_actions_for_session(session_id, scenario_id)
            if item.state == "APPROVAL_REQUIRED"
        ]
        if not pending:
            break
        for action in pending:
            approved = ec_actions.approve_action(action.action_id)
            ec_actions.execute_action(approved.action_id)
            executed += 1
    return executed


def finalize_s4_remediation_after_apply(
    *,
    session_id: str,
    family: str,
    scenario_id: str,
    agent_state: dict[str, Any],
    applied: list[str],
) -> dict[str, Any]:
    """Run batch remediation execution after fixture _apply() has minted actions."""
    if not agent_state.get("remediation_execute_pending"):
        return agent_state

    state = dict(agent_state)
    state["lifecycle"] = LIFECYCLE_REMEDIATING
    save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=state)

    _auto_execute_remediation_actions(session_id, scenario_id)

    if "apply_temporary_control" in applied:
        control = next(
            (
                item
                for item in ec_actions.list_actions_for_session(session_id, scenario_id)
                if item.kind == "firewall_block" and item.state == "EXECUTED"
            ),
            None,
        )
        if control is not None:
            ec_actions.verify_action(control.action_id)

    stuck = [
        item
        for item in ec_actions.list_actions_for_session(session_id, scenario_id)
        if item.state == "APPROVAL_REQUIRED"
    ]
    state["remediation_execute_pending"] = False
    if stuck:
        state["lifecycle"] = LIFECYCLE_PARTIAL
        state["remediation_blocked"] = [item.label for item in stuck]
    else:
        state["lifecycle"] = LIFECYCLE_VERIFYING
        save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=state)
        state["lifecycle"] = LIFECYCLE_COMPLETE
    save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=state)
    return state


def s4_followups_for_agent_mode(lifecycle: str, applied: list[str] | None = None) -> list[Any]:
    """Return lifecycle-appropriate conversational chips only — no orchestration duplicates."""
    from app.demo.fixtures.s4.pack import S4_FOLLOWUPS

    applied_ids = set(applied or [])
    if lifecycle in {
        LIFECYCLE_PLAN_READY,
        LIFECYCLE_INVESTIGATING,
        LIFECYCLE_INVESTIGATION_NEEDS_APPROVAL,
        LIFECYCLE_REMEDIATING,
        LIFECYCLE_VERIFYING,
        LIFECYCLE_REMEDIATION_PLAN_READY,
    }:
        return []
    if lifecycle in {LIFECYCLE_INVESTIGATION_COMPLETE, LIFECYCLE_PARTIAL}:
        return []
    if lifecycle == LIFECYCLE_COMPLETE:
        if "generate_executive_summary" in applied_ids:
            return []
        return [chip for chip in S4_FOLLOWUPS if chip.follow_up_id in S4_AGENT_CONVERSATIONAL_FOLLOWUPS]
    return []


def _step_status(
    *,
    step_id: str,
    applied: list[str],
    agent_state: dict[str, Any],
    phase: str,
) -> str:
    lifecycle = agent_state.get("lifecycle", LIFECYCLE_PLAN_READY)
    progress = (
        agent_state.get("investigation_progress") or []
        if phase == "investigation"
        else agent_state.get("remediation_progress") or []
    )
    for row in progress:
        if row.get("id") == step_id:
            return str(row.get("status") or "QUEUED")

    if lifecycle == LIFECYCLE_PLAN_READY:
        return "QUEUED"
    if lifecycle == LIFECYCLE_REMEDIATION_PLAN_READY and phase == "remediation":
        return "QUEUED"

    if step_id == "auth_deep_dive" and agent_state.get("adaptation_added"):
        return "COMPLETE" if "run_splunk_ioc_hunt" in applied else "SKIPPED"

    step_def = next(
        (item for item in (S4_INVESTIGATION_STEP_DEFS if phase == "investigation" else S4_REMEDIATION_STEP_DEFS) if item["id"] == step_id),
        None,
    )
    if not step_def:
        return "SKIPPED"

    follow_up_id = step_def.get("follow_up_id")
    bundle_with = step_def.get("bundle_with")
    if follow_up_id and follow_up_id in applied:
        return "COMPLETE"
    if bundle_with and bundle_with in applied:
        return "COMPLETE"
    if bundle_with == "show_advisory" and "show_advisory" in applied:
        return "COMPLETE"
    return "SKIPPED"


def _build_investigation_step_row(
    step: dict[str, Any],
    *,
    inv_selected: list[str],
    applied: list[str],
    agent_state: dict[str, Any],
    actions: list[Any],
    outcome: dict[str, Any],
) -> dict[str, Any]:
    from app.demo.fixtures.s4.investigation_findings import finding_for_investigation_step

    selected = step["id"] in inv_selected or bool(step.get("added_by_agent") and agent_state.get("adaptation_added"))
    if step["id"] == "auth_anomalies" and agent_state.get("adaptation_added"):
        status = "SKIPPED"
    else:
        status = _step_status(
            step_id=step["id"],
            applied=applied,
            agent_state=agent_state,
            phase="investigation",
        )
    finding = finding_for_investigation_step(
        step["id"],
        status=status,
        applied=applied,
        agent_state=agent_state,
        outcome=outcome,
        selected=selected,
    )
    from app.demo.fixtures.s4.investigation_state import enrich_finding_metadata

    finding = enrich_finding_metadata(finding, step_id=step["id"])
    headline = (finding or {}).get("headline_finding")
    return {
        **step,
        "summary": step.get("summary"),
        "selected": selected,
        "status": status,
        "finding": finding,
        "result": headline,
        "provenance": "SIMULATED" if step.get("follow_up_id") else "FIXTURE",
    }


def _result_for_step(step_id: str, applied: list[str], actions: list[Any]) -> str | None:
    """Remediation-step execution receipts (investigation uses structured findings)."""
    if step_id == "restrict_wan" and "apply_temporary_control" in applied:
        return "Escalation sent"
    if step_id == "enforce_mfa" and "apply_access_controls" in applied:
        return "IAM change opened"
    if step_id == "create_incident" and "create_emergency_incident" in applied:
        return "INC-48219"
    if step_id == "create_change" and "create_change_ticket" in applied:
        return "CHG-29173"
    if step_id == "submit_patch" and "request_agilus_patch" in applied:
        agilus = next((item for item in actions if getattr(item, "kind", None) == "agilus_patch_submit"), None)
        if agilus and agilus.state == "AWAITING_EXTERNAL_RESPONSE":
            return "CHG-29173"
        return "Awaiting approval"
    if step_id == "deploy_monitoring" and "deploy_splunk_monitoring" in applied:
        return "Alert candidate prepared"
    if step_id == "notify_stakeholders" and "notify_network_team" in applied:
        return "Notification sent"
    return None


def _workflow_phase(lifecycle: str) -> str:
    if lifecycle in {LIFECYCLE_PLAN_READY, LIFECYCLE_INVESTIGATING, LIFECYCLE_INVESTIGATION_NEEDS_APPROVAL}:
        return "plan"
    if lifecycle == LIFECYCLE_INVESTIGATION_COMPLETE:
        return "investigation_complete"
    return "remediation"


def build_s4_agent_workflow(
    *,
    agent_state: dict[str, Any],
    applied: list[str],
    actions: list[Any],
    outcome: dict[str, Any] | None = None,
    executive_summary: list[str] | None = None,
) -> dict[str, Any]:
    lifecycle = str(agent_state.get("lifecycle") or LIFECYCLE_PLAN_READY)
    outcome = outcome or {}
    from app.demo.fixtures.s4.pack import S4_OPENING_BRIEFING

    phase = _workflow_phase(lifecycle)
    inv_selected = list(agent_state.get("investigation_selected") or [])
    investigation_done = lifecycle in {
        LIFECYCLE_INVESTIGATION_COMPLETE,
        LIFECYCLE_REMEDIATION_PLAN_READY,
        LIFECYCLE_REMEDIATING,
        LIFECYCLE_VERIFYING,
        LIFECYCLE_COMPLETE,
        LIFECYCLE_PARTIAL,
    }
    rem_selected = list(agent_state.get("remediation_selected") or [])

    investigation_steps: list[dict[str, Any]] = []
    for step in S4_INVESTIGATION_STEP_DEFS:
        investigation_steps.append(
            _build_investigation_step_row(
                step,
                inv_selected=inv_selected,
                applied=applied,
                agent_state=agent_state,
                actions=actions,
                outcome=outcome,
            )
        )

    if agent_state.get("adaptation_added"):
        adaptation = _build_investigation_step_row(
            S4_AGENT_ADAPTATION_STEP,
            inv_selected=inv_selected,
            applied=applied,
            agent_state={**agent_state, "adaptation_added": True},
            actions=actions,
            outcome=outcome,
        )
        if not any(item["id"] == "auth_deep_dive" for item in investigation_steps):
            hunt_idx = next(
                (index for index, item in enumerate(investigation_steps) if item["id"] == "hunt_iocs"),
                len(investigation_steps) - 1,
            )
            investigation_steps.insert(hunt_idx + 1, adaptation)

    remediation_steps = [
        {
            **step,
            "summary": step.get("summary"),
            "selected": step["id"] in rem_selected,
            "status": _step_status(
                step_id=step["id"],
                applied=applied,
                agent_state=agent_state,
                phase="remediation",
            ),
            "result": _result_for_step(step["id"], applied, actions),
            "provenance": "SIMULATED",
        }
        for step in S4_REMEDIATION_STEP_DEFS
    ]

    workflow: dict[str, Any] = {
        "lifecycle": lifecycle,
        "phase": phase,
        "opening_narrative": S4_OPENING_BRIEFING,
        "brief": {
            "what_i_know": [
                "Advisory identified",
                "Internet-facing VPN infrastructure may be in scope",
                "Threat-specific detection not yet confirmed",
                "VPN-specific playbook not identified",
                "Compromise not confirmed",
            ],
            "objective": [
                "Which gateways are affected",
                "Whether exploitation is visible",
                "What detection/playbook coverage exists",
                "What immediate containment is required",
            ],
        },
        "action_plan": {
            "summary": S4_ACTION_PLAN_SUMMARY,
            "steps": [
                "Open advisory and confirm Splunk detection gap",
                "Inventory internet-facing VPN gateways and versions",
                "Hunt exploitation indicators and auth anomalies",
                "Check SOAR playbook coverage and retrieve IR guidance",
                "Propose governed remediation after evidence synthesis",
            ],
        },
        "investigation_plan": {
            "editable": lifecycle == LIFECYCLE_PLAN_READY,
            "summary": S4_INVESTIGATION_PLAN_SUMMARY,
            "primary_cta": "Run investigation",
            "secondary_cta": "Edit plan",
            "steps": investigation_steps,
        },
        "remediation_plan": {
            "editable": lifecycle == LIFECYCLE_REMEDIATION_PLAN_READY,
            "summary": "Governed containment and patch orchestration — batch-executed after one approval.",
            "primary_cta": "Approve remediation",
            "secondary_cta": "Modify plan",
            "steps": remediation_steps,
            "visible": lifecycle
            in {
                LIFECYCLE_REMEDIATION_PLAN_READY,
                LIFECYCLE_REMEDIATION_APPROVED,
                LIFECYCLE_REMEDIATING,
                LIFECYCLE_VERIFYING,
                LIFECYCLE_COMPLETE,
                LIFECYCLE_PARTIAL,
            },
        },
        "remediation_offer": None,
        "unconfirmed": list(outcome.get("unconfirmed") or []) if investigation_done else [],
        "missing_evidence": list(outcome.get("missing_evidence") or []) if investigation_done else [],
        "executive_summary": [],
        "hil_prompt": None,
        "investigation_conclusion": None,
        "investigation_summary": None,
        "final_summary": None,
        "evidence_summary": [],
    }

    if lifecycle in {
        LIFECYCLE_INVESTIGATION_COMPLETE,
        LIFECYCLE_REMEDIATION_PLAN_READY,
        LIFECYCLE_REMEDIATING,
        LIFECYCLE_VERIFYING,
        LIFECYCLE_COMPLETE,
        LIFECYCLE_PARTIAL,
    }:
        from app.demo.fixtures.s4.investigation_state import build_s4_normalized_investigation_state

        normalized = build_s4_normalized_investigation_state(
            applied=applied,
            agent_state=agent_state,
            outcome=outcome,
            investigation_steps=investigation_steps,
        )
        workflow["investigation_summary"] = normalized.get("investigation_summary")
        workflow["investigation_conclusion"] = normalized.get("investigation_conclusion")
        workflow["unconfirmed"] = list(normalized.get("outstanding_uncertainty") or [])
        workflow["missing_evidence"] = list(normalized.get("missing_evidence") or [])
        workflow["normalized_state"] = {
            key: normalized[key]
            for key in (
                "affected_asset_ids",
                "anomalous_asset_ids",
                "patch_id",
                "patch_scope_asset_ids",
                "compromise_status",
            )
        }
        if lifecycle in {
            LIFECYCLE_REMEDIATION_PLAN_READY,
            LIFECYCLE_REMEDIATING,
            LIFECYCLE_VERIFYING,
            LIFECYCLE_COMPLETE,
            LIFECYCLE_PARTIAL,
        }:
            from app.demo.fixtures.s4.remediation_plan import (
                build_s4_remediation_conclusion,
                build_s4_remediation_summary,
                enrich_remediation_steps,
            )

            selected_rem = [step for step in remediation_steps if step.get("selected", True)]
            remediation_steps = enrich_remediation_steps(
                remediation_steps,
                normalized=normalized,
                applied=applied,
            )
            workflow["remediation_summary"] = build_s4_remediation_summary(
                selected_count=len(selected_rem),
                total_count=len(remediation_steps),
            )
            workflow["remediation_conclusion"] = build_s4_remediation_conclusion(normalized=normalized)
            workflow["remediation_plan"]["steps"] = remediation_steps
            workflow["remediation_plan"]["summary"] = (
                f"Governed containment and patch orchestration for {len(normalized.get('affected_asset_ids') or [])} "
                "vulnerable gateways — batch-executed after one approval."
            )
            workflow["remediation_results"] = {
                "header": "Remediation plan",
                "steps": remediation_steps,
            }

    if lifecycle == LIFECYCLE_INVESTIGATION_NEEDS_APPROVAL:
        workflow["hil_prompt"] = {
            "title": "Additional evidence recommended",
            "body": (
                "Version evidence from CMDB/Device MCP shows four gateways on affected firmware, but Agilus MCP "
                "can cross-reference installed builds against the vendor emergency patch catalog and confirm "
                "whether versions are outdated relative to the bulletin."
            ),
            "approve_label": "Connect Agilus MCP",
            "skip_label": "Continue without Agilus",
            "approve_follow_up_id": "approve_investigation_vuln_scan",
            "skip_follow_up_id": "skip_investigation_vuln_scan",
            "connector": "Agilus MCP",
            "connection_trace": [
                {"label": "Resolve Agilus MCP endpoint from governed registry", "status": "complete"},
                {"label": "Verify service account and read-only patch-catalog scope", "status": "complete"},
                {"label": "Map VPN-GW-01/02/05/08 installed versions to vendor catalog", "status": "active"},
                {"label": "Return emergency patch EG-VPN-12.3.5-EMERG eligibility", "status": "pending"},
            ],
        }

    if investigation_done and "generate_executive_summary" in applied and executive_summary:
        workflow["executive_summary"] = list(executive_summary)

    if lifecycle == LIFECYCLE_INVESTIGATION_COMPLETE:
        workflow["next_step_cta"] = {
            "label": "Continue to remediation plan",
            "follow_up_id": "create_remediation_plan",
        }

    if lifecycle == LIFECYCLE_COMPLETE:
        workflow["final_summary"] = {
            "headline": "Exposure contained",
            "severity": "P1",
            "affected": "4 affected gateways",
            "compromise": "compromise not confirmed",
            "completed": [
                "4 affected gateways identified",
                "WAN restriction escalated to network ops",
                "Step-up MFA requested via IAM (change window pending)",
                "P1 incident INC-48219 created",
                "Emergency patch change CHG-29173 submitted",
                "Temporary Splunk monitoring enabled",
                "Network and SOC notified",
            ],
            "in_progress": ["IAM MFA policy publication", "Emergency patch deployment"],
            "risk_from": "HIGH",
            "risk_to": "MEDIUM",
            "risk_note": (
                "No evidence currently confirms exploitation. Monitoring remains active until "
                "patch verification completes."
            ),
        }

    if lifecycle in {LIFECYCLE_VERIFYING, LIFECYCLE_COMPLETE}:
        workflow["verification"] = [
            {"item": "Temporary control applied", "status": "VERIFIED", "detail": "WAN management restricted on 4/4 gateways"},
            {"item": "Incident created", "status": "VERIFIED", "detail": "INC-48219"},
            {"item": "Change request exists", "status": "ACCEPTED", "detail": "CHG-29173 — awaiting Agilus callback"},
            {"item": "Monitoring prepared", "status": "CANDIDATE", "detail": "Splunk alert candidate prepared — not deployed"},
            {"item": "Stakeholder notification", "status": "REQUESTED", "detail": "Network + SOC owners notified"},
        ]

    if investigation_done:
        workflow["investigation_results"] = {
            "header": "Investigation results",
            "steps": [
                step
                for step in investigation_steps
                if (step.get("selected", True) or step.get("added_by_agent"))
                and not (
                    step["id"] == "auth_anomalies"
                    and agent_state.get("adaptation_added")
                    and str(step.get("status") or "").upper() == "SKIPPED"
                )
            ],
        }
    if lifecycle in {LIFECYCLE_INVESTIGATING, LIFECYCLE_INVESTIGATION_NEEDS_APPROVAL}:
        workflow["execution_progress"] = {
            "phase": "investigation",
            "header": "Investigation in progress",
            "steps": investigation_steps,
        }
    elif lifecycle in {LIFECYCLE_REMEDIATING, LIFECYCLE_VERIFYING}:
        workflow["execution_progress"] = {
            "phase": "remediation",
            "header": "Remediation in progress",
            "steps": remediation_steps,
        }

    return workflow


def handle_s4_agent_follow_up(
    *,
    session_id: str,
    family: str,
    scenario_id: str,
    follow_up_id: str,
    agent_payload: dict[str, Any] | None,
    session_record: dict[str, Any],
) -> dict[str, Any] | None:
    """Apply S4 agent orchestration. Returns updated session_record or None if not handled."""
    if scenario_id != S4_SCENARIO_ID:
        return None

    agent_state = get_agent_state(session_id, family)
    payload = agent_payload or {}

    if follow_up_id == "run_investigation":
        session_record = ec_fsm_store.apply_follow_up(
            session_id, family, scenario_id=scenario_id, follow_up_id=follow_up_id
        )
        selected = payload.get("selected_step_ids") or agent_state.get("investigation_selected") or []
        agent_state["investigation_selected"] = list(selected)
        phase1 = [fid for fid in _selected_investigation_follow_ups(selected) if fid in {"run_network_assessment", "run_splunk_ioc_hunt"}]
        session_record = _apply_follow_ups(session_id, family, scenario_id, phase1)
        agent_state["lifecycle"] = LIFECYCLE_INVESTIGATION_NEEDS_APPROVAL
        agent_state["adaptation_added"] = "run_splunk_ioc_hunt" in phase1
        if "agilus_patch_analysis" in selected:
            agent_state["agilus_analysis_decision"] = "approved"
            return _continue_investigation_after_hil(
                session_id=session_id,
                family=family,
                scenario_id=scenario_id,
                agent_state=agent_state,
                include_agilus=True,
                session_record=session_record,
            )
        save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=agent_state)
        return ec_fsm_store.get_ec_session(session_id, family) or session_record

    if follow_up_id == "approve_investigation_vuln_scan":
        session_record = ec_fsm_store.apply_follow_up(
            session_id, family, scenario_id=scenario_id, follow_up_id=follow_up_id
        )
        agent_state["agilus_analysis_decision"] = "approved"
        return _continue_investigation_after_hil(
            session_id=session_id,
            family=family,
            scenario_id=scenario_id,
            agent_state=agent_state,
            include_agilus=True,
            session_record=session_record,
        )

    if follow_up_id == "skip_investigation_vuln_scan":
        session_record = ec_fsm_store.apply_follow_up(
            session_id, family, scenario_id=scenario_id, follow_up_id=follow_up_id
        )
        agent_state["agilus_analysis_decision"] = "skipped"
        return _continue_investigation_after_hil(
            session_id=session_id,
            family=family,
            scenario_id=scenario_id,
            agent_state=agent_state,
            include_agilus=False,
            session_record=session_record,
        )

    if follow_up_id == "run_remediation":
        if agent_state.get("lifecycle") not in {
            LIFECYCLE_REMEDIATION_PLAN_READY,
            LIFECYCLE_REMEDIATING,
        }:
            return ec_fsm_store.get_ec_session(session_id, family) or session_record
        session_record = ec_fsm_store.apply_follow_up(
            session_id, family, scenario_id=scenario_id, follow_up_id=follow_up_id
        )
        selected = payload.get("selected_step_ids") or agent_state.get("remediation_selected") or []
        agent_state["remediation_selected"] = list(selected)
        agent_state["lifecycle"] = LIFECYCLE_REMEDIATING
        save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=agent_state)
        follow_ups = _selected_remediation_follow_ups(selected)
        session_record = _apply_follow_ups(session_id, family, scenario_id, follow_ups)
        agent_state["remediation_execute_pending"] = True
        agent_state["lifecycle"] = LIFECYCLE_REMEDIATING
        save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=agent_state)
        return ec_fsm_store.get_ec_session(session_id, family) or session_record

    if follow_up_id == "create_remediation_plan":
        session_record = ec_fsm_store.apply_follow_up(
            session_id, family, scenario_id=scenario_id, follow_up_id=follow_up_id
        )
        agent_state["lifecycle"] = LIFECYCLE_REMEDIATION_PLAN_READY
        save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=agent_state)
        return ec_fsm_store.get_ec_session(session_id, family) or session_record

    if follow_up_id == "decline_remediation_plan":
        session_record = ec_fsm_store.apply_follow_up(
            session_id, family, scenario_id=scenario_id, follow_up_id=follow_up_id
        )
        agent_state["remediation_declined"] = True
        save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=agent_state)
        return ec_fsm_store.get_ec_session(session_id, family) or session_record

    if follow_up_id == "update_investigation_plan":
        if payload.get("selected_step_ids"):
            agent_state["investigation_selected"] = list(payload["selected_step_ids"])
        save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=agent_state)
        return ec_fsm_store.get_ec_session(session_id, family) or session_record

    if follow_up_id == "update_remediation_plan":
        if payload.get("selected_step_ids"):
            agent_state["remediation_selected"] = list(payload["selected_step_ids"])
        save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=agent_state)
        return ec_fsm_store.get_ec_session(session_id, family) or session_record

    if follow_up_id == "generate_executive_summary":
        session_record = ec_fsm_store.apply_follow_up(
            session_id, family, scenario_id=scenario_id, follow_up_id=follow_up_id
        )
        return ec_fsm_store.get_ec_session(session_id, family) or session_record

    return None


def _continue_investigation_after_hil(
    *,
    session_id: str,
    family: str,
    scenario_id: str,
    agent_state: dict[str, Any],
    include_agilus: bool,
    session_record: dict[str, Any],
) -> dict[str, Any]:
    selected = list(agent_state.get("investigation_selected") or [])
    tail_follow_ups = [
        fid
        for fid in _selected_investigation_follow_ups(selected)
        if fid in {"check_soar_playbooks", "show_incident_response_plan"}
    ]
    if "ir_guidance" in selected and "show_hardening_guidance" not in tail_follow_ups:
        tail_follow_ups.append("show_hardening_guidance")
    if include_agilus and "agilus_patch_analysis" not in selected:
        selected.append("agilus_patch_analysis")
        agent_state["investigation_selected"] = selected
    if include_agilus:
        tail_follow_ups.insert(0, "check_agilus_patch")
    agent_state["lifecycle"] = LIFECYCLE_INVESTIGATING
    save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=agent_state)
    session_record = _apply_follow_ups(session_id, family, scenario_id, tail_follow_ups)
    agent_state["lifecycle"] = LIFECYCLE_INVESTIGATION_COMPLETE
    save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=agent_state)
    return ec_fsm_store.get_ec_session(session_id, family) or session_record


def init_s4_agent_state(session_id: str, family: str, scenario_id: str) -> dict[str, Any]:
    state = _default_agent_state()
    return save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=state)
