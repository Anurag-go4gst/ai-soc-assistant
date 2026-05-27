from __future__ import annotations

from typing import Any

from app.actions.capability_policy import ActionCapability
from app.answer_guard.models import AnswerGuardStatus
from app.lineage.models import InvestigationLineage, LineageStage
from app.risk.severity_policy import SeverityDecision
from app.synthesis.models import SynthesisStatus


def build_investigation_lineage(
    *,
    trace_id: str,
    mode_source: str,
    query_understanding: Any,
    selected_use_case: Any,
    selected_skill_chain: Any,
    workflow_plan: dict[str, Any],
    spl_validation: dict[str, Any] | None,
    execution: dict[str, Any],
    source_evidence: list[dict[str, Any]],
    structured_context: dict[str, Any] | None,
    context_sufficiency: dict[str, Any] | None,
    spl_template: dict[str, object] | None,
    mitre_mappings: list[Any],
    severity_decision: SeverityDecision,
    synthesis_status: SynthesisStatus,
    answer_guard_status: AnswerGuardStatus,
    action_capability: ActionCapability,
) -> InvestigationLineage:
    use_case_id = selected_use_case.use_case_id if selected_use_case else None
    return InvestigationLineage(
        lineage_id=f"lineage:{trace_id}",
        summary="Query understanding, skill-chain selection, captured Foundation-sec packaging, and governance status were recorded without enabling final synthesis or remediation.",
        stages=[
            _stage("query_understanding", "complete", "Query understanding", f"Mapped query to {use_case_id or 'no specific use case'}.", {"mapped_use_case_ids": getattr(query_understanding, "mapped_use_case_ids", [])}, [], mode_source, "production query parser"),
            _stage("skill_chain", "complete", "Skill chain", f"Selected {selected_skill_chain.selected_skill}.", selected_skill_chain.model_dump(), [], mode_source, "production skill registry"),
            _stage("workflow", "complete", "Workflow planning", workflow_plan.get("message", "Workflow plan created."), {"status": workflow_plan.get("status"), "execution_enabled": workflow_plan.get("execution_enabled")}, [], mode_source, "production workflow planner"),
            _stage("spl_template", "complete" if spl_template else "skipped", "SPL template", "Template metadata attached when a use-case template exists.", spl_template or {}, ["spl_code"] if spl_template else [], "config" if spl_template else mode_source, "SCD/template registry"),
            _stage("spl_validation", "complete" if spl_validation else "skipped", "SPL validation", "Candidate SPL is validated before any MCP gate.", spl_validation or {}, [], mode_source, "production SPL validator"),
            _stage("mcp_tool_decision", execution.get("status", "skipped"), "MCP execution gate", execution.get("tool_selection_reason", "No MCP execution required."), execution, [], mode_source, "production MCP gate"),
            _stage("source_evidence", "complete", "Source evidence", f"{len(source_evidence)} evidence records packaged.", {"evidence_count": len(source_evidence)}, ["splunk_results_table"], mode_source, "production SourceEvidence"),
            _stage("mitre_mapping", "complete" if mitre_mappings else "skipped", "MITRE mapping", "Local MITRE mapping statuses are advisory until fully validated.", {"mappings": [_dump(item) for item in mitre_mappings]}, ["mitre_mappings"], "derived" if mitre_mappings else mode_source, "local MITRE KB"),
            _stage("severity", "complete", "Severity decision", severity_decision.severity_label, severity_decision.model_dump(), ["severity_label"], "derived", "severity matrix"),
            _stage("context_sufficiency", "complete" if context_sufficiency else "skipped", "Context sufficiency", (context_sufficiency or {}).get("status", "not evaluated"), context_sufficiency or {}, [], mode_source, "production context gate"),
            _stage("synthesis", synthesis_status.status, "LLM synthesis", synthesis_status.reason, synthesis_status.model_dump(), [], "planned", "Stage 3K"),
            _stage("answer_guard", answer_guard_status.guard_status, "Answer Guard", answer_guard_status.reason, answer_guard_status.model_dump(), [], "planned", "Stage 3L"),
            _stage("action_capability", "complete", "Action capability", action_capability.reason, action_capability.model_dump(), ["recommended_actions"], "derived", "action tier policy"),
        ],
    )


def _stage(
    stage_id: str,
    status: str,
    label: str,
    explanation: str,
    technical_output: dict[str, object],
    sections: list[str],
    mode_source: str,
    production_equivalent: str,
) -> LineageStage:
    return LineageStage(
        stage_id=stage_id,
        status=status,
        visible_label=label,
        explanation=explanation,
        technical_output=technical_output,
        produced_answer_sections=sections,
        current_mode_source=mode_source,
        production_equivalent=production_equivalent,
    )


def _dump(item: Any) -> dict[str, object]:
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return dict(item)
