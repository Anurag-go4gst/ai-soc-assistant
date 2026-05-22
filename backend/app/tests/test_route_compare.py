from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.connectors.llm.base import SkillRoutingCompletion
from app.routing.deterministic_router import route_skill_deterministic
from app.routing.llm_planner import route_skill_llm_shadow
from app.routing.route_adjudicator import adjudicate_route
from app.routing.route_compare import compare_routes
from app.routing.skill_router import route_skill
from app.routing.skills import SKILL_ENUM, validate_skill


STAGE_1_CASES: tuple[tuple[str, str], ...] = (
    ("In the last hour, which users have abnormally high failed login counts?", "attack_discovery"),
    ("Top source IPs by failed login count in the last hour.", "attack_discovery"),
    (
        "Find successful logins that followed multiple failed login attempts from the same source in the last hour.",
        "attack_discovery",
    ),
    ("Which users had the most authentication events in the last hour?", "knowledge_recall"),
    ("Show account lockouts over time in the last hour.", "alert_summary"),
    ("Show successful logins from new or unusual source IPs in the last hour.", "attack_discovery"),
)


def test_six_stage_1_auth_queries_route_to_expected_skill() -> None:
    for query, expected_skill in STAGE_1_CASES:
        routed = route_skill_deterministic(query)
        assert routed["skill"] == expected_skill


def test_closed_skill_enum_rejects_invalid_skill() -> None:
    assert "attack_discovery" in SKILL_ENUM
    with pytest.raises(ValueError):
        validate_skill("investigate_authentication")


def test_deterministic_output_shape_is_stable() -> None:
    routed = route_skill_deterministic("Top source IPs by failed login count in the last hour.")
    assert set(routed.keys()) == {"skill", "tool_plan", "confidence", "reasons"}
    assert isinstance(routed["tool_plan"], list)
    assert isinstance(routed["confidence"], float)
    assert isinstance(routed["reasons"], list)


def test_llm_shadow_output_shape_is_stable() -> None:
    routed = route_skill_llm_shadow("Show account lockouts over time in the last hour.")
    assert set(routed.keys()) == {"skill", "tool_plan", "confidence", "reasons"}
    assert routed["skill"] == "alert_summary"
    assert isinstance(routed["tool_plan"], list)
    assert isinstance(routed["confidence"], float)
    assert isinstance(routed["reasons"], list)


def test_compare_and_adjudicate_prefers_high_confidence_deterministic() -> None:
    deterministic = route_skill_deterministic("brute force failed login activity")
    llm_shadow = route_skill_llm_shadow("brute force failed login activity")
    comparison = compare_routes(llm_shadow, deterministic)
    adjudicated = adjudicate_route(comparison)

    assert comparison["match"] is True
    assert adjudicated["selected"]["skill"] == "attack_discovery"


def test_routing_disagreement_is_recorded_to_telemetry() -> None:
    telemetry = FakeTelemetry()
    routed = route_skill(
        "Top source IPs by failed login count in the last hour.",
        trace_id="trace-disagree",
        telemetry=telemetry,
        llm_connector=DisagreeingLlmConnector(),
    )

    assert routed["skill"] == "attack_discovery"
    assert telemetry.disagreements
    event = telemetry.disagreements[0]
    assert event["trace_id"] == "trace-disagree"
    assert event["disagreement_reason"] == "skill_mismatch"
    assert event["deterministic"]["skill"] == "attack_discovery"
    assert event["llm_shadow"]["skill"] == "alert_summary"
    assert event["selected"]["skill"] == "attack_discovery"


def test_routing_agreement_records_decision_not_disagreement() -> None:
    telemetry = FakeTelemetry()
    route_skill(
        "Show account lockouts over time in the last hour.",
        trace_id="trace-agree",
        telemetry=telemetry,
    )

    assert telemetry.decisions
    assert telemetry.disagreements == []
    assert telemetry.decisions[0]["trace_id"] == "trace-agree"


def test_low_confidence_returns_needs_clarification_route() -> None:
    telemetry = FakeTelemetry()
    routed = route_skill(
        "Please look at this vague situation.",
        trace_id="trace-low",
        telemetry=telemetry,
        threshold=0.80,
    )

    assert routed["skill"] == "knowledge_recall"
    assert routed["tool_plan"] == ["needs_clarification"]
    assert any("needs clarification" in reason for reason in routed["reasons"])


def test_no_splunk_write_is_attempted_by_routing() -> None:
    telemetry = FakeTelemetry()
    route_skill("Top source IPs by failed login count in the last hour.", telemetry=telemetry)
    assert not hasattr(telemetry, "splunk_write")


class FakeTelemetry:
    def __init__(self) -> None:
        self.decisions: list[dict[str, Any]] = []
        self.disagreements: list[dict[str, Any]] = []

    def record_routing_decision(self, trace_id: str, **fields: Any) -> None:
        self.decisions.append({"trace_id": trace_id, **fields})

    def record_routing_disagreement(self, trace_id: str, **fields: Any) -> None:
        self.disagreements.append({"trace_id": trace_id, **fields})


@dataclass
class DisagreeingLlmConnector:
    def complete_skill_routing(self, payload: dict[str, Any]) -> SkillRoutingCompletion:
        return SkillRoutingCompletion(
            skill="alert_summary",
            confidence=0.74,
            rationale="forced_test_disagreement",
            metadata={"mock": True},
        )
