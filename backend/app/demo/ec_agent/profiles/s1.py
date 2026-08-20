"""S1 newly observed IP — agent workflow profile."""

from __future__ import annotations

from app.demo.ec_agent.registry import register_agent_profile
from app.demo.ec_agent.types import AgentProfile
from app.demo.fixtures.s1.agent_config import CONVERSATIONAL_FOLLOWUPS, PLAN_PREREAD, S1_SCENARIO_ID
from app.demo.fixtures.s1.agent_handler import (
    build_s1_agent_workflow,
    default_agent_state,
    finalize_s1_remediation_after_apply,
    handle_s1_agent_follow_up,
    init_s1_agent_state,
    s1_followups_for_agent_mode,
)

register_agent_profile(
    AgentProfile(
        scenario_id=S1_SCENARIO_ID,
        default_agent_state=default_agent_state,
        init_session=init_s1_agent_state,
        handle_follow_up=handle_s1_agent_follow_up,
        build_workflow=build_s1_agent_workflow,
        followups_for_agent_mode=s1_followups_for_agent_mode,
        plan_preread_follow_ups=PLAN_PREREAD,
        finalize_remediation_after_apply=finalize_s1_remediation_after_apply,
        conversational_follow_ups=CONVERSATIONAL_FOLLOWUPS,
    )
)
