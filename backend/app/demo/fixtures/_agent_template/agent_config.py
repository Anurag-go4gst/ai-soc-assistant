"""Stub agent config — copy into fixtures/sN/agent_config.py and customize."""

from __future__ import annotations

from typing import Any

SCENARIO_ID = "your_scenario_id"

INVESTIGATION_STEP_DEFS: tuple[dict[str, Any], ...] = (
    {
        "id": "step_one",
        "title": "First investigation step",
        "summary": "What this step establishes.",
        "follow_up_id": "your_follow_up_id",
        "tools": ["Splunk MCP"],
        "default_selected": True,
        "phase": "investigation",
    },
)

REMEDIATION_STEP_DEFS: tuple[dict[str, Any], ...] = (
    {
        "id": "remediate_one",
        "title": "First remediation action",
        "summary": "Governed action with HIL.",
        "follow_up_id": "your_remediation_follow_up",
        "tools": ["ITSM"],
        "hil_required": True,
        "default_selected": True,
        "phase": "remediation",
    },
)

INVESTIGATION_PLAN_SUMMARY = "Short plan summary for the investigation phase."
ACTION_PLAN_SUMMARY = "Short narrative for the action plan card."
CONVERSATIONAL_FOLLOWUPS = frozenset({"generate_executive_summary"})

OPENING_NARRATIVE = "Scenario opening line shown at plan phase."
BRIEF = {
    "what_i_know": ["Fact one", "Fact two"],
    "objective": ["Objective one", "Objective two"],
}
ACTION_PLAN_STEPS = [
    "Step one in the high-level action plan",
    "Step two in the high-level action plan",
]
