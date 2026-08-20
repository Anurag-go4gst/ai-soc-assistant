"""S2 prompt-injection — agent workflow profile."""

from __future__ import annotations

from app.demo.ec_agent.registry import register_agent_profile
from app.demo.ec_agent.types import AgentProfile
from app.demo.fixtures.s2.agent_config import CONVERSATIONAL_FOLLOWUPS, PLAN_PREREAD, S2_SCENARIO_ID
from app.demo.fixtures.s2.agent_handler import (
    build_s2_agent_workflow,
    default_agent_state,
    finalize_s2_remediation_after_apply,
    handle_s2_agent_follow_up,
    init_s2_agent_state,
    s2_followups_for_agent_mode,
)

register_agent_profile(
    AgentProfile(
        scenario_id=S2_SCENARIO_ID,
        default_agent_state=default_agent_state,
        init_session=init_s2_agent_state,
        handle_follow_up=handle_s2_agent_follow_up,
        build_workflow=build_s2_agent_workflow,
        followups_for_agent_mode=s2_followups_for_agent_mode,
        plan_preread_follow_ups=PLAN_PREREAD,
        finalize_remediation_after_apply=finalize_s2_remediation_after_apply,
        conversational_follow_ups=CONVERSATIONAL_FOLLOWUPS,
    )
)
