from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.config import ConfigError, Settings, _validate, settings
from app.connectors.llm.base import SkillRoutingCompletion
from app.routing.skill_router import route_skill


def test_deterministic_only_does_not_call_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "routing_mode", "deterministic_only")
    connector = CountingLlmConnector(skill="alert_summary", metadata={"use_case_id": "UC001"})

    routed = route_skill("Top source IPs by failed login count in the last hour.", llm_connector=connector)

    assert connector.calls == 0
    assert routed["skill"] == "attack_discovery"
    assert routed["llm_shadow"] is None
    assert routed["route_decision"]["selected_by"] == "deterministic"


def test_llm_shadow_only_calls_llm_for_comparison_and_selects_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "routing_mode", "llm_shadow_only")
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", True)
    connector = CountingLlmConnector(skill="alert_summary", confidence=0.99)

    routed = route_skill("Top source IPs by failed login count in the last hour.", llm_connector=connector)

    assert connector.calls == 1
    assert routed["skill"] == "attack_discovery"
    assert routed["route_decision"]["selected_by"] == "shadow_only"
    assert routed["route_decision"]["llm_confidence_metadata"]["skill_confidence"] == 0.99


def test_shadow_disabled_prevents_llm_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "routing_mode", "llm_shadow_only")
    monkeypatch.setattr(settings, "routing_llm_shadow_enabled", False)
    connector = CountingLlmConnector(skill="alert_summary")

    routed = route_skill("Show account lockouts over time in the last hour.", llm_connector=connector)

    assert connector.calls == 0
    assert routed["llm_shadow"] is None
    assert "llm_shadow_disabled" in routed["route_decision"]["guard_checks"]


def test_llm_assisted_normalizes_and_rejects_unknown_registry_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "routing_mode", "llm_assisted_semantic")
    connector = CountingLlmConnector(
        skill="knowledge_recall",
        confidence=0.99,
        metadata={
            "use_case_id": "UC001",
            "selected_skill": "Credential Stuffing Detection",
            "evidence_needs": [
                {
                    "need_id": "auth",
                    "source_type": "splunk_auth_evidence",
                    "why": "validate the auth event pattern",
                    "priority": "High",
                    "suggested_tool_hint": "splunk_run_query",
                    "requires_validation": False,
                }
            ],
            "suggested_mcp_tools": ["splunk_run_query"],
        },
    )

    routed = route_skill("In the last hour, which users have abnormally high failed login counts?", llm_connector=connector)

    advisory = routed["llm_semantic_advisory"]
    decision = routed["route_decision"]
    assert connector.calls == 1
    assert routed["skill"] == "attack_discovery"
    assert "unknown_llm_use_case_id_rejected:UC001" in advisory["warnings"]
    assert "unknown_llm_selected_skill_rejected:Credential Stuffing Detection" in advisory["warnings"]
    assert advisory["llm_evidence_needs"][0]["priority"] == "P3"
    assert advisory["llm_evidence_needs"][0]["requires_validation"] is True
    assert "use_case_id" in decision["disagreements"]
    assert decision["deterministic_tool_mapping_summary"][0]["gated_after_validation_tools"] == ["splunk_run_query"]
    assert decision["deterministic_tool_mapping_summary"][0]["accepted_or_ignored"] == "ignored_raw_llm_tools"


def test_context_dependent_mitre_prompt_forces_clarification_before_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "routing_mode", "llm_assisted_semantic")
    connector = CountingLlmConnector(skill="spl_generation", confidence=0.99)

    routed = route_skill("Map this alert to MITRE", llm_connector=connector)

    assert connector.calls == 0
    assert routed["skill"] == "knowledge_recall"
    assert routed["tool_plan"] == ["needs_clarification"]
    assert routed["selected"]["requested_output_type"] == "clarification"
    assert routed["route_decision"]["selected_by"] == "deterministic_clarification"
    assert "deterministic_clarification_override" in routed["route_decision"]["guard_checks"]


def test_lab_llm_primary_requires_explicit_lab_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "routing_mode", "llm_primary_lab")
    monkeypatch.setattr(settings, "routing_lab_llm_primary_enabled", False)
    connector = CountingLlmConnector(skill="alert_summary", confidence=0.99)

    routed = route_skill("Top source IPs by failed login count in the last hour.", llm_connector=connector)

    assert connector.calls == 0
    assert routed["skill"] == "attack_discovery"
    assert "lab_llm_primary_blocked" in routed["route_decision"]["guard_checks"]


def test_lab_llm_primary_config_fails_in_production_without_flag() -> None:
    with pytest.raises(ConfigError):
        _validate(Settings(routing_mode="llm_primary_lab", ai_soc_environment_mode="production", routing_lab_llm_primary_enabled=True))
    with pytest.raises(ConfigError):
        _validate(Settings(routing_mode="llm_primary_lab", ai_soc_environment_mode="development", routing_lab_llm_primary_enabled=False))


def test_legacy_llm_primary_config_maps_to_safe_assisted_mode() -> None:
    validated = _validate(Settings(routing_mode="llm_primary"))
    assert validated.routing_mode == "llm_assisted_semantic"


@dataclass
class CountingLlmConnector:
    skill: str
    confidence: float = 0.72
    metadata: dict[str, Any] = field(default_factory=dict)
    calls: int = 0

    def complete_skill_routing(self, payload: dict[str, Any]) -> SkillRoutingCompletion:
        self.calls += 1
        return SkillRoutingCompletion(
            skill=self.skill,
            confidence=self.confidence,
            rationale="test_llm_advisory",
            metadata=self.metadata,
        )
