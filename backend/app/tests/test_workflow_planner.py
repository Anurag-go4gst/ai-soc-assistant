from __future__ import annotations

from typing import Any

import pytest

from app.orchestration.workflow_planner import plan_workflow


EXPECTED_STEPS = {
    "alert_summary": [
        "retrieve related alerts",
        "retrieve approved SOP/RAG context",
        "generate timeline",
        "map to MITRE",
        "synthesize analyst summary",
    ],
    "attack_discovery": [
        "generate candidate SPL",
        "validate SPL",
        "execute validated SPL through MCP",
        "minimize results",
        "map to MITRE",
        "synthesize findings",
    ],
    "spl_generation": [
        "retrieve SPL examples/policy",
        "generate candidate SPL",
        "validate SPL",
        "return validated SPL for analyst review",
    ],
    "knowledge_recall": [
        "retrieve approved documents",
        "rank chunks",
        "synthesize grounded answer",
    ],
}


@pytest.mark.parametrize("skill,expected_steps", EXPECTED_STEPS.items())
def test_each_skill_returns_expected_workflow_steps(skill: str, expected_steps: list[str]) -> None:
    telemetry = FakeTelemetry()
    plan = plan_workflow(
        selected_skill=skill,
        tool_plan=["route_only", skill],
        query="test analyst query",
        trace_id=f"trace-{skill}",
        telemetry=telemetry,
    )

    assert plan["skill"] == skill
    assert plan["status"] == "not_started"
    assert plan["execution_enabled"] is False
    assert [step["name"] for step in plan["steps"]] == expected_steps
    assert [step["order"] for step in plan["steps"]] == list(range(1, len(expected_steps) + 1))
    assert all(step["status"] == "not_started" for step in plan["steps"])
    assert telemetry.steps[0]["step_name"] == "workflow_plan_created"
    assert telemetry.steps[0]["status"] == "not_started"


def test_workflow_planner_rejects_unknown_skill() -> None:
    with pytest.raises(ValueError):
        plan_workflow(
            selected_skill="invalid_skill",
            tool_plan=["route_only"],
            query="test",
            trace_id="trace-invalid",
            telemetry=FakeTelemetry(),
        )


def test_attack_discovery_plan_is_planning_only() -> None:
    telemetry = FakeTelemetry()
    plan = plan_workflow(
        selected_skill="attack_discovery",
        tool_plan=["route_only", "attack_discovery"],
        query="Top source IPs by failed login count in the last hour.",
        trace_id="trace-attack",
        telemetry=telemetry,
    )

    assert "mcp" in plan["required_connectors"]
    assert "execution_not_enabled" in plan["safety_gates"]
    assert "spl_generation_not_enabled" in plan["safety_gates"]
    assert not hasattr(telemetry, "record_mcp_execution")
    assert not hasattr(telemetry, "record_rag_retrieval")
    assert not hasattr(telemetry, "splunk_write")


class FakeTelemetry:
    def __init__(self) -> None:
        self.steps: list[dict[str, Any]] = []

    def record_step(self, trace_id: str, step_name: str, status: str, **fields: Any) -> None:
        self.steps.append({"trace_id": trace_id, "step_name": step_name, "status": status, **fields})
