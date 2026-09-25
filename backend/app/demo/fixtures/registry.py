"""Experience Center scenario packs (S1–S7, R1, Q1, Q2). Isolated from production /chat."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any

from app.demo.ec_response import EcFollowUpChip, ExperienceCenterResponse
from app.demo.ec_agent import spec_engine
from app.demo.ec_agent.cio_content import enrich_agent_workflow
from app.demo.ec_agent.registry import has_agent_profile
from app.demo.fixtures.specs import ALL_SPECS

S1_SCENARIO_ID = "s1_governed_splunk_investigation"
S2_SCENARIO_ID = "s2_ai_prompt_injection"
S3_SCENARIO_ID = "s3_firewall_team_coordination"
S4_SCENARIO_ID = "s4_zero_day_no_playbook"
S5_SCENARIO_ID = "s5_cisco_hardening_remediation"
S6_SCENARIO_ID = "s6_investigation_continuity"
S7_SCENARIO_ID = "s7_conflicting_ot_evidence"
R1_SCENARIO_ID = "r1_rag_privileged_success_after_failure"

FLAGSHIP_SCENARIO_IDS = (
    S1_SCENARIO_ID,
    S2_SCENARIO_ID,
    S3_SCENARIO_ID,
    S4_SCENARIO_ID,
    S5_SCENARIO_ID,
    S6_SCENARIO_ID,
    S7_SCENARIO_ID,
    R1_SCENARIO_ID,
)


class _Pack:
    def __init__(
        self,
        *,
        followup_ids: frozenset[str],
        followups: Callable[[], list[EcFollowUpChip]],
        build_turn: Callable[..., ExperienceCenterResponse],
        analyst_override: Callable[[str, dict[str, Any]], dict[str, Any] | None],
        demo_scenarios: Callable[[], dict[str, Any]],
        resolve: Callable[[str], str] | None = None,
    ) -> None:
        self.followup_ids = followup_ids
        self.followups = followups
        self.build_turn = build_turn
        self.analyst_override = analyst_override
        self.demo_scenarios = demo_scenarios
        self.resolve = resolve or (lambda follow_up_id: follow_up_id)


def _spec_analyst_override(spec: spec_engine.ScenarioSpec, scenario_id: str, base: dict[str, Any]) -> dict[str, Any] | None:
    """Plan-turn analyst card for callers of the legacy ``run_demo_scenario`` dict path."""
    if scenario_id != spec.scenario_id:
        return None
    response = spec_engine.build_turn(spec, session_id="ec-override", turn=0, applied_follow_up_ids=[])
    return {**base, **(response.analyst or {})}


def _spec_pack(spec: spec_engine.ScenarioSpec) -> _Pack:
    return _Pack(
        followup_ids=spec_engine.FOLLOW_UP_IDS,
        followups=spec_engine.followup_chips,
        build_turn=partial(spec_engine.build_turn, spec),
        analyst_override=partial(_spec_analyst_override, spec),
        demo_scenarios=partial(spec_engine.demo_scenario_entry, spec),
    )


# Every Experience Center scenario (S1–S7, R1, Q1, Q2) runs on the shared spec engine.
PACKS: dict[str, _Pack] = {spec.scenario_id: _spec_pack(spec) for spec in ALL_SPECS}


def resolve_follow_up(scenario_id: str, follow_up_id: str) -> str:
    pack = PACKS.get(scenario_id)
    if pack is None:
        return follow_up_id
    return pack.resolve(follow_up_id)


def followups_for_flagship(scenario_id: str) -> list[EcFollowUpChip] | None:
    pack = PACKS.get(scenario_id)
    if pack is None:
        return None
    return pack.followups()


def known_flagship_follow_up_ids(scenario_id: str) -> set[str] | None:
    pack = PACKS.get(scenario_id)
    if pack is None:
        return None
    return set(pack.followup_ids)


def build_flagship_turn(
    scenario_id: str,
    *,
    session_id: str,
    turn: int,
    applied_follow_up_ids: list[str],
    pending_action_id: str | None = None,
    awaiting_external: bool = False,
    agent_state: dict[str, Any] | None = None,
) -> ExperienceCenterResponse | None:
    pack = PACKS.get(scenario_id)
    if pack is None:
        return None
    kwargs: dict[str, Any] = {
        "session_id": session_id,
        "turn": turn,
        "applied_follow_up_ids": applied_follow_up_ids,
        "pending_action_id": pending_action_id,
        "awaiting_external": awaiting_external,
    }
    if not has_agent_profile(scenario_id):
        return pack.build_turn(**kwargs)
    kwargs["agent_state"] = agent_state
    response = pack.build_turn(**kwargs)
    return _with_cio_layer(scenario_id, response)


def _with_cio_layer(scenario_id: str, response: ExperienceCenterResponse) -> ExperienceCenterResponse:
    """Apply the shared CIO content layer (step reasons, executive brief, tool fabric)."""
    workflow = (response.model_extra or {}).get("ec_agent_workflow")
    if not isinstance(workflow, dict):
        return response
    payload = response.model_dump()
    payload["ec_agent_workflow"] = enrich_agent_workflow(scenario_id, payload["ec_agent_workflow"])
    lifecycle = payload["ec_agent_workflow"].get("lifecycle")
    if lifecycle == "PLAN_READY":
        _present_plan_only(scenario_id, payload)
    elif lifecycle in {"INVESTIGATION_COMPLETE", "COMPLETE", "PARTIAL"}:
        _mirror_plan_in_animation(scenario_id, payload, lifecycle)
    return ExperienceCenterResponse.model_validate(payload)


def _mirror_plan_in_animation(scenario_id: str, payload: dict[str, Any], lifecycle: str) -> None:
    """The run/approve animation walks the steps the user approved, not an internal follow-up."""
    from app.demo.ec_journeys import agent_steps_journey

    workflow = payload["ec_agent_workflow"]
    investigation = lifecycle == "INVESTIGATION_COMPLETE"
    container = workflow.get("investigation_results" if investigation else "remediation_results") or workflow.get(
        "remediation_plan"
    ) or {}
    steps = [
        (str(step.get("title") or ""), str((step.get("finding") or {}).get("headline_finding") or step.get("result") or ""))
        for step in container.get("steps") or []
        if step.get("selected", True) and str(step.get("status") or "").upper() not in {"SKIPPED", "QUEUED"}
    ]
    if not steps:
        return
    payload["ec_execution_journey"] = agent_steps_journey(
        scenario_id,
        "run_investigation" if investigation else "run_remediation",
        steps=steps,
        header="Running the investigation" if investigation else "Carrying out the approved actions",
    ).model_dump()


def _present_plan_only(scenario_id: str, payload: dict[str, Any]) -> None:
    """At PLAN_READY nothing has run: no verdict in the title, no results in the animation."""
    from app.demo.ec_agent.cio_content import cio_content_for
    from app.demo.ec_journeys import agent_planning_journey

    workflow = payload["ec_agent_workflow"]
    steps = [step for step in (workflow.get("investigation_plan") or {}).get("steps") or [] if step.get("selected", True)]
    used_tools = [tool["name"] for tool in workflow.get("tool_fabric") or [] if tool.get("used")]
    content = cio_content_for(scenario_id)
    if content is not None and content.plan_title:
        for key in ("analyst", "analyst_response"):
            if isinstance(payload.get(key), dict):
                payload[key] = {**payload[key], "finding_title": content.plan_title}
    payload["ec_status_summary"] = f"Plan ready · {len(steps)} checks proposed · nothing has run yet"
    journey = payload.get("ec_execution_journey")
    if isinstance(journey, dict) and journey.get("kind") == "initial":
        payload["ec_execution_journey"] = agent_planning_journey(
            scenario_id, tool_names=used_tools, step_count=len(steps)
        ).model_dump()


def analyst_override_for(scenario_id: str, base: dict[str, Any]) -> dict[str, Any] | None:
    pack = PACKS.get(scenario_id)
    if pack is None:
        return None
    return pack.analyst_override(scenario_id, base)


def all_flagship_demo_scenarios() -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for pack in PACKS.values():
        merged.update(pack.demo_scenarios())
    return merged


