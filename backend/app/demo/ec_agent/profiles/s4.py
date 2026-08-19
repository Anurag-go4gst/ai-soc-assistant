"""S4 zero-day — reference agent workflow profile."""

from __future__ import annotations

from app.demo.ec_agent.registry import register_agent_profile
from app.demo.ec_agent.types import AgentProfile
from app.demo.ec_agent_lifecycle import (
    S4_AGENT_CONVERSATIONAL_FOLLOWUPS,
    S4_SCENARIO_ID,
    _default_agent_state,
    build_s4_agent_workflow,
    finalize_s4_remediation_after_apply,
    handle_s4_agent_follow_up,
    init_s4_agent_state,
    s4_followups_for_agent_mode,
)
from app.demo.fixtures.s4.pack import S4_PLAN_PREREAD

register_agent_profile(
    AgentProfile(
        scenario_id=S4_SCENARIO_ID,
        default_agent_state=_default_agent_state,
        init_session=init_s4_agent_state,
        handle_follow_up=handle_s4_agent_follow_up,
        build_workflow=build_s4_agent_workflow,
        followups_for_agent_mode=s4_followups_for_agent_mode,
        plan_preread_follow_ups=tuple(S4_PLAN_PREREAD),
        finalize_remediation_after_apply=finalize_s4_remediation_after_apply,
        conversational_follow_ups=S4_AGENT_CONVERSATIONAL_FOLLOWUPS,
    )
)
