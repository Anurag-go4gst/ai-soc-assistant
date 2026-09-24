"""EC-only turn runner. Production /chat continues to use run_demo_scenario() dicts."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.demo import ec_actions, ec_fsm_store
from app.demo.ec_response import (
    EcFollowUpChip,
    EcProjection,
    EcProjectionView,
    EcProvenanceStamp,
    EcSessionState,
    ExperienceCenterResponse,
)
from app.demo.scenarios import SCENARIOS, run_demo_scenario
from app.demo.fixtures.registry import (
    build_flagship_turn,
    followups_for_flagship,
    known_flagship_follow_up_ids,
    resolve_follow_up,
)

_DEFAULT_FOLLOWUPS: dict[str, tuple[EcFollowUpChip, ...]] = {
    "firewall_deny_coordinated_attack": (
        EcFollowUpChip(follow_up_id="check_identity", label="Check identity for svc_jump_ops"),
        EcFollowUpChip(follow_up_id="extend_blast_radius", label="Extend blast-radius search"),
        EcFollowUpChip(follow_up_id="open_p1_ticket", label="Open P1 incident ticket"),
    ),
    "firewall_baseline_template_spl": (
        EcFollowUpChip(follow_up_id="review_baseline_window", label="Review 7-day baseline window"),
    ),
    "failed_login_spike_app01": (
        EcFollowUpChip(follow_up_id="success_after_failure", label="Run success-after-failure correlation"),
        EcFollowUpChip(follow_up_id="check_privileged_accounts", label="Check privileged account impact"),
    ),
}


# Legacy (non-agent) scenarios: an interactive action is only minted once the chip that asks
# for it is applied — a ticket must not exist before anyone requested it.
_SEED_ONLY_AFTER_FOLLOW_UP: dict[str, dict[str, str]] = {
    "firewall_deny_coordinated_attack": {"open_p1_incident_ticket": "open_p1_ticket"},
}

# What each legacy follow-up chip adds to the answer, so the answer evolves with the conversation
# instead of repeating the same summary on every turn.
_FOLLOW_UP_FINDINGS: dict[str, dict[str, str]] = {
    "firewall_deny_coordinated_attack": {
        "check_identity": (
            "Identity check: 3 svc_jump_ops logons on 10.20.1.10 between 03:12 and 03:19 came from "
            "198.51.100.42 — credential use from the attacker's IP is now confirmed (T1078 supported)."
        ),
        "extend_blast_radius": (
            "Blast radius: no connections from 10.20.1.10 to other internal hosts after 03:19 — no "
            "lateral movement seen in the last 24 hours."
        ),
        "open_p1_ticket": (
            "Escalation of INC-2026-89412 (opened as P2 when the 14-day watch was raised) to P1 is "
            "prepared for the on-duty SOC lead — approve the ticket update below."
        ),
    },
}


def _legacy_follow_up_view(
    scenario_id: str,
    payload: dict[str, Any],
    applied: list[str],
) -> dict[str, Any]:
    """Append the findings of applied chips to the analyst card (copy, not in place)."""
    findings = [
        text for follow_up_id, text in _FOLLOW_UP_FINDINGS.get(scenario_id, {}).items() if follow_up_id in applied
    ]
    if not findings:
        return payload
    updated = dict(payload)
    for key in ("analyst_response", "analyst"):
        card = updated.get(key)
        if isinstance(card, dict):
            card = dict(card)
            card["initial_assessment"] = [*(card.get("initial_assessment") or []), *findings]
            if "check_identity" in applied and card.get("mitre_mappings"):
                card["mitre_mappings"] = [
                    {**row, "Status": "Supported", "Evidence": "svc_jump_ops logons attributed to 198.51.100.42"}
                    if row.get("Technique") == "T1078"
                    else row
                    for row in card["mitre_mappings"]
                ]
            updated[key] = card
    return updated


class UnknownFollowUpError(KeyError):
    """follow_up_id is not registered for this scenario — do not invent a scenario."""


def _family_for(scenario_id: str) -> str:
    scenario = SCENARIOS[scenario_id]
    return str(scenario.fsm_family or scenario.scenario_id)


def followups_for(scenario_id: str) -> list[EcFollowUpChip]:
    flagship = followups_for_flagship(scenario_id)
    if flagship is not None:
        return flagship
    return list(_DEFAULT_FOLLOWUPS.get(scenario_id, ()))


def known_follow_up_ids(scenario_id: str) -> set[str]:
    flagship = known_flagship_follow_up_ids(scenario_id)
    if flagship is not None:
        return flagship
    return {chip.follow_up_id for chip in followups_for(scenario_id)}


def _build_projection(scenario_id: str, payload: dict[str, Any]) -> EcProjection:
    fixture = EcProvenanceStamp(kind="experience_center_fixture", detail=scenario_id)
    skill = str(payload.get("selected_skill") or "")
    evidence_ids = [
        str(item.get("evidence_id"))
        for item in (payload.get("source_evidence") or [])
        if isinstance(item, dict) and item.get("evidence_id")
    ]
    approved = bool((payload.get("spl_validation") or {}).get("approved")) if payload.get("spl_validation") else False
    return EcProjection(
        understanding=EcProjectionView(
            title="Understanding",
            summary="Fixture-selected investigation family for this Experience Center scenario.",
            items=[f"route_source=ec_fixture_selected", f"family={skill}"],
            provenance=EcProvenanceStamp(kind="ec_fixture_selected", detail=skill or None),
        ),
        resource_plan=EcProjectionView(
            title="Resources",
            summary="Governed fixture resources only. No ResourcePlan graph execution.",
            items=list(payload.get("tool_plan") or []) or ["fixture_resources"],
            provenance=fixture,
        ),
        phase_contract=EcProjectionView(
            title="Controls",
            summary="Experience Center projects phase-shaped controls; production PhaseContract is unused.",
            items=["HIL remains in force", "candidate SPL is not executed", "no production Phase 10"],
            provenance=EcProvenanceStamp(kind="ec_scenario_policy", detail="ec_control_projection"),
        ),
        evidence_state=EcProjectionView(
            title="Evidence",
            summary="Fixture evidence packaged for the visitor answer.",
            items=evidence_ids or ["no_source_evidence_ids"],
            provenance=EcProvenanceStamp(
                kind="production_validator_read_only" if approved else "experience_center_fixture",
                detail="validate_spl" if payload.get("spl_validation") else "fixture_evidence",
            ),
        ),
        investigation_outcome=EcProjectionView(
            title="Outcome",
            summary=str(payload.get("analyst_summary") or payload.get("message") or "Fixture outcome"),
            items=["production InvestigationOutcome field unused"],
            provenance=fixture,
        ),
        provenance=fixture,
    )


def run_experience_center_turn(
    scenario_id: str,
    *,
    session_id: str | None = None,
    follow_up_id: str | None = None,
    agent_payload: dict[str, Any] | None = None,
) -> ExperienceCenterResponse:
    if scenario_id not in SCENARIOS:
        raise KeyError(scenario_id)
    if follow_up_id:
        follow_up_id = resolve_follow_up(scenario_id, follow_up_id)
    if follow_up_id and follow_up_id not in known_follow_up_ids(scenario_id):
        raise UnknownFollowUpError(follow_up_id)

    family = _family_for(scenario_id)
    active_session = session_id or f"ec-sess-{uuid4().hex[:10]}"

    if follow_up_id:
        from app.demo.ec_agent.dispatch import handle_agent_follow_up

        handled = handle_agent_follow_up(
            session_id=active_session,
            family=family,
            scenario_id=scenario_id,
            follow_up_id=follow_up_id,
            agent_payload=agent_payload,
            session_record=ec_fsm_store.get_ec_session(active_session, family) or {},
        )
        if handled is not None:
            session_record = handled
        else:
            session_record = ec_fsm_store.apply_follow_up(
                active_session,
                family,
                scenario_id=scenario_id,
                follow_up_id=follow_up_id,
            )
    else:
        existing = ec_fsm_store.get_ec_session(active_session, family)
        session_record = existing or ec_fsm_store.upsert_ec_session(
            active_session,
            family,
            scenario_id=scenario_id,
            turn=0,
        )

    from app.demo.ec_agent.dispatch import maybe_init_agent_session

    session_record = maybe_init_agent_session(
        scenario_id=scenario_id,
        session_id=active_session,
        family=family,
        session_record=session_record,
        follow_up_id=follow_up_id,
    )

    flagship = build_flagship_turn(
        scenario_id,
        session_id=active_session,
        turn=int(session_record.get("turn") or 0),
        applied_follow_up_ids=list(session_record.get("applied_follow_up_ids") or []),
        pending_action_id=session_record.get("pending_action_id"),
        awaiting_external=bool(session_record.get("awaiting_external")),
        agent_state=session_record.get("agent_state"),
    )
    if flagship is not None:
        return _with_story_thread(scenario_id, flagship)

    applied_ids = list(session_record.get("applied_follow_up_ids") or [])
    payload = _legacy_follow_up_view(scenario_id, run_demo_scenario(scenario_id), applied_ids)

    analyst = payload.get("analyst_response") if isinstance(payload.get("analyst_response"), dict) else None
    gated = _SEED_ONLY_AFTER_FOLLOW_UP.get(scenario_id, {})
    interactive = [
        item
        for item in (analyst or {}).get("interactive_actions") or []
        if not (isinstance(item, dict) and item.get("id") in gated and gated[item["id"]] not in applied_ids)
    ]
    actions = ec_actions.list_actions_for_session(active_session, scenario_id)
    if not actions and interactive:
        actions = ec_actions.seed_from_interactive_actions(
            interactive_actions=interactive,
            session_id=active_session,
            scenario_id=scenario_id,
        )

    provenance = dict(payload.get("ec_provenance") or {})
    provenance.update(
        {
            "envelope": "experience_center_response",
            "route_source": "ec_fixture_selected",
            "live_llm_called": False,
            "live_mcp_called": False,
        }
    )

    envelope = {
        **payload,
        "scenario_id": scenario_id,
        "analyst": analyst,
        "route_source": "ec_fixture_selected",
        "ec_projection": _build_projection(scenario_id, payload).model_dump(),
        "ec_actions": [item.model_dump() for item in actions],
        "ec_followups": [
            item.model_dump() for item in followups_for(scenario_id) if item.follow_up_id not in applied_ids
        ],
        "ec_session_state": EcSessionState(
            session_id=active_session,
            family=family,
            scenario_id=scenario_id,
            turn=int(session_record.get("turn") or 0),
            pending_action_id=session_record.get("pending_action_id"),
            awaiting_external=bool(session_record.get("awaiting_external")),
            applied_follow_up_ids=list(session_record.get("applied_follow_up_ids") or []),
        ).model_dump(),
        "ec_provenance": provenance,
    }
    return _with_story_thread(scenario_id, ExperienceCenterResponse.model_validate(envelope))


def _with_story_thread(scenario_id: str, response: ExperienceCenterResponse) -> ExperienceCenterResponse:
    from app.demo.ec_story import story_thread_for

    thread = story_thread_for(scenario_id)
    if thread is None:
        return response
    return ExperienceCenterResponse.model_validate({**response.model_dump(), "ec_story_thread": thread})
