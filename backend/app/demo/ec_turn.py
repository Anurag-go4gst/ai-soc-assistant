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


class UnknownFollowUpError(KeyError):
    """follow_up_id is not registered for this scenario — do not invent a scenario."""


def _family_for(scenario_id: str) -> str:
    scenario = SCENARIOS[scenario_id]
    return str(scenario.fsm_family or scenario.scenario_id)


def followups_for(scenario_id: str) -> list[EcFollowUpChip]:
    return list(_DEFAULT_FOLLOWUPS.get(scenario_id, ()))


def known_follow_up_ids(scenario_id: str) -> set[str]:
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
) -> ExperienceCenterResponse:
    if scenario_id not in SCENARIOS:
        raise KeyError(scenario_id)
    if follow_up_id and follow_up_id not in known_follow_up_ids(scenario_id):
        raise UnknownFollowUpError(follow_up_id)

    payload = run_demo_scenario(scenario_id)
    family = _family_for(scenario_id)
    active_session = session_id or f"ec-sess-{uuid4().hex[:10]}"

    if follow_up_id:
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

    analyst = payload.get("analyst_response") if isinstance(payload.get("analyst_response"), dict) else None
    interactive = list((analyst or {}).get("interactive_actions") or [])
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
        "ec_followups": [item.model_dump() for item in followups_for(scenario_id)],
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
    return ExperienceCenterResponse.model_validate(envelope)
