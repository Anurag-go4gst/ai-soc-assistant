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
    route_plan_shadow: dict[str, Any] | None = None,
) -> InvestigationLineage:
    use_case_id = selected_use_case.use_case_id if selected_use_case else None
    stages = [
        _stage("query_understanding", "complete", "Query understanding", f"Mapped query to {use_case_id or 'no specific use case'}.", {"mapped_use_case_ids": getattr(query_understanding, "mapped_use_case_ids", [])}, [], mode_source, "production query parser"),
        _stage("skill_chain", "complete", "Skill chain", f"Selected {selected_skill_chain.selected_skill}.", selected_skill_chain.model_dump(), [], mode_source, "production skill registry"),
        _stage("workflow", "complete", "Workflow planning", workflow_plan.get("message", "Workflow plan created."), {"status": workflow_plan.get("status"), "execution_enabled": workflow_plan.get("execution_enabled")}, [], mode_source, "production workflow planner"),
    ]
    if route_plan_shadow is not None:
        stages.append(
            _stage(
                "route_plan_shadow",
                str(route_plan_shadow.get("route_status") or route_plan_shadow.get("preflight_status") or "observed"),
                "Route-plan shadow",
                "Dormant route-plan preflight and validation metadata only; execution remains unauthorized.",
                route_plan_shadow,
                [],
                "shadow",
                "Stage 3K-R2 dormant route-plan validator",
            )
        )
        if route_plan_shadow.get("llm_called"):
            stages.append(_llm_route_plan_candidate_stage(route_plan_shadow))
        if route_plan_shadow.get("template_match_attempted"):
            stages.append(_template_match_shadow_stage(route_plan_shadow))
        if route_plan_shadow.get("analyst_summary_shadow_available"):
            stages.append(_analyst_summary_shadow_stage(route_plan_shadow))
        if route_plan_shadow.get("intent_operation_bridge"):
            stages.append(_intent_operation_bridge_stage(route_plan_shadow))
        if route_plan_shadow.get("route_authority_compare"):
            stages.append(_route_authority_compare_stage(route_plan_shadow))
    stages.extend(
        [
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
        ]
    )
    return InvestigationLineage(
        lineage_id=f"lineage:{trace_id}",
        summary="Query understanding, skill-chain selection, captured Foundation-sec packaging, and governance status were recorded without enabling final synthesis or remediation.",
        stages=stages,
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


def _llm_route_plan_candidate_stage(route_plan_shadow: dict[str, Any]) -> LineageStage:
    dropped = route_plan_shadow.get("llm_candidate_dropped_reasons") or []
    if route_plan_shadow.get("llm_candidate_route_plan_available"):
        status = "accepted_shadow"
    elif dropped:
        status = "dropped"
    else:
        status = "observed"
    return _stage(
        "llm_route_plan_candidate",
        status,
        "LLM route-plan candidate (shadow)",
        "Instruct-only shadow candidate; deterministic routing and validation retain authority.",
        {
            "llm_role": route_plan_shadow.get("llm_role"),
            "llm_model_family": route_plan_shadow.get("llm_model_family"),
            "llm_candidate_route_plan_available": route_plan_shadow.get("llm_candidate_route_plan_available"),
            "llm_candidate_dropped_reasons": dropped,
            "deterministic_route_plan_wins": route_plan_shadow.get("deterministic_route_plan_wins"),
            "disagreements": route_plan_shadow.get("disagreements"),
            "coe_synthetic_fixture": route_plan_shadow.get("coe_synthetic_fixture"),
            "captured_live_run": route_plan_shadow.get("captured_live_run"),
            "production_execution": route_plan_shadow.get("production_execution"),
        },
        [],
        "shadow",
        "Stage 3K-Q1F LLM route-plan candidate generator",
    )


def _analyst_summary_shadow_stage(route_plan_shadow: dict[str, Any]) -> LineageStage:
    source = str(route_plan_shadow.get("analyst_summary_shadow_source") or "unknown")
    dropped = route_plan_shadow.get("analyst_summary_dropped_reasons") or []
    status = "dropped" if dropped and source == "deterministic_skeleton" else "observed"
    if source == "llm_shadow" and not dropped:
        status = "accepted_shadow"
    return _stage(
        "analyst_summary_shadow",
        status,
        "Analyst summary (shadow narration)",
        "Dormant shadow narration for lineage reveal only; not used as the analyst-facing answer.",
        {
            "analyst_summary_shadow_text": route_plan_shadow.get("analyst_summary_shadow_text"),
            "analyst_summary_trace_bullets": route_plan_shadow.get("analyst_summary_trace_bullets"),
            "analyst_summary_shadow_source": source,
            "analyst_summary_dropped_reasons": dropped,
            "analyst_summary_narration_llm_called": route_plan_shadow.get("analyst_summary_narration_llm_called"),
            "coe_synthetic_fixture": route_plan_shadow.get("coe_synthetic_fixture"),
            "captured_live_run": route_plan_shadow.get("captured_live_run"),
            "production_execution": route_plan_shadow.get("production_execution"),
        },
        [],
        "shadow",
        "Stage 3K-Q1G Instruct shadow narration",
    )


def _route_authority_compare_stage(route_plan_shadow: dict[str, Any]) -> LineageStage:
    compare = route_plan_shadow.get("route_authority_compare") or {}
    status = str(compare.get("intent_operation_bridge_status") or "observed")
    return _stage(
        "route_authority_compare",
        status,
        "Route authority compare (shadow)",
        "Dual-run compare of legacy selected_skill vs route_plan primary_skill; no authority migration.",
        dict(compare),
        [],
        "shadow",
        "Stage 3L-S3 Steps 1–2 route authority compare",
    )


def _intent_operation_bridge_stage(route_plan_shadow: dict[str, Any]) -> LineageStage:
    bridge = route_plan_shadow.get("intent_operation_bridge") or {}
    status = str(bridge.get("bridge_status") or "observed")
    return _stage(
        "intent_operation_bridge",
        status,
        "Intent ↔ operation bridge (shadow)",
        "Legacy SKILL_ENUM intent compared to route_plan.primary_skill for lineage only; selected_skill unchanged.",
        dict(bridge),
        [],
        "shadow",
        "Stage 3L-S2A-FOLLOWUP intent-to-operation bridge",
    )


def _template_match_shadow_stage(route_plan_shadow: dict[str, Any]) -> LineageStage:
    status = str(route_plan_shadow.get("template_match_shadow_status") or "no_match")
    return _stage(
        "template_match_shadow",
        status,
        "Template match (shadow)",
        "Dormant template candidate only. Not executed. Execution authorized: false.",
        {
            "matched_template_id": route_plan_shadow.get("matched_template_id"),
            "template_validator_profile": route_plan_shadow.get("template_validator_profile"),
            "template_sample_only": route_plan_shadow.get("template_sample_only"),
            "template_production_executable": route_plan_shadow.get("template_production_executable"),
            "rendered_spl_available": route_plan_shadow.get("rendered_spl_available"),
            "rendered_spl_validator_approved": route_plan_shadow.get("rendered_spl_validator_approved"),
            "rendered_spl_execution_eligible": route_plan_shadow.get("rendered_spl_execution_eligible"),
            "rendered_spl_sha256": route_plan_shadow.get("rendered_spl_sha256"),
            "evidence_output_contract": route_plan_shadow.get("evidence_output_contract"),
            "template_mismatch_reasons": route_plan_shadow.get("template_mismatch_reasons"),
            "coe_synthetic_fixture": route_plan_shadow.get("coe_synthetic_fixture"),
            "captured_live_run": route_plan_shadow.get("captured_live_run"),
            "production_execution": route_plan_shadow.get("production_execution"),
        },
        [],
        "shadow",
        "Stage 3K-Q1E deterministic template matcher and renderer",
    )
