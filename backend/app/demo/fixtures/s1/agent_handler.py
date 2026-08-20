"""S1 agent orchestration — EC-only. Not imported by production /chat."""

from __future__ import annotations

from typing import Any

from app.demo import ec_actions, ec_fsm_store
from app.demo.ec_agent import lifecycle as L
from app.demo.ec_mcp_lifecycle_fixture import PRIMARY_ATTACKER_IP
from app.demo.fixtures.s1.agent_config import (
    ACTION_PLAN_STEPS,
    ACTION_PLAN_SUMMARY,
    ADAPTATION_STEP,
    BRIEF,
    INVESTIGATION_PLAN_SUMMARY,
    INVESTIGATION_STEP_DEFS,
    OPENING_NARRATIVE,
    REMEDIATION_STEP_DEFS,
    S1_SCENARIO_ID,
)
from app.demo.fixtures.s1.investigation_findings import finding_for_investigation_step
from app.demo.fixtures.s1.investigation_state import (
    build_s1_normalized_investigation_state,
    enrich_finding_metadata,
)
from app.demo.fixtures.s1.remediation_plan import (
    REM_OPERATIONAL_STATUS,
    S1_MONITOR_SAVED_SEARCH_NAME,
    S1_PLANNED_INCIDENT_ID,
    build_s1_remediation_conclusion,
    build_s1_remediation_summary,
    enrich_remediation_steps,
)

# Firewall stays unexecuted — SOP threshold is not met. Other rem actions run after Approve.
_HIL_ACTION_KINDS = {"firewall_block"}


def default_agent_state() -> dict[str, Any]:
    return {
        "lifecycle": L.LIFECYCLE_PLAN_READY,
        "investigation_selected": [
            step["id"] for step in INVESTIGATION_STEP_DEFS if step.get("default_selected", True)
        ],
        "remediation_selected": [step["id"] for step in REMEDIATION_STEP_DEFS],
        "investigation_progress": [],
        "remediation_progress": [],
        "verification": [],
        "adaptation_added": False,
        "block_threshold_met": False,
        "remediation_declined": False,
    }


def get_s1_agent_state(session_id: str | None, family: str) -> dict[str, Any]:
    return L.get_agent_state(session_id, family, default_state=default_agent_state())


def init_s1_agent_state(session_id: str, family: str, scenario_id: str) -> dict[str, Any]:
    return L.save_agent_state(
        session_id, family, scenario_id=scenario_id, agent_state=default_agent_state()
    )


def s1_followups_for_agent_mode(lifecycle: str, applied: list[str] | None = None) -> list[Any]:
    del lifecycle, applied
    # Executive summary is auto-populated after investigation. Agent mode owns every action.
    return []


def finalize_s1_remediation_after_apply(
    *,
    session_id: str,
    family: str,
    scenario_id: str,
    agent_state: dict[str, Any],
    applied: list[str],
) -> dict[str, Any]:
    if not agent_state.get("remediation_execute_pending"):
        return agent_state

    state = dict(agent_state)
    state["lifecycle"] = L.LIFECYCLE_REMEDIATING
    L.save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=state)

    pending = [
        item
        for item in ec_actions.list_actions_for_session(session_id, scenario_id)
        if item.state == "APPROVAL_REQUIRED"
    ]
    for action in pending:
        if action.kind in _HIL_ACTION_KINDS:
            continue
        approved = ec_actions.approve_action(action.action_id)
        executed = ec_actions.execute_action(approved.action_id)
        if action.kind == "email_send" and executed.state != "EXECUTED":
            ec_actions.record_fixture_execution(
                approved.action_id,
                summary="SOC notification delivered to FIREWALL_TEAM",
            )

    stuck = [
        item
        for item in ec_actions.list_actions_for_session(session_id, scenario_id)
        if item.state == "APPROVAL_REQUIRED" and item.kind not in _HIL_ACTION_KINDS
    ]
    state["remediation_execute_pending"] = False
    if stuck:
        state["lifecycle"] = L.LIFECYCLE_PARTIAL
        state["remediation_blocked"] = [item.label for item in stuck]
    else:
        state["lifecycle"] = L.LIFECYCLE_VERIFYING
        L.save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=state)
        state["lifecycle"] = L.LIFECYCLE_COMPLETE
    L.save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=state)
    return state


def _step_status(
    *,
    step_id: str,
    applied: list[str],
    agent_state: dict[str, Any],
    phase: str,
) -> str:
    lifecycle = agent_state.get("lifecycle", L.LIFECYCLE_PLAN_READY)
    progress = (
        agent_state.get("investigation_progress") or []
        if phase == "investigation"
        else agent_state.get("remediation_progress") or []
    )
    for row in progress:
        if row.get("id") == step_id:
            return str(row.get("status") or "QUEUED")

    if lifecycle == L.LIFECYCLE_PLAN_READY:
        return "QUEUED"
    if lifecycle == L.LIFECYCLE_REMEDIATION_PLAN_READY and phase == "remediation":
        return "QUEUED"

    defs = INVESTIGATION_STEP_DEFS if phase == "investigation" else REMEDIATION_STEP_DEFS
    step_def = next((item for item in defs if item["id"] == step_id), None)
    if step_def is None and step_id == ADAPTATION_STEP["id"]:
        step_def = ADAPTATION_STEP
    if not step_def:
        return "SKIPPED"

    follow_up_id = step_def.get("follow_up_id")
    bundle_with = step_def.get("bundle_with")
    applied_hit = bool(
        (follow_up_id and follow_up_id in applied) or (bundle_with and bundle_with in applied)
    )
    if phase == "remediation" and applied_hit:
        if lifecycle in {
            L.LIFECYCLE_COMPLETE,
            L.LIFECYCLE_VERIFYING,
            L.LIFECYCLE_PARTIAL,
            L.LIFECYCLE_REMEDIATING,
        }:
            return REM_OPERATIONAL_STATUS.get(step_id, "COMPLETE")
        return "COMPLETE"
    if follow_up_id and follow_up_id in applied:
        return "COMPLETE"
    if bundle_with and bundle_with in applied:
        return "COMPLETE"
    if phase == "remediation" and step_id == "prepare_block" and lifecycle in {
        L.LIFECYCLE_COMPLETE,
        L.LIFECYCLE_VERIFYING,
        L.LIFECYCLE_PARTIAL,
    }:
        return "NOT_REQUIRED"
    return "SKIPPED"


def _build_investigation_step_row(
    step: dict[str, Any],
    *,
    inv_selected: list[str],
    applied: list[str],
    agent_state: dict[str, Any],
    outcome: dict[str, Any],
) -> dict[str, Any]:
    selected = step["id"] in inv_selected or bool(
        step.get("added_by_agent") and agent_state.get("adaptation_added")
    )
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
    finding = enrich_finding_metadata(finding, step_id=step["id"])
    headline = (finding or {}).get("headline_finding")
    return {
        **step,
        "summary": step.get("summary"),
        "selected": selected,
        "status": status,
        "finding": finding,
        "result": headline,
        "provenance": "GOVERNED" if step.get("follow_up_id") else "FIXTURE",
    }


def _result_for_remediation_step(step_id: str, applied: list[str], actions: list[Any]) -> str | None:
    if step_id in {"generate_spl", "validate_spl"} and "prepare_monitoring_detection" in applied:
        return "14-day monitoring SPL generated and verified"
    if step_id in {"deploy_monitoring", "verify_monitoring"} and "raise_mcp_monitoring" in applied:
        notify = next((item for item in actions if getattr(item, "kind", None) == "notify"), None)
        if step_id == "deploy_monitoring":
            if notify is not None and notify.state in {"EXECUTED", "VERIFIED"}:
                return f"Baseline query executed · schedule {S1_MONITOR_SAVED_SEARCH_NAME} in Splunk"
            return "Running baseline splunk_run_query"
        if notify is not None and notify.state in {"EXECUTED", "VERIFIED"}:
            return "Query replay verified · saved search scheduling pending"
        return "Re-running splunk_run_query"
    if step_id == "create_incident" and "create_incident_ticket" in applied:
        ticket = next((item for item in actions if getattr(item, "kind", None) == "ticket_create"), None)
        if ticket is not None and ticket.state in {"EXECUTED", "VERIFIED"}:
            return f"Incident created · {S1_PLANNED_INCIDENT_ID}"
        return f"Creating incident {S1_PLANNED_INCIDENT_ID}"
    if step_id == "monitor_14d" and "monitor_affected_hosts" in applied:
        return "14-day jump-host and svc_jump_ops watch ACTIVE"
    if step_id == "prepare_block" and "prepare_firewall_block" in applied:
        return "Conditional IP block · NOT REQUIRED YET"
    if step_id == "notify_firewall" and "email_firewall_team" in applied:
        email = next((item for item in actions if getattr(item, "kind", None) == "email_send"), None)
        if email is not None and email.state in {"EXECUTED", "VERIFIED"}:
            return "SOC team notified"
        return "Sending SOC notification"
    if step_id == "update_ticket" and "update_incident" in applied:
        ticket = next((item for item in actions if getattr(item, "kind", None) == "ticket_update"), None)
        if ticket is not None and ticket.state in {"EXECUTED", "VERIFIED"}:
            return f"Incident updated · {S1_PLANNED_INCIDENT_ID}"
        return "Updating incident"
    return None


def build_s1_agent_workflow(
    *,
    agent_state: dict[str, Any],
    applied: list[str],
    actions: list[Any],
    outcome: dict[str, Any] | None = None,
    executive_summary: list[str] | None = None,
) -> dict[str, Any]:
    lifecycle = str(agent_state.get("lifecycle") or L.LIFECYCLE_PLAN_READY)
    outcome = outcome or {}
    phase = L.workflow_phase(lifecycle)
    inv_selected = list(agent_state.get("investigation_selected") or [])
    rem_selected = list(agent_state.get("remediation_selected") or [])
    investigation_done = lifecycle in {
        L.LIFECYCLE_INVESTIGATION_COMPLETE,
        L.LIFECYCLE_REMEDIATION_PLAN_READY,
        L.LIFECYCLE_REMEDIATING,
        L.LIFECYCLE_VERIFYING,
        L.LIFECYCLE_COMPLETE,
        L.LIFECYCLE_PARTIAL,
    }

    investigation_steps = [
        _build_investigation_step_row(
            step,
            inv_selected=inv_selected,
            applied=applied,
            agent_state=agent_state,
            outcome=outcome,
        )
        for step in INVESTIGATION_STEP_DEFS
        if not step.get("added_by_agent")
    ]
    if agent_state.get("adaptation_added"):
        adapted = _build_investigation_step_row(
            ADAPTATION_STEP,
            inv_selected=inv_selected,
            applied=applied,
            agent_state=agent_state,
            outcome=outcome,
        )
        insert_at = next(
            (index + 1 for index, step in enumerate(investigation_steps) if step["id"] == "requested_30d"),
            len(investigation_steps),
        )
        investigation_steps.insert(insert_at, adapted)
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
            "result": _result_for_remediation_step(step["id"], applied, actions),
            "provenance": "GOVERNED",
        }
        for step in REMEDIATION_STEP_DEFS
    ]

    workflow: dict[str, Any] = {
        "lifecycle": lifecycle,
        "phase": phase,
        "opening_narrative": OPENING_NARRATIVE,
        "brief": BRIEF,
        "action_plan": {"summary": ACTION_PLAN_SUMMARY, "steps": list(ACTION_PLAN_STEPS)},
        "investigation_plan": {
            "editable": lifecycle == L.LIFECYCLE_PLAN_READY,
            "summary": INVESTIGATION_PLAN_SUMMARY,
            "primary_cta": "Run investigation",
            "secondary_cta": "Edit plan",
            "steps": investigation_steps,
        },
        "remediation_plan": {
            "editable": lifecycle == L.LIFECYCLE_REMEDIATION_PLAN_READY,
            "summary": "SOP: raise MCP IP monitoring first, then HIL block if required — batch-executed after one approval.",
            "primary_cta": "Approve remediation",
            "secondary_cta": "Modify plan",
            "steps": remediation_steps,
            "visible": lifecycle
            in {
                L.LIFECYCLE_REMEDIATION_PLAN_READY,
                L.LIFECYCLE_REMEDIATION_APPROVED,
                L.LIFECYCLE_REMEDIATING,
                L.LIFECYCLE_VERIFYING,
                L.LIFECYCLE_COMPLETE,
                L.LIFECYCLE_PARTIAL,
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

    if investigation_done:
        normalized = build_s1_normalized_investigation_state(
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
                "indicator",
                "notable_fired",
                "newly_observed",
                "mcp_endpoint",
                "malicious_confirmed",
                "jump_host",
            )
        }
        if lifecycle in {
            L.LIFECYCLE_REMEDIATION_PLAN_READY,
            L.LIFECYCLE_REMEDIATING,
            L.LIFECYCLE_VERIFYING,
            L.LIFECYCLE_COMPLETE,
            L.LIFECYCLE_PARTIAL,
        }:
            selected_rem = [step for step in remediation_steps if step.get("selected", True)]
            remediation_steps = enrich_remediation_steps(
                remediation_steps, normalized=normalized, applied=applied
            )
            workflow["remediation_summary"] = build_s1_remediation_summary(
                selected_count=len(selected_rem),
                total_count=len(remediation_steps),
            )
            workflow["remediation_conclusion"] = build_s1_remediation_conclusion(normalized=normalized)
            workflow["remediation_plan"]["steps"] = remediation_steps
            workflow["remediation_results"] = {"header": "Remediation plan", "steps": remediation_steps}

    if investigation_done:
        summary = list(executive_summary or [])
        if summary:
            workflow["executive_summary"] = summary

    if lifecycle == L.LIFECYCLE_INVESTIGATION_COMPLETE:
        if agent_state.get("remediation_declined"):
            workflow["next_step_cta"] = None
            workflow["remediation_offer"] = None
        else:
            workflow["next_step_cta"] = {
                "label": "Yes, create remediation plan",
                "follow_up_id": "create_remediation_plan",
            }
            workflow["remediation_offer"] = {
                "title": "Continue to remediation plan?",
                "body": (
                    "SOP default is targeted monitoring. A block is not justified merely because the IP is new. "
                    "Create the remediation plan only if you want to proceed."
                ),
                "yes_label": "Yes, create remediation plan",
                "no_label": "Not now",
                "yes_follow_up_id": "create_remediation_plan",
                "no_follow_up_id": "decline_remediation_plan",
            }

    if lifecycle == L.LIFECYCLE_COMPLETE:
        workflow["final_summary"] = {
            "title": "RESPONSE COMPLETE",
            "headline": "Baseline monitoring query executed · saved search scheduling pending · malicious use not confirmed",
            "severity": "P2",
            "affected": PRIMARY_ATTACKER_IP,
            "compromise": "not confirmed",
            "completed": [
                "Baseline monitoring query executed via splunk_run_query",
                "Jump-host 443/8443 baseline reviewed",
                "svc_jump_ops auth correlation reviewed",
                f"Incident {S1_PLANNED_INCIDENT_ID} created",
                "SOC notified",
                "Incident updated",
            ],
            "in_progress": [
                "14-day monitoring window",
                f"Schedule {S1_MONITOR_SAVED_SEARCH_NAME} saved search in Splunk (manual — no MCP deploy tool)",
            ],
            "deferred": ["IP block not required at current SOP threshold"],
            "risk_from": "MEDIUM",
            "risk_to": "MEDIUM",
            "risk_note": (
                "Current risk: MEDIUM. Malicious use: NOT CONFIRMED. "
                "Baseline query: EXECUTED. Saved search: SCHEDULE MANUALLY. Blocking: CONDITIONAL."
            ),
        }

    if lifecycle in {L.LIFECYCLE_VERIFYING, L.LIFECYCLE_COMPLETE}:
        workflow["verification"] = [
            {"item": "Existing IOC detection", "status": "NO_ALERT", "detail": "IP not present in the IOC list used by this detection"},
            {"item": "Newly observed", "status": "VERIFIED", "detail": "Prior 30-day window empty"},
            {"item": "Identity", "status": "VERIFIED", "detail": "Registered MCP endpoint (inventory evidence)"},
            {"item": "Permitted sessions", "status": "UNEXPLAINED", "detail": "3 allows on 10.20.1.10 remain unexplained; auth src not proven"},
            {"item": "Malicious use", "status": "NOT_CONFIRMED", "detail": "Unlisted locally; no confirmed compromise"},
            {"item": "Monitoring", "status": "IN_PROGRESS", "detail": "splunk_run_query baseline executed; schedule saved search manually"},
            {"item": "Block", "status": "NOT_REQUIRED", "detail": "SOP blocking threshold not met — not executed"},
        ]

    if investigation_done:
        workflow["investigation_results"] = {
            "header": "Investigation results",
            "steps": [
                step
                for step in investigation_steps
                if step.get("selected", True) or step.get("added_by_agent")
            ],
        }
    if lifecycle in {L.LIFECYCLE_INVESTIGATING, L.LIFECYCLE_INVESTIGATION_NEEDS_APPROVAL}:
        workflow["execution_progress"] = {
            "phase": "investigation",
            "header": "Investigation in progress",
            "steps": investigation_steps,
        }
    elif lifecycle in {L.LIFECYCLE_REMEDIATING, L.LIFECYCLE_VERIFYING}:
        workflow["execution_progress"] = {
            "phase": "remediation",
            "header": "Remediation in progress",
            "steps": remediation_steps,
        }

    return workflow


def handle_s1_agent_follow_up(
    *,
    session_id: str,
    family: str,
    scenario_id: str,
    follow_up_id: str,
    agent_payload: dict[str, Any] | None,
    session_record: dict[str, Any],
) -> dict[str, Any] | None:
    if scenario_id != S1_SCENARIO_ID:
        return None

    agent_state = get_s1_agent_state(session_id, family)
    payload = agent_payload or {}

    if follow_up_id == "run_investigation":
        session_record = ec_fsm_store.apply_follow_up(
            session_id, family, scenario_id=scenario_id, follow_up_id=follow_up_id
        )
        selected = payload.get("selected_step_ids") or agent_state.get("investigation_selected") or []
        agent_state["investigation_selected"] = list(selected)
        agent_state["lifecycle"] = L.LIFECYCLE_INVESTIGATING
        L.save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=agent_state)
        follow_ups = L.selected_follow_ups(INVESTIGATION_STEP_DEFS, list(selected))
        session_record = L.apply_follow_ups(session_id, family, scenario_id, follow_ups)
        if "search_firewall_30d" in (session_record.get("applied_follow_up_ids") or follow_ups) or (
            "requested_30d" in selected
        ):
            agent_state["adaptation_added"] = True
            selected_ids = list(agent_state.get("investigation_selected") or [])
            if ADAPTATION_STEP["id"] not in selected_ids:
                selected_ids.append(ADAPTATION_STEP["id"])
            agent_state["investigation_selected"] = selected_ids
            L.save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=agent_state)
            session_record = L.apply_follow_ups(
                session_id,
                family,
                scenario_id,
                ["investigate_permitted_sessions", "check_successful_auth"],
            )
        agent_state["lifecycle"] = L.LIFECYCLE_INVESTIGATION_COMPLETE
        L.save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=agent_state)
        return ec_fsm_store.get_ec_session(session_id, family) or session_record

    if follow_up_id == "run_remediation":
        if agent_state.get("lifecycle") not in {
            L.LIFECYCLE_REMEDIATION_PLAN_READY,
            L.LIFECYCLE_REMEDIATING,
        }:
            return ec_fsm_store.get_ec_session(session_id, family) or session_record
        session_record = ec_fsm_store.apply_follow_up(
            session_id, family, scenario_id=scenario_id, follow_up_id=follow_up_id
        )
        selected = payload.get("selected_step_ids") or agent_state.get("remediation_selected") or []
        agent_state["remediation_selected"] = list(selected)
        agent_state["lifecycle"] = L.LIFECYCLE_REMEDIATING
        L.save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=agent_state)
        follow_ups = [
            fid
            for fid in L.selected_follow_ups(REMEDIATION_STEP_DEFS, list(selected))
            if fid != "verify_firewall_block"
        ]
        session_record = L.apply_follow_ups(session_id, family, scenario_id, follow_ups)
        agent_state["remediation_execute_pending"] = True
        agent_state["lifecycle"] = L.LIFECYCLE_REMEDIATING
        L.save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=agent_state)
        return ec_fsm_store.get_ec_session(session_id, family) or session_record

    if follow_up_id == "create_remediation_plan":
        session_record = ec_fsm_store.apply_follow_up(
            session_id, family, scenario_id=scenario_id, follow_up_id=follow_up_id
        )
        agent_state["lifecycle"] = L.LIFECYCLE_REMEDIATION_PLAN_READY
        agent_state["remediation_declined"] = False
        L.save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=agent_state)
        return ec_fsm_store.get_ec_session(session_id, family) or session_record

    if follow_up_id == "decline_remediation_plan":
        session_record = ec_fsm_store.apply_follow_up(
            session_id, family, scenario_id=scenario_id, follow_up_id=follow_up_id
        )
        agent_state["remediation_declined"] = True
        L.save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=agent_state)
        return ec_fsm_store.get_ec_session(session_id, family) or session_record

    if follow_up_id == "update_investigation_plan":
        if payload.get("selected_step_ids"):
            agent_state["investigation_selected"] = list(payload["selected_step_ids"])
        L.save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=agent_state)
        return ec_fsm_store.get_ec_session(session_id, family) or session_record

    if follow_up_id == "update_remediation_plan":
        if payload.get("selected_step_ids"):
            agent_state["remediation_selected"] = list(payload["selected_step_ids"])
        L.save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=agent_state)
        return ec_fsm_store.get_ec_session(session_id, family) or session_record

    if follow_up_id == "generate_executive_summary":
        session_record = ec_fsm_store.apply_follow_up(
            session_id, family, scenario_id=scenario_id, follow_up_id=follow_up_id
        )
        return ec_fsm_store.get_ec_session(session_id, family) or session_record

    return None
