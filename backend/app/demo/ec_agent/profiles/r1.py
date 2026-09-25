"""R1 governed RAG answer — agent workflow profile."""

from __future__ import annotations

from app.demo.ec_agent.registry import register_agent_profile
from app.demo.ec_agent.types import AgentProfile
from app.demo.fixtures.r1.pack import (
    R1_SCENARIO_ID,
    build_r1_agent_workflow,
    default_agent_state,
    finalize_r1_remediation_after_apply,
    handle_r1_agent_follow_up,
    init_r1_agent_state,
    r1_followups_for_agent_mode,
)

register_agent_profile(
    AgentProfile(
        scenario_id=R1_SCENARIO_ID,
        default_agent_state=default_agent_state,
        init_session=init_r1_agent_state,
        handle_follow_up=handle_r1_agent_follow_up,
        build_workflow=build_r1_agent_workflow,
        followups_for_agent_mode=r1_followups_for_agent_mode,
        finalize_remediation_after_apply=finalize_r1_remediation_after_apply,
    )
)
