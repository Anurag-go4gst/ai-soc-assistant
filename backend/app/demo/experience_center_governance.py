"""Stage 3M-EC: Experience Center governance panels (demo trace only; no execution)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.demo.mcp_result_envelope import demo_envelope_from_rows
from app.risk.severity_policy import SeverityDecision

COMPLETED_CAPABILITIES = [
    "legacy intent routing",
    "runtime operation contracts",
    "intent-to-operation bridge",
    "SPL validation metadata",
    "MCP execution gate",
    "evidence packaging",
    "MITRE mapping",
    "severity decision",
    "context sufficiency",
    "action capability policy",
]

GATED_WIP_CAPABILITIES = [
    "live MCP/Splunk execution",
    "first real MCP schema confirmation",
    "final LLM synthesis",
    "Answer Guard execution",
    "renderer consumption of output artifacts",
    "pattern #2 authority expansion",
    "full production readiness for all 105 questions",
]

PIPELINE_STAGE_SPECS: list[tuple[str, str, str]] = [
    ("query_understanding", "query_understanding", "Query understanding"),
    ("workflow_planning", "workflow", "Workflow planning"),
    ("spl_template", "spl_template", "SPL template"),
    ("spl_validation", "spl_validation", "SPL validation"),
    ("mcp_execution_gate", "mcp_tool_decision", "MCP execution gate"),
    ("source_evidence", "source_evidence", "Source evidence"),
    ("mitre_mapping", "mitre_mapping", "MITRE mapping"),
    ("severity_decision", "severity", "Severity decision"),
    ("context_sufficiency", "context_sufficiency", "Context sufficiency"),
    ("action_capability", "action_capability", "Action capability"),
    ("llm_synthesis_planned", "synthesis", "LLM synthesis planned"),
    ("answer_guard_planned", "answer_guard", "Answer Guard planned"),
]

FAILED_LOGIN_WHY_P2 = [
    "high failed-login volume",
    "multiple source IPs",
    "APP-01 target",
    "T1110.001 supported",
]

FAILED_LOGIN_WHY_NOT_P1_P0 = [
    "no confirmed successful login after failures",
    "no confirmed privileged/service account impact",
    "no confirmed critical asset status",
    "no confirmed source ownership",
    "no confirmed post-authentication activity",
    "account compromise not confirmed",
]

SEVERITY_PRIORITY_NOTE = (
    "Action priority is not the same as incident severity. P1 actions are immediate validation tasks; "
    "the current incident severity remains P2 High."
)


class McpEnvelopeGovernancePanel(BaseModel):
    available: bool = False
    origin: str | None = None
    schema_confirmed: bool | None = None
    schema_confirmed_reason: str | None = None
    status: str | None = None
    row_count: int | None = None
    total_row_count: int | None = None
    truncated: bool | None = None
    truncation_reason: str | None = None
    fields: list[str] = Field(default_factory=list)
    preview_rows_count: int | None = None
    warnings: list[str] = Field(default_factory=list)
    provenance: str | None = None
    executed_spl: str | None = None


class SeverityGovernancePanel(BaseModel):
    severity_label: str
    why_severity_title: str
    why_severity: list[str] = Field(default_factory=list)
    why_not_higher_title: str = "Why not P1/P0?"
    why_not_higher: list[str] = Field(default_factory=list)
    priority_note: str | None = None


class PipelineStageStatus(BaseModel):
    stage_id: str
    label: str
    status: str


class SkillsOperationsGovernancePanel(BaseModel):
    intent_skill: str
    legacy_router_skill: str
    runtime_operation: str | None = None
    runtime_operation_note: str
    pipeline_stages: list[PipelineStageStatus] = Field(default_factory=list)


class CompletionStatusGovernancePanel(BaseModel):
    completed: list[str] = Field(default_factory=list)
    gated_wip: list[str] = Field(default_factory=list)


class ExperienceCenterGovernance(BaseModel):
    mcp_envelope: McpEnvelopeGovernancePanel | None = None
    severity: SeverityGovernancePanel | None = None
    skills_operations: SkillsOperationsGovernancePanel
    completion_status: CompletionStatusGovernancePanel


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
) -> ExperienceCenterGovernance:
    envelope_panel = _mcp_envelope_panel(source_evidence, execution)
    severity_panel = _severity_panel(scenario_id, severity_decision)
    skills_panel = _skills_operations_panel(
        selected_skill=selected_skill,
        investigation_lineage=investigation_lineage,
        route_plan_shadow=route_plan_shadow,
        selected_use_case=selected_use_case,
    )
    return ExperienceCenterGovernance(
        mcp_envelope=envelope_panel,
        severity=severity_panel,
        skills_operations=skills_panel,
        completion_status=CompletionStatusGovernancePanel(
            completed=list(COMPLETED_CAPABILITIES),
            gated_wip=list(GATED_WIP_CAPABILITIES),
        ),
    )


def _mcp_envelope_panel(
    source_evidence: list[dict[str, Any]],
    execution: dict[str, Any] | None,
) -> McpEnvelopeGovernancePanel | None:
    splunk_items = [item for item in source_evidence if item.get("source_type") == "splunk_mcp"]
    if not splunk_items and not (execution or {}).get("splunk_result_envelope"):
        return None

    envelope_dict: dict[str, Any] | None = None
    executed_spl: str | None = None
    if execution and isinstance(execution.get("splunk_result_envelope"), dict):
        envelope_dict = execution["splunk_result_envelope"]
        executed_spl = execution.get("executed_spl")
    elif splunk_items:
        item = splunk_items[0]
        preview_rows = item.get("preview_rows") or []
        if isinstance(preview_rows, list) and preview_rows:
            envelope = demo_envelope_from_rows(
                preview_rows,
                trace_id=str(item.get("trace_id") or ""),
                normalized_spl=item.get("executed_spl"),
            )
            envelope_dict = envelope.to_dict()
        executed_spl = item.get("executed_spl")

    if not envelope_dict:
        return McpEnvelopeGovernancePanel(available=False)

    preview_rows = envelope_dict.get("rows") or []
    return McpEnvelopeGovernancePanel(
        available=True,
        origin=str(envelope_dict.get("origin") or ""),
        schema_confirmed=bool(envelope_dict.get("schema_confirmed")),
        schema_confirmed_reason=str(envelope_dict.get("schema_confirmed_reason") or ""),
        status=str(envelope_dict.get("status") or ""),
        row_count=int(envelope_dict.get("row_count") or 0),
        total_row_count=envelope_dict.get("total_row_count"),
        truncated=bool(envelope_dict.get("truncated")),
        truncation_reason=envelope_dict.get("truncation_reason"),
        fields=[str(field) for field in envelope_dict.get("fields") or []],
        preview_rows_count=len(preview_rows) if isinstance(preview_rows, list) else 0,
        warnings=[str(warning) for warning in envelope_dict.get("warnings") or []],
        provenance=str(envelope_dict.get("provenance") or ""),
        executed_spl=executed_spl,
    )


def _severity_panel(scenario_id: str, severity_decision: SeverityDecision) -> SeverityGovernancePanel:
    label = severity_decision.severity_label
    if scenario_id == "failed_login_spike_app01" and label == "P2 High":
        return SeverityGovernancePanel(
            severity_label=label,
            why_severity_title="Why P2 High?",
            why_severity=list(FAILED_LOGIN_WHY_P2),
            why_not_higher=list(FAILED_LOGIN_WHY_NOT_P1_P0),
            priority_note=SEVERITY_PRIORITY_NOTE,
        )

    title = f"Why {label}?"
    why_severity = list(severity_decision.matched_rules) or [f"Default severity policy applied: {label}."]
    why_not_higher = list(severity_decision.why_not_higher)
    if severity_decision.missing_evidence:
        why_not_higher.extend(
            f"missing evidence for escalation: {item}" for item in severity_decision.missing_evidence
        )
    return SeverityGovernancePanel(
        severity_label=label,
        why_severity_title=title,
        why_severity=why_severity,
        why_not_higher=why_not_higher or ["Higher severity thresholds were not met by available evidence."],
        priority_note=None,
    )


def _skills_operations_panel(
    *,
    selected_skill: str,
    investigation_lineage: dict[str, Any] | None,
    route_plan_shadow: dict[str, Any] | None,
    selected_use_case: dict[str, Any] | None,
) -> SkillsOperationsGovernancePanel:
    runtime_operation, runtime_note = _runtime_operation(route_plan_shadow, selected_use_case)
    lineage_stages = {
        str(stage.get("stage_id")): str(stage.get("status") or "unknown")
        for stage in (investigation_lineage or {}).get("stages") or []
        if isinstance(stage, dict)
    }
    pipeline = [
        PipelineStageStatus(
            stage_id=panel_id,
            label=label,
            status=lineage_stages.get(lineage_id, "not evaluated"),
        )
        for panel_id, lineage_id, label in PIPELINE_STAGE_SPECS
    ]
    return SkillsOperationsGovernancePanel(
        intent_skill=selected_skill,
        legacy_router_skill=selected_skill,
        runtime_operation=runtime_operation,
        runtime_operation_note=runtime_note,
        pipeline_stages=pipeline,
    )


def _runtime_operation(
    route_plan_shadow: dict[str, Any] | None,
    selected_use_case: dict[str, Any] | None,
) -> tuple[str | None, str]:
    if route_plan_shadow:
        bridge = route_plan_shadow.get("intent_operation_bridge")
        if isinstance(bridge, dict):
            operation = bridge.get("runtime_operation") or bridge.get("operation_id")
            if operation:
                return str(operation), "from route_plan_shadow intent-operation bridge (shadow only)"
        operation = route_plan_shadow.get("runtime_operation") or route_plan_shadow.get("coverage_operation")
        if operation:
            return str(operation), "from route_plan_shadow metadata (shadow only)"

    if selected_use_case:
        use_case_id = selected_use_case.get("use_case_id")
        if use_case_id:
            return None, f"not evaluated in demo fixture (production-equivalent mapping available: {use_case_id})"

    return None, "not evaluated in demo fixture"
