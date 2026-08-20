"""S7 agent orchestration — EC-only. Not imported by production /chat."""

from __future__ import annotations

from typing import Any

from app.demo import ec_actions, ec_fsm_store
from app.demo.ec_agent import lifecycle as L
from app.demo.fixtures.s7.agent_config import (
    ACTION_PLAN_STEPS,
    ACTION_PLAN_SUMMARY,
    BRIEF,
    CONVERSATIONAL_FOLLOWUPS,
    INVESTIGATION_PLAN_SUMMARY,
    INVESTIGATION_STEP_DEFS,
    OPENING_NARRATIVE,
    REMEDIATION_STEP_DEFS,
    S7_SCENARIO_ID,
)
from app.demo.fixtures.s7.investigation_findings import finding_for_investigation_step
from app.demo.fixtures.s7.investigation_state import (
    build_s7_normalized_investigation_state,
    enrich_finding_metadata,
)
from app.demo.fixtures.s7.remediation_plan import (
    build_s7_remediation_conclusion,
    build_s7_remediation_summary,
    enrich_remediation_steps,
)


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
    }


def get_s7_agent_state(session_id: str | None, family: str) -> dict[str, Any]:
    return L.get_agent_state(session_id, family, default_state=default_agent_state())


def init_s7_agent_state(session_id: str, family: str, scenario_id: str) -> dict[str, Any]:
    return L.save_agent_state(
        session_id, family, scenario_id=scenario_id, agent_state=default_agent_state()
    )


def s7_followups_for_agent_mode(lifecycle: str, applied: list[str] | None = None) -> list[Any]:
    from app.demo.fixtures.s7.pack import S7_FOLLOWUPS

    applied_ids = set(applied or [])
    if lifecycle == L.LIFECYCLE_COMPLETE:
        if "generate_executive_summary" in applied_ids:
            return []
        return [chip for chip in S7_FOLLOWUPS if chip.follow_up_id in CONVERSATIONAL_FOLLOWUPS]
    return []


def finalize_s7_remediation_after_apply(
    *,
    session_id: str,
    family: str,
    scenario_id: str,
    agent_state: dict[str, Any],
    applied: list[str],
) -> dict[str, Any]:
    del applied
    if not agent_state.get("remediation_execute_pending"):
        return agent_state

    state = dict(agent_state)
    state["lifecycle"] = L.LIFECYCLE_REMEDIATING
    L.save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=state)

    L.auto_execute_pending_actions(session_id, scenario_id)

    stuck = [
        item
        for item in ec_actions.list_actions_for_session(session_id, scenario_id)
        if item.state == "APPROVAL_REQUIRED"
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
    if not step_def:
        return "SKIPPED"

    follow_up_id = step_def.get("follow_up_id")
    bundle_with = step_def.get("bundle_with")
    if follow_up_id and follow_up_id in applied:
        return "COMPLETE"
    if bundle_with and bundle_with in applied:
        return "COMPLETE"
    return "SKIPPED"


def _build_investigation_step_row(
    step: dict[str, Any],
    *,
    inv_selected: list[str],
    applied: list[str],
    agent_state: dict[str, Any],
    outcome: dict[str, Any],
) -> dict[str, Any]:
    selected = step["id"] in inv_selected
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
        "provenance": "SIMULATED" if step.get("follow_up_id") else "FIXTURE",
    }


def _result_for_remediation_step(step_id: str, applied: list[str], actions: list[Any]) -> str | None:
    if step_id == "ask_ot" and "ask_ot_team" in applied:
        email = next((item for item in actions if getattr(item, "kind", None) == "email_send"), None)
        if email is not None and email.state in {"EXECUTED", "VERIFIED"}:
            return "OT team notified"
        return "Draft pending send"
    if step_id == "ingest_ot" and "ingest_ot_response" in applied:
        return "OT reply ingested"
    if step_id == "create_incident" and "create_incident_ticket" in applied:
        return "Incident INC-OT-14 opened"
    if step_id == "cmdb_correction" and "recommend_cmdb_correction" in applied:
        return "CMDB correction ticket opened"
    if step_id == "closure" and "generate_closure_summary" in applied:
        return "Closed after conflict resolution"
    return None


def build_s7_agent_workflow(
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
    ]
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
            "provenance": "SIMULATED",
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
            "summary": "HIL-gated OT confirmation, then incident and CMDB correction — batch-executed after one approval.",
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
        normalized = build_s7_normalized_investigation_state(
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
            for key in ("device", "path", "device_active", "cmdb_stale", "recycled_identity", "forced_incident")
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
            workflow["remediation_summary"] = build_s7_remediation_summary(
                selected_count=len(selected_rem),
                total_count=len(remediation_steps),
            )
            workflow["remediation_conclusion"] = build_s7_remediation_conclusion(normalized=normalized)
            workflow["remediation_plan"]["steps"] = remediation_steps
            workflow["remediation_results"] = {"header": "Remediation plan", "steps": remediation_steps}

    if investigation_done and "generate_executive_summary" in applied and executive_summary:
        workflow["executive_summary"] = list(executive_summary)

    if lifecycle == L.LIFECYCLE_INVESTIGATION_COMPLETE:
        workflow["next_step_cta"] = {
            "label": "Continue to remediation plan",
            "follow_up_id": "create_remediation_plan",
        }

    if lifecycle == L.LIFECYCLE_COMPLETE:
        path_b = bool((workflow.get("normalized_state") or {}).get("recycled_identity"))
        workflow["final_summary"] = {
            "title": "OT conflict investigation completed",
            "headline": (
                "Recycled identity · not an incident · CMDB process correction"
                if path_b
                else "Device active · CMDB stale · incident after conflict resolution"
            ),
            "severity": "P2",
            "affected": "OT-RTU-14",
            "compromise": "not confirmed from Splunk alone",
            "completed": (
                [
                    "Splunk unauthorized-access telemetry confirmed",
                    "CMDB retirement consistent with recycled identity",
                    "No live-device compromise",
                    "CMDB data-quality ticket opened",
                ]
                if path_b
                else [
                    "Splunk unauthorized-access telemetry confirmed",
                    "OT inventory shows OT-RTU-14 active on cell 4",
                    "CMDB retirement is stale",
                    "OT team notified (simulated HIL email)",
                    "Security incident INC-OT-14 opened",
                    "CMDB data-quality ticket opened",
                ]
            ),
            "in_progress": [],
            "risk_from": "HIGH",
            "risk_to": "MEDIUM",
            "risk_note": (
                "A recycled identity is not a live compromise."
                if path_b
                else "Splunk telemetry plus a live device is a real concern; CMDB retirement was not proof the asset was gone."
            ),
        }

    if lifecycle in {L.LIFECYCLE_VERIFYING, L.LIFECYCLE_COMPLETE}:
        path_b = bool((workflow.get("normalized_state") or {}).get("recycled_identity"))
        workflow["verification"] = [
            {"item": "Splunk telemetry", "status": "VERIFIED", "detail": "Unauthorized-access events for OT-RTU-14"},
            {
                "item": "Device live?",
                "status": "NOT_CONFIRMED" if path_b else "VERIFIED",
                "detail": "Recycled identity" if path_b else "OT inventory active on cell 4",
            },
            {
                "item": "Incident from Splunk alone",
                "status": "BLOCKED",
                "detail": "Conflict resolved before ticket",
            },
            {
                "item": "OT notification",
                "status": "REQUESTED" if "ask_ot_team" in applied else "SKIPPED",
                "detail": "Logical recipient OT_TEAM",
            },
        ]

    if investigation_done:
        workflow["investigation_results"] = {
            "header": "Investigation results",
            "steps": [step for step in investigation_steps if step.get("selected", True)],
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


def handle_s7_agent_follow_up(
    *,
    session_id: str,
    family: str,
    scenario_id: str,
    follow_up_id: str,
    agent_payload: dict[str, Any] | None,
    session_record: dict[str, Any],
) -> dict[str, Any] | None:
    if scenario_id != S7_SCENARIO_ID:
        return None

    agent_state = get_s7_agent_state(session_id, family)
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
        follow_ups = L.selected_follow_ups(REMEDIATION_STEP_DEFS, list(selected))
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
