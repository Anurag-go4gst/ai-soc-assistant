"""R1 — a question answered by governed RAG, then acted on. Experience Center only.

Lifecycle is the same as every agent scenario:
plan (the retrieval pipeline, as steps) → approve → outcome (cited answer + "How RAG answered
this") → remediation plan (incident + escalation email) → approve → closure.

Nothing here calls retrieval, an LLM or an MCP live: the retrieval is a captured run of the
governed retriever (see ``rag_content``), replayed deterministically.
"""

from __future__ import annotations

from typing import Any

from app.demo import ec_actions, ec_email_drafts, ec_fsm_store
from app.demo.ec_agent import lifecycle as L
from app.demo.fixtures import common as C
from app.demo.fixtures.r1.rag_content import (
    ANSWER_HEADLINE,
    ANSWER_SENTENCES,
    CITATION_LABELS,
    KNOWLEDGE_GAPS,
    build_rag_trace,
    load_capture,
)

R1_SCENARIO_ID = "r1_rag_privileged_success_after_failure"
R1_FAMILY = "r1_governed_rag"
R1_INCIDENT_ID = "INC-2026-90217"
R1_ACCOUNT = "adm_ops02"
R1_HOST = "FIN-DB-02"
R1_SOURCE_IP = "10.30.7.21"

R1_QUERY = (
    "A privileged account logged in successfully after repeated failed logins. "
    "What does our SOP require, and what does our escalation matrix say?"
)

INVESTIGATION_STEP_DEFS: tuple[dict[str, Any], ...] = (
    {
        "id": "rewrite_query",
        "title": "Turn the question into a retrieval query",
        "summary": "Extract the concepts to search for: privileged account, success after failed logins, SOP requirement, escalation.",
        "follow_up_id": "rag_rewrite_query",
        "tools": ["SOC-KB (RAG)"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "select_collections",
        "title": "Choose which knowledge collections to search",
        "summary": "Limit the search to the collections that can answer this: SOC SOPs and the escalation matrix.",
        "follow_up_id": "rag_select_collections",
        "tools": ["SOC-KB (RAG)"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "policy_filter",
        "title": "Exclude anything not approved for use",
        "summary": "Drop draft, rejected, superseded and expired documents before ranking, so they can never shape the answer.",
        "follow_up_id": "rag_policy_filter",
        "tools": ["SOC-KB (RAG)"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "retrieve_rank",
        "title": "Retrieve and rank passages",
        "summary": "Score the remaining passages against the query and keep the best matches with their confidence.",
        "follow_up_id": "rag_retrieve_rank",
        "tools": ["SOC-KB (RAG)"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "grounding_check",
        "title": "Check every answer sentence has a source",
        "summary": "Each sentence must cite a retrieved passage; anything unsupported is reported as a gap, not answered.",
        "follow_up_id": "rag_grounding_check",
        "tools": ["SOC-KB (RAG)"],
        "default_selected": True,
        "phase": "investigation",
    },
    {
        "id": "compose_answer",
        "title": "Compose the cited answer",
        "summary": "Write the answer from the cited passages only, keeping the guardrails the SOP sets on wording.",
        "follow_up_id": "rag_compose_answer",
        "tools": ["SOC-KB (RAG)"],
        "default_selected": True,
        "phase": "investigation",
    },
)

REMEDIATION_STEP_DEFS: tuple[dict[str, Any], ...] = (
    {
        "id": "create_incident",
        "title": f"Create an incident for {R1_ACCOUNT}",
        "summary": f"Open {R1_INCIDENT_ID} with the SOP checklist and the cited passages attached.",
        "follow_up_id": "create_incident_ticket",
        "tools": ["ITSM"],
        "default_selected": True,
        "phase": "remediation",
    },
    {
        "id": "email_tier2",
        "title": "Escalate to the Tier 2 SOC analyst by email",
        "summary": "Send the escalation the matrix requires, with what to review first. You review the draft before it is sent.",
        "follow_up_id": "email_tier2_escalation",
        "tools": ["Email"],
        "hil_required": True,
        "default_selected": True,
        "phase": "remediation",
    },
)

R1_FOLLOWUPS = (
    C.chip("run_investigation", "Run investigation", action=True),
    C.chip("create_remediation_plan", "Continue to remediation plan", action=True),
    C.chip("run_remediation", "Approve remediation", action=True),
    C.chip("update_investigation_plan", "Update investigation plan"),
    C.chip("update_remediation_plan", "Update remediation plan"),
    *(C.chip(step["follow_up_id"], step["title"]) for step in INVESTIGATION_STEP_DEFS),
    C.chip("create_incident_ticket", "Create incident", action=True),
    C.chip("email_tier2_escalation", "Escalate to Tier 2 SOC analyst", action=True),
)
R1_FOLLOWUP_IDS = frozenset(item.follow_up_id for item in R1_FOLLOWUPS)

BRIEF = {
    "what_i_know": [
        f"Alert: {R1_ACCOUNT} (privileged) on {R1_HOST} — 14 failed logins, then a success from {R1_SOURCE_IP}",
        "The question is about policy: what our SOP requires and whom we escalate to",
        "Answers must come from approved SOC knowledge, with a source for every sentence",
    ],
    "objective": [
        "What does the SOP require before escalating?",
        "Who does the escalation matrix say we escalate to?",
        "What must we not claim yet?",
    ],
}


# ------------------------------------------------------------------------------ findings


def _investigation_finding(step_id: str, status: str) -> dict[str, Any]:
    capture = load_capture()
    entries = capture["retrieved_entries"]
    excluded = {reason: count for reason, count in capture["excluded_counts"].items() if count}
    complete = {
        "rewrite_query": "Query: privileged account · successful login after failures · SOP requirement · escalation matrix",
        "select_collections": "2 collections searched: SOC SOPs, Escalation matrix",
        "policy_filter": (
            f"{sum(v for k, v in excluded.items() if k != 'wrong_allowed_use')} non-approved versions excluded "
            f"({', '.join(k for k in excluded if k != 'wrong_allowed_use')}) · "
            f"{excluded.get('wrong_allowed_use', 0)} passage not approved for this use"
        ),
        "retrieve_rank": (
            f"{len(entries)} passages kept · top {CITATION_LABELS[entries[0]['entry_id']]} "
            f"(confidence {entries[0]['confidence']:.2f})"
        ),
        "grounding_check": (
            f"{len(ANSWER_SENTENCES)}/{len(ANSWER_SENTENCES)} answer sentences cited · "
            f"{len(KNOWLEDGE_GAPS)} gaps reported, not answered"
        ),
        "compose_answer": "Cited answer ready: review, escalate to Tier 2, do not claim compromise",
    }[step_id]
    queued = {
        "rewrite_query": "Queued — extract search concepts",
        "select_collections": "Queued — choose collections",
        "policy_filter": "Queued — exclude non-approved documents",
        "retrieve_rank": "Queued — retrieve and rank passages",
        "grounding_check": "Queued — check citations",
        "compose_answer": "Queued — compose cited answer",
    }[step_id]
    token = status.upper()
    headline = complete if token == "COMPLETE" else ("Running…" if token == "RUNNING" else queued)
    return {
        "headline_finding": headline,
        "headlines_by_status": {"QUEUED": queued, "RUNNING": "Running…", "COMPLETE": complete},
        "attention_state": "NORMAL",
        "evidence_sources": [{"source": "SOC-KB (RAG)", "provenance": "governed_retrieval", "tool": "retrieve_soc_kb"}],
    }


def _remediation_finding(step_id: str, status: str, executed: bool, email_envelope: dict[str, Any]) -> dict[str, Any]:
    token = status.upper()
    if step_id == "create_incident":
        queued = f"Queued — create {R1_INCIDENT_ID}"
        complete = f"Incident {R1_INCIDENT_ID} created · SOP checklist and citations attached"
        details: dict[str, Any] = {"ticket": {"id": R1_INCIDENT_ID, "severity": "P2", "account": R1_ACCOUNT, "host": R1_HOST}}
    else:
        queued = "Queued — email Tier 2 SOC analyst (you review the draft first)"
        complete = "Tier 2 SOC analyst notified · escalation per ESC-AUTH-001"
        email = email_envelope["email"]
        details = {
            "email_draft": {
                "to": email["to"],
                "cc": email.get("cc"),
                "subject": email["subject"],
                "body": email["body"],
                "status": "sent" if executed else "queued",
            },
            "email_extra": email_envelope,
        }
    headline = complete if (token not in {"QUEUED", "RUNNING"} and executed) else ("Running…" if token == "RUNNING" else queued)
    return {
        "headline_finding": headline,
        "headlines_by_status": {"QUEUED": queued, "RUNNING": "Running…", "COMPLETE": complete},
        "attention_state": "NORMAL",
        "details": details,
    }


# ------------------------------------------------------------------------------ agent state


def default_agent_state() -> dict[str, Any]:
    return {
        "lifecycle": L.LIFECYCLE_PLAN_READY,
        "investigation_selected": [step["id"] for step in INVESTIGATION_STEP_DEFS],
        "remediation_selected": [step["id"] for step in REMEDIATION_STEP_DEFS],
    }


def get_r1_agent_state(session_id: str | None, family: str) -> dict[str, Any]:
    return L.get_agent_state(session_id, family, default_state=default_agent_state())


def init_r1_agent_state(session_id: str, family: str, scenario_id: str) -> dict[str, Any]:
    return L.save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=default_agent_state())


def r1_followups_for_agent_mode(lifecycle: str, applied: list[str] | None = None) -> list[Any]:
    # The agent lane owns every action; no chips in agent mode.
    del lifecycle, applied
    return []


def finalize_r1_remediation_after_apply(
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
    L.auto_execute_pending_actions(session_id, scenario_id)
    stuck = [
        item
        for item in ec_actions.list_actions_for_session(session_id, scenario_id)
        if item.state == "APPROVAL_REQUIRED"
    ]
    state["remediation_execute_pending"] = False
    state["lifecycle"] = L.LIFECYCLE_PARTIAL if stuck else L.LIFECYCLE_COMPLETE
    if stuck:
        state["remediation_blocked"] = [item.label for item in stuck]
    L.save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=state)
    return state


def handle_r1_agent_follow_up(
    *,
    session_id: str,
    family: str,
    scenario_id: str,
    follow_up_id: str,
    agent_payload: dict[str, Any] | None,
    session_record: dict[str, Any],
) -> dict[str, Any] | None:
    if scenario_id != R1_SCENARIO_ID:
        return None
    agent_state = get_r1_agent_state(session_id, family)
    payload = agent_payload or {}

    def _current() -> dict[str, Any]:
        return ec_fsm_store.get_ec_session(session_id, family) or session_record

    if follow_up_id == "run_investigation":
        ec_fsm_store.apply_follow_up(session_id, family, scenario_id=scenario_id, follow_up_id=follow_up_id)
        selected = list(payload.get("selected_step_ids") or agent_state.get("investigation_selected") or [])
        agent_state["investigation_selected"] = selected
        L.apply_follow_ups(session_id, family, scenario_id, L.selected_follow_ups(INVESTIGATION_STEP_DEFS, selected))
        agent_state["lifecycle"] = L.LIFECYCLE_INVESTIGATION_COMPLETE
        L.save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=agent_state)
        return _current()

    if follow_up_id == "create_remediation_plan":
        ec_fsm_store.apply_follow_up(session_id, family, scenario_id=scenario_id, follow_up_id=follow_up_id)
        agent_state["lifecycle"] = L.LIFECYCLE_REMEDIATION_PLAN_READY
        L.save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=agent_state)
        return _current()

    if follow_up_id == "run_remediation":
        if agent_state.get("lifecycle") not in {L.LIFECYCLE_REMEDIATION_PLAN_READY, L.LIFECYCLE_REMEDIATING}:
            return _current()
        ec_fsm_store.apply_follow_up(session_id, family, scenario_id=scenario_id, follow_up_id=follow_up_id)
        selected = list(payload.get("selected_step_ids") or agent_state.get("remediation_selected") or [])
        agent_state["remediation_selected"] = selected
        L.apply_follow_ups(session_id, family, scenario_id, L.selected_follow_ups(REMEDIATION_STEP_DEFS, selected))
        agent_state["remediation_execute_pending"] = True
        agent_state["lifecycle"] = L.LIFECYCLE_REMEDIATING
        L.save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=agent_state)
        return _current()

    if follow_up_id in {"update_investigation_plan", "update_remediation_plan"}:
        key = "investigation_selected" if follow_up_id == "update_investigation_plan" else "remediation_selected"
        if payload.get("selected_step_ids"):
            agent_state[key] = list(payload["selected_step_ids"])
        L.save_agent_state(session_id, family, scenario_id=scenario_id, agent_state=agent_state)
        return _current()

    return None


# ------------------------------------------------------------------------------ workflow


def _step_status(step: dict[str, Any], *, lifecycle: str, applied: list[str], phase: str) -> str:
    if lifecycle == L.LIFECYCLE_PLAN_READY:
        return "QUEUED"
    if phase == "remediation" and lifecycle == L.LIFECYCLE_REMEDIATION_PLAN_READY:
        return "QUEUED"
    return "COMPLETE" if step.get("follow_up_id") in applied else "SKIPPED"


def _email_envelope() -> dict[str, Any]:
    return ec_email_drafts.r1_tier2_escalation_email(
        incident_id=R1_INCIDENT_ID,
        account=R1_ACCOUNT,
        host=R1_HOST,
        source_ip=R1_SOURCE_IP,
    )


def build_r1_agent_workflow(*, agent_state: dict[str, Any], applied: list[str]) -> dict[str, Any]:
    lifecycle = str(agent_state.get("lifecycle") or L.LIFECYCLE_PLAN_READY)
    phase = L.workflow_phase(lifecycle)
    inv_selected = list(agent_state.get("investigation_selected") or [])
    rem_selected = list(agent_state.get("remediation_selected") or [])
    investigation_done = lifecycle not in {L.LIFECYCLE_PLAN_READY, L.LIFECYCLE_INVESTIGATING}
    email_envelope = _email_envelope()

    investigation_steps = []
    for step in INVESTIGATION_STEP_DEFS:
        status = _step_status(step, lifecycle=lifecycle, applied=applied, phase="investigation")
        finding = _investigation_finding(step["id"], status)
        investigation_steps.append(
            {**step, "selected": step["id"] in inv_selected, "status": status, "finding": finding, "result": finding["headline_finding"]}
        )

    remediation_steps = []
    for step in REMEDIATION_STEP_DEFS:
        status = _step_status(step, lifecycle=lifecycle, applied=applied, phase="remediation")
        executed = step["follow_up_id"] in applied and lifecycle in {L.LIFECYCLE_COMPLETE, L.LIFECYCLE_PARTIAL}
        finding = _remediation_finding(step["id"], status, executed, email_envelope)
        remediation_steps.append(
            {**step, "selected": step["id"] in rem_selected, "status": status, "finding": finding, "result": finding["headline_finding"]}
        )

    rem_visible = lifecycle in {
        L.LIFECYCLE_REMEDIATION_PLAN_READY,
        L.LIFECYCLE_REMEDIATING,
        L.LIFECYCLE_VERIFYING,
        L.LIFECYCLE_COMPLETE,
        L.LIFECYCLE_PARTIAL,
    }
    workflow: dict[str, Any] = {
        "lifecycle": lifecycle,
        "phase": phase,
        "opening_narrative": "",
        "brief": BRIEF,
        "investigation_plan": {
            "editable": lifecycle == L.LIFECYCLE_PLAN_READY,
            "summary": "Six governed retrieval steps: search only approved SOC knowledge, rank it, and cite every sentence.",
            "primary_cta": "Run investigation",
            "secondary_cta": "Edit plan",
            "steps": investigation_steps,
        },
        "remediation_plan": {
            "editable": lifecycle == L.LIFECYCLE_REMEDIATION_PLAN_READY,
            "summary": "Two actions the SOP and escalation matrix call for — batch-executed after one approval.",
            "primary_cta": "Approve remediation",
            "secondary_cta": "Modify plan",
            "steps": remediation_steps,
            "visible": rem_visible,
        },
        "remediation_offer": None,
        "unconfirmed": [],
        "missing_evidence": [],
        "executive_summary": [],
        "hil_prompt": None,
        "investigation_conclusion": None,
        "investigation_summary": None,
        "final_summary": None,
    }

    if investigation_done:
        capture = load_capture()
        workflow["rag_trace"] = build_rag_trace()
        workflow["investigation_summary"] = {
            "title": "Answer ready",
            "steps_completed": sum(1 for step in investigation_steps if step["status"] == "COMPLETE"),
            "steps_total": len(investigation_steps),
            "metrics": [
                {"label": "Passages used", "value": sum(1 for p in workflow["rag_trace"]["passages"] if p["used"])},
                {"label": "Excluded (not approved)", "value": workflow["rag_trace"]["excluded_total"]},
                {"label": "Top confidence", "value": f"{capture['confidence']:.2f}"},
                {"label": "Sentences cited", "value": f"{len(ANSWER_SENTENCES)}/{len(ANSWER_SENTENCES)}"},
            ],
        }
        workflow["investigation_conclusion"] = {
            "headline": ANSWER_HEADLINE,
            "narrative_points": [
                f"{text} [{', '.join(CITATION_LABELS[c] for c in cites)}]" for text, cites in ANSWER_SENTENCES
            ],
        }
        workflow["unconfirmed"] = [f"Not in our knowledge base: {gap}" for gap in KNOWLEDGE_GAPS]
        workflow["investigation_results"] = {"header": "Retrieval steps", "steps": investigation_steps}

    if lifecycle == L.LIFECYCLE_INVESTIGATION_COMPLETE:
        workflow["next_step_cta"] = {"label": "Continue to remediation plan", "follow_up_id": "create_remediation_plan"}

    if rem_visible:
        workflow["remediation_results"] = {"header": "Remediation plan", "steps": remediation_steps}
        workflow["remediation_summary"] = {
            "title": "Remediation plan ready",
            "steps_completed": 0,
            "steps_total": len(rem_selected),
            "plan_steps": f"{len(rem_selected)}/{len(remediation_steps)} selected",
            "metrics": [{"label": "Incident", "value": R1_INCIDENT_ID}, {"label": "Escalation", "value": "Tier 2 SOC analyst"}],
        }
        workflow["remediation_conclusion"] = {
            "title": "Remediation approach",
            "headline": "Do exactly what the SOP and escalation matrix require — no account action without a human decision.",
            "narrative_points": [
                f"Open {R1_INCIDENT_ID} for {R1_ACCOUNT} on {R1_HOST} with the SOP checklist and the cited passages.",
                "Escalate to the Tier 2 SOC analyst, as ESC-AUTH-001 requires for privileged accounts; you review the email before it is sent.",
            ],
        }

    if lifecycle == L.LIFECYCLE_COMPLETE:
        workflow["final_summary"] = {
            "title": "Escalation completed",
            "headline": f"{R1_INCIDENT_ID} open · Tier 2 SOC analyst notified · compromise not claimed",
            "severity": "P2",
            "affected": f"{R1_ACCOUNT} on {R1_HOST}",
            "compromise": "not confirmed",
            "completed": [
                f"Incident {R1_INCIDENT_ID} created with SOP checklist and citations",
                "Tier 2 SOC analyst notified per ESC-AUTH-001",
            ],
            "in_progress": ["Tier 2 review of the account, the source and the session"],
            "risk_from": "MEDIUM",
            "risk_to": "MEDIUM",
            "risk_note": "Risk is unchanged until Tier 2 reviews the session; escalation puts the right person on it now.",
        }
    return workflow


# ------------------------------------------------------------------------------ turn


def _apply(applied: list[str], session_id: str) -> None:
    if "create_incident_ticket" in applied:
        C.ensure_executed_action(
            kind="ticket_create",
            label=f"Create incident {R1_INCIDENT_ID}",
            session_id=session_id,
            scenario_id=R1_SCENARIO_ID,
            extra={"ticket": {"id": R1_INCIDENT_ID, "severity": "P2", "account": R1_ACCOUNT, "host": R1_HOST}},
        )
    if "email_tier2_escalation" in applied:
        C.ensure_hil_action(
            kind="email_send",
            label="Escalate to Tier 2 SOC analyst",
            session_id=session_id,
            scenario_id=R1_SCENARIO_ID,
            extra=_email_envelope(),
        )


def build_r1_turn(
    *,
    session_id: str,
    turn: int,
    applied_follow_up_ids: list[str],
    pending_action_id: str | None = None,
    awaiting_external: bool = False,
    agent_state: dict[str, Any] | None = None,
):
    applied = list(applied_follow_up_ids)
    _apply(applied, session_id)
    state = dict(agent_state or get_r1_agent_state(session_id, R1_FAMILY))
    if state.get("remediation_execute_pending"):
        state = finalize_r1_remediation_after_apply(
            session_id=session_id,
            family=R1_FAMILY,
            scenario_id=R1_SCENARIO_ID,
            agent_state=state,
            applied=applied,
        )
    lifecycle = str(state.get("lifecycle") or L.LIFECYCLE_PLAN_READY)
    workflow = build_r1_agent_workflow(agent_state=state, applied=applied)
    from app.demo.ec_journeys import journey_for

    outcome = {
        "disposition": "policy_answer",
        "confirmed": [text for text, _ in ANSWER_SENTENCES[:4]],
        "supported": [],
        "unconfirmed": [f"Not in our knowledge base: {gap}" for gap in KNOWLEDGE_GAPS],
        "missing_evidence": [],
        "production_investigation_outcome_unused": True,
    }
    source = [
        C.evidence(
            f"ev-r1-{CITATION_LABELS[entry['entry_id']].lower()}",
            "rag",
            entry["citation"],
            [{"excerpt": entry["source_excerpt"], "confidence": entry["confidence"], "approval": entry["approval_status"]}],
            provenance="governed_retrieval_capture",
            tool_name="retrieve_soc_kb",
        )
        for entry in load_capture()["retrieved_entries"]
    ]
    return C.envelope(
        scenario_id=R1_SCENARIO_ID,
        family=R1_FAMILY,
        session_id=session_id,
        turn=turn,
        applied=applied,
        chips=r1_followups_for_agent_mode(lifecycle, applied),
        title="Privileged login after failures — what the SOP requires",
        direct_line="",
        assessment=ANSWER_HEADLINE,
        found=ANSWER_HEADLINE,
        outcome=outcome,
        evidence_state=[C.state_item("soc_kb", "SOC knowledge base", "OBTAINED", "Approved SOP and escalation passages")],
        source_evidence=source,
        actions=C.actions_for(session_id, R1_SCENARIO_ID),
        resources=["SOC-KB (RAG)", "ITSM", "Email"],
        controls=["Approved knowledge only", "Every sentence cited", "No account action without a human decision"],
        pending_action_id=pending_action_id,
        awaiting_external=awaiting_external,
        extra={
            "selected_skill": "knowledge_recall",
            "ec_agent_workflow": workflow,
            "ec_agent_lifecycle": lifecycle,
            "ec_workflow_state": lifecycle,
            "ec_provenance": {
                "envelope": "experience_center_response",
                "route_source": "ec_fixture_selected",
                "live_llm_called": False,
                "live_mcp_called": False,
                "live_rag_called": False,
                "rag_source": "captured_governed_retrieval",
            },
        },
        journey=journey_for(R1_SCENARIO_ID, applied),
        severity="P2 High",
    )


def r1_analyst_override(scenario_id: str, base: dict[str, Any]) -> dict[str, Any] | None:
    if scenario_id != R1_SCENARIO_ID:
        return None
    env = build_r1_turn(session_id="r1-override", turn=0, applied_follow_up_ids=[])
    return {**base, **(env.analyst or {})}


def build_r1_demo_scenarios() -> dict[str, Any]:
    return {
        R1_SCENARIO_ID: C.demo_scenario(
            scenario_id=R1_SCENARIO_ID,
            label="R1 · Governed knowledge answer (RAG)",
            query=R1_QUERY,
            demo_order=8,
            family=R1_FAMILY,
            summary="Policy question answered from approved SOC knowledge with a citation for every sentence.",
            expected_skill="knowledge_recall",
        )
    }
