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
    cc_mailbox: str = ""


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
    assignment_group: str = ""
    ticket_summary: str = ""


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
        if action.email is not None and action.email.cc_mailbox and action.email.cc_mailbox not in LOGICAL_TEAMS:
            raise ValueError(f"{spec.scenario_id}: {action.id} cc mailbox is not an allowlisted team")
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


# --- rendering context ------------------------------------------------------------------------

PRIORITIES = ("P1", "P2", "P3", "P4")
_REASON_MAX = 300
_SENT_MODES = {"live_allowlisted_email", "fake_test_transport"}


@dataclass
class _Ctx:
    """What text may say right now: which tickets exist, and the priority in force."""

    spec: ScenarioSpec
    executed: set[str]
    priority: dict[str, Any]


def _priority(spec: ScenarioSpec, state: dict[str, Any]) -> dict[str, Any]:
    policy = env.incident_priority(asset_tier=spec.asset_tier, evidence_state=spec.evidence_state)
    override = state.get("priority_override") if isinstance(state.get("priority_override"), dict) else {}
    chosen = str(override.get("priority") or policy["priority"])
    reason = str(override.get("reason") or "") if chosen != policy["priority"] else ""
    basis = f"analyst override of policy {policy['priority']}: {reason}" if reason else policy["rule"]
    return {
        "priority": chosen,
        "policy_priority": policy["priority"],
        "rule": policy["rule"],
        "policy_basis": policy["basis"],
        "basis": basis,
        "override_reason": reason or None,
    }


def _ctx(spec: ScenarioSpec, state: dict[str, Any], executed: set[str]) -> _Ctx:
    return _Ctx(spec=spec, executed=executed, priority=_priority(spec, state))


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


def _fill(text: str, ctx: _Ctx) -> str:
    """Resolve ``{incident}``, ``{ticket:<id>}``, ``{priority}`` and ``{priority_basis}``.

    A ticket number appears only once its ticket exists; the priority is the one in force.
    """
    spec = ctx.spec
    incident = _incident_id(spec, ctx.executed)
    text = text.replace("{incident}", incident or INCIDENT_PENDING_TEXT)
    text = text.replace("{priority_basis}", ctx.priority["basis"]).replace("{priority}", ctx.priority["priority"])
    by_id = {action.id: action for action in spec.actions}

    def ticket(match: re.Match[str]) -> str:
        action = by_id.get(match.group(1))
        if action is None or not action.ticket_id:
            raise ValueError(f"{spec.scenario_id}: unknown ticket token {match.group(0)}")
        return action.ticket_id if action.id in ctx.executed else TICKET_PENDING_TEXT

    return _TICKET_TOKEN.sub(ticket, text)


def _email_payload(ctx: _Ctx, action: Action, *, sent: bool) -> dict[str, Any]:
    assert action.email is not None
    to = action.email.to + (f" · cc {action.email.cc}" if action.email.cc else "")
    return {
        "to": to,
        "subject": _fill(action.email.subject, ctx),
        "body": _fill(action.email.body, ctx),
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


def _email_delivery(record: Any) -> dict[str, Any]:
    """What actually happened to an email, from the transport receipt — never assumed."""
    receipt = dict(getattr(record, "receipt", None) or {})
    mode = str(receipt.get("execution_mode") or "")
    sent = getattr(record, "state", None) in {"EXECUTED", "VERIFIED"} and mode in _SENT_MODES
    if sent and mode == "live_allowlisted_email":
        line = f"Delivered by SMTP to {receipt.get('to')}"
    elif sent:
        line = f"Accepted by the test mail transport for {receipt.get('to')}"
    elif receipt.get("reason") == "recipient_not_allowlisted":
        line = "Not sent — the recipient is not on the outbound email allowlist"
    else:
        line = "Not sent — outbound email is not configured"
    return {
        "sent": sent,
        "line": line,
        "to_address": receipt.get("to") if sent else None,
        "cc_addresses": list(receipt.get("cc") or []) if sent else [],
        "cc_not_copied": list(receipt.get("cc_skipped") or []),
        "message_id": receipt.get("provider_message_id") if sent else None,
    }


def _ticket_record(ctx: _Ctx, action: Action, *, opened_at: str, related: list[str]) -> dict[str, Any] | None:
    """The ticket as ITSM holds it after creation (or the update written to it)."""
    spec = ctx.spec
    group = action.assignment_group or _DEFAULT_GROUP.get(action.verb, "SOC Tier 2")
    if action.verb == "incident":
        description = "\n".join(
            [
                spec.conclusion_headline,
                "",
                *[f"- {point}" for point in spec.points],
                *(["", "Open questions:", *[f"- {item}" for item in spec.unresolved]] if spec.unresolved else []),
            ]
        )
        return {
            "number": action.ticket_id,
            "type": "Incident",
            "state": "New",
            "priority": f"{ctx.priority['priority']} ({ctx.priority['basis']})",
            "threat_assessment": spec.threat,
            "category": "Security incident",
            "configuration_item": spec.subject,
            "assignment_group": group,
            "short_description": _fill(action.ticket_summary or spec.conclusion_headline, ctx),
            "description": description,
            "opened": opened_at,
            "opened_by": "AI SOC Assistant, approved by the SOC analyst",
            "related": related,
        }
    if action.verb in {"request", "change"}:
        record = {
            "number": action.ticket_id,
            "type": "Change" if action.verb == "change" else "Request",
            "state": {"SCHEDULED": "Scheduled", "EXECUTED": "Approved"}.get(action.status_after, "Open"),
            "assignment_group": group,
            "short_description": _fill(action.ticket_summary or action.title, ctx),
            "description": _fill(action.proposal, ctx),
            "opened": opened_at,
            "opened_by": "AI SOC Assistant, approved by the SOC analyst",
            "parent": _incident_id(spec, ctx.executed),
        }
        if action.spl:
            record["attachment"] = validated_spl(spec, action.spl)
        return record
    if action.verb == "ticket_update":
        return {
            "number": _incident_id(spec, ctx.executed),
            "type": "Incident update",
            "state": "In progress",
            "work_note": _fill(action.executed, ctx),
            "updated": opened_at,
            "updated_by": "AI SOC Assistant, approved by the SOC analyst",
        }
    return None


_DEFAULT_GROUP = {"incident": "SOC Tier 2", "ticket_update": "SOC Tier 2"}


def _action_row(
    ctx: _Ctx,
    action: Action,
    *,
    selected: bool,
    record: Any | None,
    opened_at: str,
    related: list[str],
) -> dict[str, Any]:
    spec = ctx.spec
    state = getattr(record, "state", None)
    ran = state in {"EXECUTED", "VERIFIED", "AWAITING_EXTERNAL_RESPONSE"}
    failed = state == "FAILED"
    delivery = _email_delivery(record) if action.email is not None and record is not None else None
    if not selected and not ran:
        status, label = "SKIPPED", "Not selected"
    elif failed and delivery is not None:
        status, label = "NOT_SENT", "Not sent"
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
        details["email_draft"] = _email_payload(ctx, action, sent=bool(delivery and delivery["sent"]))
        if delivery is not None:
            details["email_delivery"] = delivery
    result = None
    if ran:
        result = _fill(action.executed, ctx)
        if state == "VERIFIED" and action.verified:
            result = f"{result} · {_fill(action.verified, ctx)}"
        ticket = _ticket_record(ctx, action, opened_at=opened_at, related=related)
        if ticket is not None:
            details["ticket"] = ticket
    elif failed:
        result = delivery["line"] if delivery is not None else str(
            (getattr(record, "receipt", None) or {}).get("summary") or "Action failed — nothing changed"
        )
    row: dict[str, Any] = {
        "id": action.id,
        "title": _fill(action.title, ctx),
        "summary": _fill(action.proposal, ctx),
        "tools": _tools(action.tool),
        "tool_ids": [action.tool],
        "selected": selected,
        "status": status,
        "status_label": label,
        "result": result,
        "provenance": "GOVERNED",
        "hil_required": True,
        "finding": {"headline_finding": result, "details": details},
    }
    if action.verb == "incident" and status == "PROPOSED" and spec.assessed:
        row["priority_control"] = {
            "policy_priority": ctx.priority["policy_priority"],
            "policy_rule": ctx.priority["rule"],
            "policy_basis": ctx.priority["policy_basis"],
            "options": list(PRIORITIES),
            "selected": ctx.priority["priority"],
            "reason": ctx.priority["override_reason"] or "",
        }
    return row


def _assessment(spec: ScenarioSpec, priority: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = env.incident_priority(asset_tier=spec.asset_tier, evidence_state=spec.evidence_state)
    chosen = priority or {"priority": policy["priority"], "override_reason": None}
    assessment: dict[str, Any] = {
        "incident_priority": chosen["priority"],
        "priority_rule": policy["rule"],
        "priority_basis": policy["basis"],
        "threat_assessment": spec.threat,
    }
    if chosen.get("override_reason"):
        assessment["priority_override"] = {
            "policy_priority": policy["priority"],
            "reason": chosen["override_reason"],
        }
    return assessment


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
    ctx = _ctx(spec, agent_state, executed)
    opened_at = str(agent_state.get("executed_at") or "")
    created = [action.ticket_id for action in spec.actions if action.ticket_id and action.id in executed]
    actions = [
        _action_row(
            ctx,
            action,
            selected=action.id in rem_selected,
            record=records.get(action.id),
            opened_at=opened_at,
            related=[ticket for ticket in created if ticket != action.ticket_id],
        )
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
            "error": agent_state.get("remediation_error"),
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
            # Findings carry the policy priority; an analyst override applies to the ticket.
            "assessment": _assessment(spec) if spec.assessed else None,
            "sources": list(spec.sources),
        }
        workflow["unconfirmed"] = list(spec.unresolved)
    if lifecycle == L.LIFECYCLE_INVESTIGATION_COMPLETE and not agent_state.get("remediation_declined"):
        workflow["remediation_offer"] = {
            "title": "Continue to the proposed response?",
            "body": _fill(spec.decision, ctx),
            "yes_label": "Show proposed response",
            "no_label": "Not now",
            "yes_follow_up_id": "create_remediation_plan",
            "no_follow_up_id": "decline_remediation_plan",
        }
    if remediation_visible:
        workflow["remediation_results"] = {"header": "Proposed response", "steps": actions}
    if lifecycle in {L.LIFECYCLE_COMPLETE, L.LIFECYCLE_PARTIAL}:
        workflow["final_summary"] = _final_summary(ctx, actions)
    return workflow


_DONE = {"EXECUTED", "VERIFIED", "REQUESTED", "SCHEDULED", "AWAITING_REPLY"}


def _final_summary(ctx: _Ctx, actions: list[dict[str, Any]]) -> dict[str, Any]:
    spec = ctx.spec
    done = [row for row in actions if row["status"] in _DONE]
    failed = [row for row in actions if row["status"] in {"FAILED", "NOT_SENT"}]
    skipped = [row for row in actions if row["status"] == "SKIPPED"]
    assessment = _assessment(spec, ctx.priority) if spec.assessed else None
    title = spec.final_state if not failed else f"PARTIALLY COMPLETE — {spec.final_state}"
    return {
        "title": title,
        "headline": _fill(spec.final_headline, ctx),
        "assessment": assessment,
        "actions": [
            {
                "title": row["title"],
                "status": row["status"],
                "status_label": row["status_label"],
                "result": row["result"],
                "ticket": (row["finding"] or {}).get("details", {}).get("ticket"),
                "email": (row["finding"] or {}).get("details", {}).get("email_draft"),
                "email_delivery": (row["finding"] or {}).get("details", {}).get("email_delivery"),
            }
            for row in done + failed
        ],
        "completed": [str(row["result"] or row["title"]) for row in done],
        "in_progress": list(spec.pending),
        "deferred": [*spec.not_proposed, *(f"Not run: {row['title']}" for row in skipped)],
        "risk_note": _fill(spec.next_triggers, ctx),
        "severity": assessment["incident_priority"] if assessment else "",
        "affected": spec.subject,
        "compromise": spec.threat.lower(),
    }


# --- lifecycle -------------------------------------------------------------------------------


def _execute_actions(spec: ScenarioSpec, state: dict[str, Any], session_id: str) -> None:
    """Run the approved actions in plan order: create → approve → execute → verify.

    Emails go through the allowlisted outbound transport. If it is not configured, the action
    fails and says so; nothing records a delivery that did not happen.
    """
    selected = set(state.get("remediation_selected") or [])
    action_ids = dict(state.get("action_ids") or {})
    executed: set[str] = set()
    for action in spec.actions:
        if action.id not in selected or action.id in action_ids:
            continue
        ctx = _ctx(spec, state, executed)
        extra: dict[str, Any] = {}
        if action.ticket_id:
            extra["ticket"] = {
                "id": action.ticket_id,
                "type": action.verb,
                "summary": _fill(action.title, ctx),
                **({"priority": ctx.priority["priority"]} if action.verb == "incident" else {}),
            }
        if action.email is not None:
            payload = _email_payload(ctx, action, sent=True)
            extra.update(
                {
                    "logical_recipient": action.email.mailbox,
                    "cc_logical": [action.email.cc_mailbox] if action.email.cc_mailbox else [],
                    "email": {"to": action.email.mailbox, "subject": payload["subject"], "body": payload["body"]},
                }
            )
        record = ec_actions.prepare_action(
            kind=_KIND_BY_ACTION[action.verb],
            label=_fill(action.title, ctx),
            session_id=session_id,
            scenario_id=spec.scenario_id,
            extra=extra,
        )
        record = ec_actions.approve_action(record.action_id)
        record = ec_actions.execute_action(record.action_id)
        if record.state == "EXECUTED" and action.verified:
            record = ec_actions.verify_action(record.action_id)
        action_ids[action.id] = record.action_id
        if record.state in {"EXECUTED", "VERIFIED"}:
            executed.add(action.id)
    state["action_ids"] = action_ids


def _apply_priority_override(spec: ScenarioSpec, state: dict[str, Any], override: Any) -> str | None:
    """Record an analyst's priority choice. A change from policy needs a reason; returns an error."""
    if not isinstance(override, dict) or _incident_action(spec) is None or not spec.assessed:
        return None
    chosen = str(override.get("priority") or "").strip().upper()
    if chosen not in PRIORITIES:
        return f"Priority must be one of {', '.join(PRIORITIES)}."
    reason = " ".join(str(override.get("reason") or "").split())[:_REASON_MAX]
    policy = env.incident_priority(asset_tier=spec.asset_tier, evidence_state=spec.evidence_state)["priority"]
    if chosen != policy and not reason:
        return f"Give a reason for changing the priority from {policy} to {chosen}."
    state["priority_override"] = {"priority": chosen, "reason": reason} if chosen != policy else None
    return None


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
        error = _apply_priority_override(spec, state, payload.get("priority_override"))
        state["remediation_error"] = error
        if error is None:
            selected = list(payload.get("selected_step_ids") or state.get("remediation_selected") or [])
            state["remediation_selected"] = [action.id for action in spec.actions if action.id in selected]
            state["executed_at"] = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC").lstrip("0")
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
        title = workflow["final_summary"]["headline"]
        assessment = title
    else:
        title = spec.conclusion_headline
        assessment = spec.conclusion_headline

    priority = _priority(spec, state)
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
