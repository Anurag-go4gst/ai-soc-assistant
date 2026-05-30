"""Experience Center wrapper for shared governance trace panels."""

from __future__ import annotations

from typing import Any

from app.governance.trace_panels import (
    CompletionStatusGovernancePanel,
    GovernanceTrace,
    McpEnvelopeGovernancePanel,
    PipelineStageStatus,
    SeverityGovernancePanel,
    SkillsOperationsGovernancePanel,
    build_governance_trace,
)
from app.risk.severity_policy import SeverityDecision

# Backward-compatible aliases for imports and tests.
ExperienceCenterGovernance = GovernanceTrace

__all__ = [
    "CompletionStatusGovernancePanel",
    "ExperienceCenterGovernance",
    "GovernanceTrace",
    "McpEnvelopeGovernancePanel",
    "PipelineStageStatus",
    "SeverityGovernancePanel",
    "SkillsOperationsGovernancePanel",
    "build_experience_center_governance",
    "build_governance_trace",
]


def build_experience_center_governance(
    *,
    scenario_id: str,
    selected_skill: str,
    severity_decision: SeverityDecision,
    source_evidence: list[dict[str, Any]],
    execution: dict[str, Any] | None,
    investigation_lineage: dict[str, Any] | None,
    route_plan_shadow: dict[str, Any] | None,
    selected_use_case: dict[str, Any] | None,
) -> GovernanceTrace:
    trace = build_governance_trace(
        demo_mode=True,
        scenario_id=scenario_id,
        use_case_id=selected_use_case.get("use_case_id") if selected_use_case else None,
        selected_skill=selected_skill,
        severity_decision=severity_decision,
        investigation_lineage=investigation_lineage,
        source_evidence=source_evidence,
        execution=execution,
        route_plan_shadow=route_plan_shadow,
        selected_use_case=selected_use_case,
    )
    if trace is None:
        raise RuntimeError("experience_center_governance requires selected_skill")
    return trace
