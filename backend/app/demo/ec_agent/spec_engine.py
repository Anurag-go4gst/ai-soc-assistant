"""Declarative Experience Center scenarios on the shared agent lifecycle.

A scenario is written as a :class:`ScenarioSpec` — the question, 2–3 checks, an optional check
the agent adds when the evidence asks for it, the findings, the proposed actions and the final
state. This module turns a spec into the ``ec_agent_workflow`` payload, registers it as an agent
profile and runs its lifecycle, so every scenario behaves identically:

    plan (nothing has run) → findings → proposed response (PROPOSED) → execution + verification

Rules this module enforces once for every scenario:

* Actions are PROPOSED until approved; only an executed action reports a result.
* A ticket ID appears only after the ITSM action that creates it has executed.
* Incident priority comes from :func:`ec_environment.incident_priority` and is shown next to,
  not merged with, the threat assessment.
* Every Splunk search passes the real deterministic validator before it is shown.
* Dates are rendered against the time the page is served.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.demo import ec_actions, ec_fsm_store
from app.demo import ec_environment as env
from app.demo.ec_agent import lifecycle as L
from app.demo.ec_agent.registry import register_agent_profile
from app.demo.ec_agent.tool_catalog import tool_display_name, tool_fabric
from app.demo.ec_agent.types import AgentProfile
from app.demo.ec_email import LOGICAL_TEAMS
from app.demo.ec_response import EcFollowUpChip, ExperienceCenterResponse
from app.demo.fixtures import common as C
from app.safeguards.spl_validator import validate_spl

FOLLOW_UP_IDS = frozenset(
    {
        "run_investigation",
        "create_remediation_plan",
        "decline_remediation_plan",
        "run_remediation",
        "update_investigation_plan",
        "update_remediation_plan",
    }
)

_TOOL_OPERATION = {
    "splunk_mcp": "splunk_run_query",
    "agilus_mcp": "agilus.read_device",
    "soc_kb": "soc_kb.retrieve",
    "itsm": "itsm.lookup",
    "email": "email.send",
}

# ec_actions kinds per action verb.
_KIND_BY_ACTION = {
    "incident": "ticket_create",
    "change": "ticket_create",
    "request": "ticket_create",
    "ticket_update": "ticket_update",
    "email": "email_send",
    "agilus_change": "agilus_change",
    "agilus_verify": "agilus_verify",
}

INCIDENT_PENDING_TEXT = "INC number pending"
TICKET_PENDING_TEXT = "number pending"
_TICKET_TOKEN = re.compile(r"\{ticket:([a-z0-9_]+)\}")


@dataclass(frozen=True)
class Check:
    """One investigation check. ``result`` is only shown after the check has run."""

    id: str
    title: str
    plan: str
    tool: str
    result: str
    evidence: tuple[str, ...] = ()
    spl: str | None = None
    operation: str | None = None
    attention: str = "NORMAL"
    selected: bool = True


@dataclass(frozen=True)
class Email:
    """``to``/``cc`` are shown to the analyst; ``mailbox`` is the allowlisted team mailbox it is sent to."""

    to: str
    subject: str
    body: str
    mailbox: str
    cc: str = ""


@dataclass(frozen=True)
class Action:
    """One proposed action. ``proposal`` is present tense-future; ``executed`` is past tense."""

    id: str
    title: str
    proposal: str
    tool: str
    verb: str  # incident | change | request | ticket_update | email | agilus_change | agilus_verify
    executed: str
    verified: str | None = None
    status_after: str = "EXECUTED"  # EXECUTED | REQUESTED | SCHEDULED | AWAITING_REPLY
    ticket_id: str | None = None
    email: Email | None = None
    spl: str | None = None
    selected: bool = True


@dataclass(frozen=True)
class ScenarioSpec:
    scenario_id: str
    family: str
    label: str
    question: str
    demo_order: int
    plan_intro: str
    checks: tuple[Check, ...]
    conclusion_headline: str
    points: tuple[str, ...]
    threat: str
    asset_tier: int
    evidence_state: str
    subject: str
    decision: str
    actions: tuple[Action, ...]
    final_state: str
    final_headline: str
    plan_title: str
    aliases: tuple[str, ...] = ()
    added_check: Check | None = None
    added_after: str | None = None
    added_when: tuple[str, ...] = ()  # the added check appears when any of these checks ran
    unresolved: tuple[str, ...] = ()
    not_proposed: tuple[str, ...] = ()
    pending: tuple[str, ...] = ()
    next_triggers: str = ""
    existing_incident: str | None = None
    sources: tuple[str, ...] = ()  # knowledge sources cited in the answer (RAG)
    category: str = "Flagship"
    # Earlier wording of the question: still resolves to this scenario, never suggested.
    legacy_phrasings: tuple[str, ...] = ()
    # Keep the existing catalog entry (Q1/Q2 also feed the frozen ChatPanel picker); the EC
    # catalog overlays ``question`` instead.
    keep_legacy_entry: bool = False
    assessed: bool = True  # False for non-incident asks (e.g. a baseline): no priority shown
    spl_profile: dict[str, Any] = field(default_factory=lambda: dict(env.SPL_SOURCE_PROFILE))


_SPECS: dict[str, ScenarioSpec] = {}


def spec_for(scenario_id: str) -> ScenarioSpec | None:
    return _SPECS.get(scenario_id)


def registered_spec_ids() -> tuple[str, ...]:
    return tuple(_SPECS)


# --- validation ------------------------------------------------------------------------------


def validated_spl(spec: ScenarioSpec, spl: str) -> str:
    """Return the validator-normalized SPL, or fail loudly: a fixture must not show unsafe SPL."""
    result = validate_spl(spl, template_profile=spec.spl_profile)
    if not result.get("approved") or not result.get("normalized_spl"):
        raise RuntimeError(
            f"{spec.scenario_id}: fixture SPL failed validate_spl: {result.get('reject_reasons')} :: {spl}"
        )
    return str(result["normalized_spl"])


def _check_spec(spec: ScenarioSpec) -> None:
    ids = [check.id for check in spec.checks] + ([spec.added_check.id] if spec.added_check else [])
    ids += [action.id for action in spec.actions]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{spec.scenario_id}: duplicate step ids")
    if spec.threat not in env.THREAT_ASSESSMENTS:
        raise ValueError(f"{spec.scenario_id}: unknown threat assessment {spec.threat}")
    env.incident_priority(asset_tier=spec.asset_tier, evidence_state=spec.evidence_state)
    for step in [*spec.checks, *([spec.added_check] if spec.added_check else []), *spec.actions]:
        if step.spl:
            validated_spl(spec, step.spl)
    for action in spec.actions:
        if action.verb not in _KIND_BY_ACTION:
            raise ValueError(f"{spec.scenario_id}: unknown action verb {action.verb}")
        if action.email is not None and action.email.mailbox not in LOGICAL_TEAMS:
            raise ValueError(f"{spec.scenario_id}: {action.id} mailbox {action.email.mailbox} is not an allowlisted team")
        if action.verb in {"incident", "change", "request"} and not action.ticket_id:
            raise ValueError(f"{spec.scenario_id}: {action.id} creates a ticket but has no ticket_id")


# --- agent state -----------------------------------------------------------------------------


def _default_state(spec: ScenarioSpec) -> dict[str, Any]:
    return {
        "lifecycle": L.LIFECYCLE_PLAN_READY,
        "investigation_selected": [check.id for check in spec.checks if check.selected],
        "remediation_selected": [action.id for action in spec.actions if action.selected],
        "added_check": False,
        "remediation_declined": False,
        "action_ids": {},
    }


def _state(spec: ScenarioSpec, session_id: str | None, family: str) -> dict[str, Any]:
    state = L.get_agent_state(session_id, family, default_state=_default_state(spec))
    state.setdefault("action_ids", {})
    return state


def _save(spec: ScenarioSpec, session_id: str, family: str, state: dict[str, Any]) -> None:
    L.save_agent_state(session_id, family, scenario_id=spec.scenario_id, agent_state=state)


# --- ticket IDs ------------------------------------------------------------------------------


def _incident_action(spec: ScenarioSpec) -> Action | None:
    return next((action for action in spec.actions if action.verb == "incident"), None)


def _incident_id(spec: ScenarioSpec, executed: set[str]) -> str | None:
    """The incident number, only once it exists (created here, or opened by an earlier question)."""
    if spec.existing_incident:
        return spec.existing_incident
    creator = _incident_action(spec)
    if creator is not None and creator.id in executed:
        return creator.ticket_id
    return None


def _fill(text: str, spec: ScenarioSpec, executed: set[str]) -> str:
    """Resolve ``{incident}`` and ``{ticket:<action_id>}``: a number only once its ticket exists."""
    incident = _incident_id(spec, executed)
    text = text.replace("{incident}", incident or INCIDENT_PENDING_TEXT)
    by_id = {action.id: action for action in spec.actions}

    def ticket(match: re.Match[str]) -> str:
        action = by_id.get(match.group(1))
        if action is None or not action.ticket_id:
            raise ValueError(f"{spec.scenario_id}: unknown ticket token {match.group(0)}")
        return action.ticket_id if action.id in executed else TICKET_PENDING_TEXT

    return _TICKET_TOKEN.sub(ticket, text)


def _email_payload(spec: ScenarioSpec, action: Action, executed: set[str], sent: bool) -> dict[str, Any]:
    assert action.email is not None
    to = action.email.to + (f" · cc {action.email.cc}" if action.email.cc else "")
    return {
        "to": to,
        "subject": _fill(action.email.subject, spec, executed),
        "body": _fill(action.email.body, spec, executed),
        "status": "sent" if sent else "draft",
    }


# --- workflow payload ------------------------------------------------------------------------


def _tools(tool_id: str) -> list[str]:
    return [tool_display_name(tool_id)]


def _check_row(spec: ScenarioSpec, check: Check, *, ran: bool, selected: bool, added: bool) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": check.id,
        "title": check.title,
        "summary": check.plan,
        "tools": _tools(check.tool),
        "tool_ids": [check.tool],
        "selected": selected,
        "status": "COMPLETE" if ran else ("SKIPPED" if not selected else "QUEUED"),
        "added_by_agent": added,
        "provenance": "GOVERNED",
        "result": check.result if ran else None,
        "finding": None,
    }
    if ran:
        details: dict[str, Any] = {
            "execution": check.operation or _TOOL_OPERATION.get(check.tool, check.tool),
            "connector": tool_display_name(check.tool),
        }
        if check.spl:
            details["normalized_spl"] = validated_spl(spec, check.spl)
            details["validation"] = "Passed deterministic SPL validation (scope, time bounds, result cap)"
        row["finding"] = {
            "headline_finding": check.result,
            "key_evidence": list(check.evidence),
            "attention_state": check.attention,
            "details": details,
        }
    return row


def _action_row(
    spec: ScenarioSpec,
    action: Action,
    *,
    selected: bool,
    record: Any | None,
    executed: set[str],
) -> dict[str, Any]:
    state = getattr(record, "state", None)
    ran = state in {"EXECUTED", "VERIFIED", "AWAITING_EXTERNAL_RESPONSE"}
    failed = state == "FAILED"
    if not selected and not ran:
        status, label = "SKIPPED", "Not selected"
    elif failed:
        status, label = "FAILED", "Failed"
    elif ran and state == "VERIFIED" and action.status_after == "EXECUTED":
        status, label = "VERIFIED", "Verified"
    elif ran:
        # A verified request is still only a request: the other team has not acted yet.
        status = action.status_after
        label = {
            "EXECUTED": "Executed",
            "REQUESTED": "Requested",
            "SCHEDULED": "Scheduled",
            "AWAITING_REPLY": "Sent · awaiting reply",
        }[action.status_after]
    else:
        status, label = "PROPOSED", "Pending approval"

    details: dict[str, Any] = {"connector": tool_display_name(action.tool)}
    if action.spl:
        details["normalized_spl"] = validated_spl(spec, action.spl)
    if action.email is not None:
        details["email_draft"] = _email_payload(spec, action, executed, sent=ran)
    result = None
    if ran:
        result = _fill(action.executed, spec, executed)
        if state == "VERIFIED" and action.verified:
            result = f"{result} · {_fill(action.verified, spec, executed)}"
    elif failed:
        result = str((getattr(record, "receipt", None) or {}).get("summary") or "Action failed — nothing changed")
    return {
        "id": action.id,
        "title": action.title,
        "summary": _fill(action.proposal, spec, executed),
        "tools": _tools(action.tool),
        "tool_ids": [action.tool],
        "selected": selected,
        "status": status,
        "status_label": label,
        "result": result,
        "provenance": "GOVERNED",
        "hil_required": True,
        "finding": {"headline_finding": result, "details": details} if (result or details) else None,
    }


def _assessment(spec: ScenarioSpec) -> dict[str, str]:
    priority = env.incident_priority(asset_tier=spec.asset_tier, evidence_state=spec.evidence_state)
    return {
        "incident_priority": priority["priority"],
        "priority_rule": priority["rule"],
        "priority_basis": priority["basis"],
        "threat_assessment": spec.threat,
    }


def _records_by_step(spec: ScenarioSpec, state: dict[str, Any], session_id: str) -> dict[str, Any]:
    by_id = {record.action_id: record for record in ec_actions.list_actions_for_session(session_id, spec.scenario_id)}
    return {
        step_id: by_id[action_id]
        for step_id, action_id in (state.get("action_ids") or {}).items()
        if action_id in by_id
    }


def build_workflow(spec: ScenarioSpec, *, agent_state: dict[str, Any], session_id: str) -> dict[str, Any]:
    lifecycle = str(agent_state.get("lifecycle") or L.LIFECYCLE_PLAN_READY)
    ran_investigation = lifecycle not in {L.LIFECYCLE_PLAN_READY, L.LIFECYCLE_INVESTIGATING}
    inv_selected = set(agent_state.get("investigation_selected") or [])
    rem_selected = set(agent_state.get("remediation_selected") or [])

    checks = [
        _check_row(
            spec,
            check,
            ran=ran_investigation and check.id in inv_selected,
            selected=check.id in inv_selected,
            added=False,
        )
        for check in spec.checks
    ]
    if spec.added_check is not None and agent_state.get("added_check"):
        added = _check_row(spec, spec.added_check, ran=ran_investigation, selected=True, added=True)
        position = next(
            (index + 1 for index, row in enumerate(checks) if row["id"] == spec.added_after), len(checks)
        )
        checks.insert(position, added)

    records = _records_by_step(spec, agent_state, session_id)
    executed = {
        step_id
        for step_id, record in records.items()
        if record.state in {"EXECUTED", "VERIFIED", "AWAITING_EXTERNAL_RESPONSE"}
    }
    actions = [
        _action_row(spec, action, selected=action.id in rem_selected, record=records.get(action.id), executed=executed)
        for action in spec.actions
    ]

    used_tools = {check.tool for check in spec.checks} | {action.tool for action in spec.actions}
    if spec.added_check is not None:
        used_tools.add(spec.added_check.tool)
    if any(check.spl for check in spec.checks):
        used_tools.add("spl_validator")

    remediation_visible = lifecycle in {
        L.LIFECYCLE_REMEDIATION_PLAN_READY,
        L.LIFECYCLE_REMEDIATING,
        L.LIFECYCLE_VERIFYING,
        L.LIFECYCLE_COMPLETE,
        L.LIFECYCLE_PARTIAL,
    }
    workflow: dict[str, Any] = {
        "lifecycle": lifecycle,
        "phase": L.workflow_phase(lifecycle),
        "opening_narrative": spec.plan_intro,
        "investigation_plan": {
            "editable": lifecycle == L.LIFECYCLE_PLAN_READY,
            "primary_cta": "Run investigation",
            "secondary_cta": "Edit plan",
            "steps": checks,
        },
        "remediation_plan": {
            "editable": lifecycle == L.LIFECYCLE_REMEDIATION_PLAN_READY,
            "primary_cta": "Approve selected actions",
            "visible": remediation_visible,
            "steps": actions,
        },
        "remediation_offer": None,
        "unconfirmed": [],
        "missing_evidence": [],
        "executive_summary": [],
        "hil_prompt": None,
        "investigation_conclusion": None,
        "final_summary": None,
        "tool_fabric": tool_fabric(used_tools),
    }
    if ran_investigation:
        workflow["investigation_results"] = {
            "header": "Investigation results",
            "steps": [row for row in checks if row["selected"]],
        }
        workflow["investigation_conclusion"] = {
            "title": "Findings",
            "headline": spec.conclusion_headline,
            "narrative_points": list(spec.points),
            "assessment": _assessment(spec) if spec.assessed else None,
            "sources": list(spec.sources),
        }
        workflow["unconfirmed"] = list(spec.unresolved)
    if lifecycle == L.LIFECYCLE_INVESTIGATION_COMPLETE and not agent_state.get("remediation_declined"):
        workflow["remediation_offer"] = {
            "title": "Continue to the proposed response?",
            "body": spec.decision,
            "yes_label": "Show proposed response",
            "no_label": "Not now",
            "yes_follow_up_id": "create_remediation_plan",
            "no_follow_up_id": "decline_remediation_plan",
        }
    if remediation_visible:
        workflow["remediation_results"] = {"header": "Proposed response", "steps": actions}
    if lifecycle in {L.LIFECYCLE_COMPLETE, L.LIFECYCLE_PARTIAL}:
        workflow["final_summary"] = _final_summary(spec, actions)
    return workflow


def _final_summary(spec: ScenarioSpec, actions: list[dict[str, Any]]) -> dict[str, Any]:
    done = [row for row in actions if row["status"] not in {"PROPOSED", "SKIPPED", "FAILED"}]
    failed = [row for row in actions if row["status"] == "FAILED"]
    skipped = [row for row in actions if row["status"] == "SKIPPED"]
    assessment = _assessment(spec) if spec.assessed else None
    return {
        "title": spec.final_state if not failed else "PARTIALLY COMPLETE",
        "headline": spec.final_headline,
        "assessment": assessment,
        "actions": [
            {"title": row["title"], "status": row["status"], "status_label": row["status_label"], "result": row["result"]}
            for row in done + failed
        ],
        "completed": [str(row["result"] or row["title"]) for row in done],
        "in_progress": list(spec.pending),
        "deferred": [*spec.not_proposed, *(f"Not run: {row['title']}" for row in skipped)],
        "risk_note": spec.next_triggers,
        "severity": assessment["incident_priority"] if assessment else "",
        "affected": spec.subject,
        "compromise": spec.threat.lower(),
    }


# --- lifecycle -------------------------------------------------------------------------------


def _execute_actions(spec: ScenarioSpec, state: dict[str, Any], session_id: str) -> None:
    """Run the approved actions in plan order: create → approve → execute → verify."""
    selected = set(state.get("remediation_selected") or [])
    action_ids = dict(state.get("action_ids") or {})
    executed: set[str] = set()
    for action in spec.actions:
        if action.id not in selected or action.id in action_ids:
            continue
        extra: dict[str, Any] = {}
        if action.ticket_id:
            extra["ticket"] = {"id": action.ticket_id, "type": action.verb, "summary": action.title}
        if action.email is not None:
            payload = _email_payload(spec, action, executed, sent=True)
            extra.update(
                {
                    "logical_recipient": action.email.mailbox,
                    "email": {"to": action.email.mailbox, "subject": payload["subject"], "body": payload["body"]},
                }
            )
        record = ec_actions.prepare_action(
            kind=_KIND_BY_ACTION[action.verb],
            label=action.title,
            session_id=session_id,
            scenario_id=spec.scenario_id,
            extra=extra,
        )
        record = ec_actions.approve_action(record.action_id)
        record = ec_actions.execute_action(record.action_id)
        if action.verb == "email" and record.state == "FAILED" and L._demo_mail_unconfigured(record):
            # No mail relay in this environment: the connector records delivery to the mailbox.
            record = ec_actions.record_fixture_execution(
                record.action_id, summary=f"Delivered to {action.email.to if action.email else 'recipient'}"
            )
        if record.state == "EXECUTED" and action.verified:
            record = ec_actions.verify_action(record.action_id)
        action_ids[action.id] = record.action_id
        if record.state in {"EXECUTED", "VERIFIED"}:
            executed.add(action.id)
    state["action_ids"] = action_ids


def handle_follow_up(
    spec: ScenarioSpec,
    *,
    session_id: str,
    family: str,
    follow_up_id: str,
    agent_payload: dict[str, Any] | None,
    session_record: dict[str, Any],
) -> dict[str, Any] | None:
    if follow_up_id not in FOLLOW_UP_IDS:
        return None
    state = _state(spec, session_id, family)
    payload = agent_payload or {}
    lifecycle = state.get("lifecycle")

    if follow_up_id == "update_investigation_plan" and payload.get("selected_step_ids"):
        state["investigation_selected"] = list(payload["selected_step_ids"])
    elif follow_up_id == "update_remediation_plan" and payload.get("selected_step_ids"):
        state["remediation_selected"] = list(payload["selected_step_ids"])
    elif follow_up_id == "run_investigation" and lifecycle == L.LIFECYCLE_PLAN_READY:
        selected = list(payload.get("selected_step_ids") or state.get("investigation_selected") or [])
        state["investigation_selected"] = [check.id for check in spec.checks if check.id in selected]
        # The agent adds a check only when a check whose evidence raises the question has run.
        state["added_check"] = bool(
            spec.added_check is not None and set(spec.added_when) & set(state["investigation_selected"])
        )
        state["lifecycle"] = L.LIFECYCLE_INVESTIGATION_COMPLETE
    elif follow_up_id == "create_remediation_plan" and lifecycle == L.LIFECYCLE_INVESTIGATION_COMPLETE:
        state["lifecycle"] = L.LIFECYCLE_REMEDIATION_PLAN_READY
        state["remediation_declined"] = False
    elif follow_up_id == "decline_remediation_plan" and lifecycle == L.LIFECYCLE_INVESTIGATION_COMPLETE:
        state["remediation_declined"] = True
    elif follow_up_id == "run_remediation" and lifecycle == L.LIFECYCLE_REMEDIATION_PLAN_READY:
        selected = list(payload.get("selected_step_ids") or state.get("remediation_selected") or [])
        state["remediation_selected"] = [action.id for action in spec.actions if action.id in selected]
        _execute_actions(spec, state, session_id)
        records = _records_by_step(spec, state, session_id)
        failed = any(record.state == "FAILED" for record in records.values())
        state["lifecycle"] = L.LIFECYCLE_PARTIAL if failed else L.LIFECYCLE_COMPLETE

    _save(spec, session_id, family, state)
    return ec_fsm_store.apply_follow_up(session_id, family, scenario_id=spec.scenario_id, follow_up_id=follow_up_id)


# --- turn ------------------------------------------------------------------------------------


def build_turn(
    spec: ScenarioSpec,
    *,
    session_id: str,
    turn: int,
    applied_follow_up_ids: list[str],
    pending_action_id: str | None = None,
    awaiting_external: bool = False,
    agent_state: dict[str, Any] | None = None,
) -> ExperienceCenterResponse:
    del pending_action_id, awaiting_external
    state = dict(agent_state or _default_state(spec))
    state.setdefault("action_ids", {})
    workflow = build_workflow(spec, agent_state=state, session_id=session_id)
    lifecycle = workflow["lifecycle"]
    records = list(ec_actions.list_actions_for_session(session_id, spec.scenario_id))

    if lifecycle == L.LIFECYCLE_PLAN_READY:
        title = spec.plan_title
        assessment = spec.plan_intro
    elif lifecycle in {L.LIFECYCLE_COMPLETE, L.LIFECYCLE_PARTIAL}:
        title = spec.final_headline
        assessment = spec.final_headline
    else:
        title = spec.conclusion_headline
        assessment = spec.conclusion_headline

    priority = env.incident_priority(asset_tier=spec.asset_tier, evidence_state=spec.evidence_state)
    outcome = {
        "disposition": lifecycle,
        "confirmed": [point for point in spec.points if point.lower().startswith("confirmed")],
        "unconfirmed": list(spec.unresolved),
        "missing_evidence": [],
    }
    response = C.envelope(
        scenario_id=spec.scenario_id,
        family=spec.family,
        session_id=session_id,
        turn=turn,
        applied=list(applied_follow_up_ids),
        chips=[],
        assessment=assessment,
        title=title,
        found=assessment,
        outcome=outcome,
        evidence_state=[],
        source_evidence=[],
        actions=records,
        resources=[tool["name"] for tool in workflow["tool_fabric"] if tool["used"]],
        controls=["Nothing runs until approved", "Validated SPL only", "Ticket IDs only after creation"],
        severity=priority["priority"] if spec.assessed and lifecycle != L.LIFECYCLE_PLAN_READY else "Not assessed",
        direct_line="",
        extra={
            "ec_agent_workflow": workflow,
            "ec_agent_lifecycle": lifecycle,
            "ec_workflow_state": lifecycle,
            "ec_opening_briefing": None,
        },
    )
    payload = response.model_dump()
    payload.update(_spl_governance_trace(spec, workflow))
    payload["note"] = ""
    payload["human_review"] = {**payload["human_review"], "safe_message_for_user": "Actions run only after approval."}
    return ExperienceCenterResponse.model_validate(env.render_tokens_deep(payload, now=datetime.now(timezone.utc)))


def _spl_governance_trace(spec: ScenarioSpec, workflow: dict[str, Any]) -> dict[str, Any]:
    """Candidate → validated → executed trace for the first Splunk search that ran.

    The candidate is never executed; only the validator's normalized SPL is reported as executed.
    """
    ran = {row["id"] for row in (workflow.get("investigation_results") or {}).get("steps") or []}
    checks = [*spec.checks, *([spec.added_check] if spec.added_check else [])]
    first = next((check for check in checks if check.spl and check.id in ran), None)
    if first is None:
        return {}
    validation = validate_spl(first.spl or "", template_profile=spec.spl_profile)
    approved = bool(validation.get("approved"))
    return {
        "candidate_spl": {
            "candidate_spl": first.spl,
            "execution_eligible": False,
            "generation_mode": "ec_investigation_plan",
        },
        "spl_validation": {**validation, "approved": approved, "execution_eligible": False},
        "execution": {
            "status": "simulated_receipts_packaged",
            "production_mcp_executed": False,
            "executed_spl": validation.get("normalized_spl") if approved else None,
            "block_reason": "live_mcp_not_called",
            "exact_call_authorization": "APPROVED" if approved else "BLOCKED",
            "candidate_spl_not_executed": True,
        },
    }


# --- registration ----------------------------------------------------------------------------


def register_spec(spec: ScenarioSpec) -> None:
    """Validate the spec once at import, then register it as an agent profile."""
    if spec.scenario_id in _SPECS:
        raise ValueError(f"scenario spec already registered: {spec.scenario_id}")
    _check_spec(spec)
    _SPECS[spec.scenario_id] = spec

    def _init(session_id: str, family: str, scenario_id: str) -> dict[str, Any]:
        del scenario_id
        return L.save_agent_state(session_id, family, scenario_id=spec.scenario_id, agent_state=_default_state(spec))

    def _handle(**kwargs: Any) -> dict[str, Any] | None:
        if kwargs.get("scenario_id") != spec.scenario_id:
            return None
        return handle_follow_up(
            spec,
            session_id=kwargs["session_id"],
            family=kwargs["family"],
            follow_up_id=kwargs["follow_up_id"],
            agent_payload=kwargs.get("agent_payload"),
            session_record=kwargs.get("session_record") or {},
        )

    register_agent_profile(
        AgentProfile(
            scenario_id=spec.scenario_id,
            default_agent_state=lambda: _default_state(spec),
            init_session=_init,
            handle_follow_up=_handle,
            build_workflow=lambda **kwargs: build_workflow(
                spec, agent_state=kwargs.get("agent_state") or {}, session_id=str(kwargs.get("session_id") or "")
            ),
            followups_for_agent_mode=lambda lifecycle, applied=None: [],
        )
    )


def followup_chips() -> list[EcFollowUpChip]:
    """Agent mode owns every action; no chips are offered."""
    return []


def demo_scenario_entry(spec: ScenarioSpec) -> dict[str, Any]:
    from dataclasses import replace

    if spec.keep_legacy_entry:
        return {}
    # The legacy dict path (run_demo_scenario) shows the first planned search as a candidate:
    # never executable there, exactly like every other catalog candidate.
    first_spl = next((check.spl for check in spec.checks if check.spl), None)
    entry = C.demo_scenario(
        scenario_id=spec.scenario_id,
        label=spec.label,
        query=spec.question,
        demo_order=spec.demo_order,
        family=spec.family,
        summary=spec.plan_intro,
        candidate_spl=first_spl,
    )
    return {
        spec.scenario_id: replace(
            entry, aliases=tuple(spec.aliases), hidden_aliases=tuple(spec.legacy_phrasings), category=spec.category
        )
    }


def new_session_id() -> str:
    return f"ec-sess-{uuid4().hex[:10]}"
