from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

from app.actions.capability_policy import ActionCapability
from app.answer_guard.models import AnswerGuardStatus
from app.lineage.models import InvestigationLineage
from app.query_understanding.models import QueryUnderstandingResult
from app.risk.severity_policy import SeverityDecision
from app.skills.models import SkillChain, SkillSelectionResult
from app.synthesis.models import SynthesisStatus
from app.threat.mitre_kb import MitreMappingDecision
from app.demo.experience_center_governance import ExperienceCenterGovernance
from app.governance.trace_panels import GovernanceTrace
from app.use_cases.models import UseCaseSelection

PlanningOutcomeStatus = Literal[
    "planned",
    "clarification_required",
    "resolution_failed",
    "planning_failed",
    "policy_blocked",
    "unsupported",
    "execution_failed",
    "persistence_failed",
]

PlanningOutcomeCategory = Literal[
    "policy",
    "clarification",
    "planner",
    "database",
    "resolution",
    "unsupported",
    "execution",
    "invariant",
]

ReconciliationReason = Literal[
    "execution_outcome_uncertain",
    "execution_step_in_progress",
]


class WorkflowStep(BaseModel):
    order: int
    name: str
    status: str
    required_connectors: list[str]
    safety_gates: list[str]


class WorkflowPlan(BaseModel):
    trace_id: str
    skill: str
    tool_plan: list[str]
    status: str
    execution_enabled: bool
    steps: list[WorkflowStep]
    required_connectors: list[str]
    safety_gates: list[str]
    required_sources: list[str] = []
    available_sources: list[str] = []
    missing_sources: list[str] = []
    message: str


class CandidateSplEnvelope(BaseModel):
    trace_id: str
    skill: str
    user_query: str
    candidate_spl: str
    generation_mode: str
    confidence: float
    assumptions: list[str]
    warnings: list[str]
    selected_candidate_spl_provider: str | None = None
    reason: str | None = None
    saia_available: bool | None = None
    saia_usable: bool | None = None
    fallback_required: bool | None = None
    candidate_spl_generated: bool | None = None
    validation_required: bool | None = None
    execution_eligible: bool | None = None
    capability_profile: dict[str, object] | None = None
    template_id: str | None = None
    llm_supported: bool | None = None
    llm_fallback_used: bool | None = None
    llm_fallback_status: str | None = None
    llm_fallback_reason: str | None = None
    llm_model: str | None = None
    llm_latency_ms: int | None = None
    spl_template_status: str | None = None
    template_production_executable: bool | None = None
    governed_limitation: str | None = None
    allowed_spl_templates: list[str] | None = None
    enrichment_evidence_requirements: list[str] | None = None
    detection_family: str | None = None
    user_constraint_bindings: dict[str, object] | None = None
    spl_binding_trace: dict[str, object] | None = None
    utility_spl_draft_trace: dict[str, object] | None = None
    review_only_spl_postprocessor_trace: dict[str, object] | None = None
    review_only_spl_postprocessor_warnings: list[str] | None = None
    # T1 SPL-native (T2 shape) review-only artifact.  Present only for the
    # runtime-source-profile SPL-native path; review-only and never executable.
    t2_spl_native: dict[str, object] | None = None


class SplDraftPreviewEnvelope(BaseModel):
    draft_spl: str
    draft_status: str
    draft_source: str
    detection_family: str
    template_match_strength: str | None = None
    assumptions: list[str]
    required_source_fields: list[str]
    source_profile_missing: bool
    governed_template_missing: bool
    validator_status: str
    validator_reject_reasons: list[str] = []
    review_required: bool
    execution_enabled: bool
    execution_eligible: bool = False
    governed: bool = False
    catalog_approved: bool = False
    user_constraint_bindings: dict[str, object] | None = None
    template_compatibility: dict[str, object] | None = None
    unbound_constraints: list[dict[str, object]] = []
    source_profile_bindings: list[dict[str, object]] = []
    source_profile_lookup_attempted: bool | None = None
    environment_knowledge_lookup_attempted: bool | None = None
    source_profile_bindings_found: list[dict[str, object]] = []
    source_profile_bindings_applied: list[dict[str, object]] = []
    source_profile_bindings_missing: list[dict[str, object]] = []
    source_family_draft_sections: list[dict[str, object]] = []
    warning: str
    not_catalog_approved_notice: str


class LlmSplCandidateEnvelope(BaseModel):
    llm_spl_candidate: str = ""
    llm_spl_candidate_status: str
    llm_spl_confidence_score: float = 0.0
    llm_spl_confidence_label: str = "low"
    detection_family: str | None = None
    quality_status: str | None = None
    validator_status: str | None = None
    quality_findings: list[dict[str, object]] = []
    validation_findings: list[str] = []
    assumptions: list[str] = []
    required_fields: list[str] = []
    missing_details: list[str] = []
    clarifying_questions: list[str] = []
    validation_notes: list[str] = []
    soc_std_rules_applied: list[str] = []
    risk_notes: list[str] = []
    execution_eligible: bool = False
    governed: bool = False
    catalog_approved: bool = False
    execution_enabled: bool = False
    review_required: bool = True
    provider: str | None = None
    model: str | None = None
    latency_ms: int | None = None


class SplValidationEnvelope(BaseModel):
    approved: bool
    normalized_spl: str | None = None
    reject_reasons: list[str]
    warnings: list[str]
    enforced_limits: dict[str, object]
    policy_version: str
    selected_candidate_spl_provider: str | None = None
    candidate_provider_reason: str | None = None
    saia_available: bool | None = None
    fallback_required: bool | None = None
    spl_explanation_provider: str | None = None
    spl_optimization_provider: str | None = None
    spl_guidance_provider: str | None = None
    optimization_applied: bool | None = None
    optimization_revalidation_status: dict[str, object] | None = None
    optimization_revalidation_approved: bool | None = None
    capability_profile: dict[str, object] | None = None
    template_id: str | None = None
    llm_supported: bool | None = None
    llm_fallback_used: bool | None = None
    llm_fallback_status: str | None = None
    llm_fallback_reason: str | None = None
    llm_model: str | None = None
    llm_latency_ms: int | None = None
    llm_fallback: dict[str, object] | None = None
    spl_template_status: str | None = None
    template_production_executable: bool | None = None
    governed_limitation: str | None = None
    allowed_spl_templates: list[str] | None = None
    enrichment_evidence_requirements: list[str] | None = None


class ExecutionEnvelope(BaseModel):
    status: str
    execution_intent: str
    selected_mcp_server: str | None = None
    selected_mcp_tool: str | None = None
    tool_selection_status: str
    tool_selection_reason: str
    executed_spl: str | None = None
    result_count: int
    results_preview: list[dict[str, object]]
    block_reason: str | None = None
    duration_ms: int
    precondition_evaluation: dict[str, object] | None = None
    # Batch 1 HIL hardening — explicit, always-present execution semantics.
    # evidence_source: mock | live | unavailable
    # execution_status_label: not_executed | review_required | mock_executed | live_executed
    evidence_source: str | None = None
    execution_status_label: str | None = None
    # G2 — execution uncertainty (additive; default preserves legacy clients).
    outcome_uncertain: bool = False
    reconciliation_reason: ReconciliationReason | None = None

    @field_validator("reconciliation_reason", mode="before")
    @classmethod
    def _reconciliation_reason_allowlist(cls, value: object, info) -> object:
        if not info.data.get("outcome_uncertain"):
            return None
        cleaned = str(value or "").strip()
        if cleaned in {"execution_outcome_uncertain", "execution_step_in_progress"}:
            return cleaned
        return "execution_outcome_uncertain"


class HumanReviewEnvelope(BaseModel):
    required: bool
    review_type: str
    reason: str
    reviewer_role: str
    allowed_actions: list[str]
    safe_message_for_user: str
    sop_reference: str | None = None
    sop_excerpt: str | None = None
    sop_action_hint: str | None = None
    proposed_normalized_spl: str | None = None
    selected_mcp_tool: str | None = None
    selected_mcp_server: str | None = None


class SourceEvidenceEnvelope(BaseModel):
    evidence_id: str
    trace_id: str
    source_type: str
    source_name: str
    tool_name: str | None = None
    collection_status: str
    query_or_request_summary: str | None = None
    executed_spl: str | None = None
    result_count: int
    fields_returned: list[str]
    preview_rows: list[dict[str, object]]
    raw_result_hash: str | None = None
    raw_result_stored: bool
    time_range: str | None = None
    warnings: list[str]
    sensitivity_flags: list[str]
    tool_category: str | None = None
    provider_used: str | None = None
    saved_search_name: str | None = None
    output_type: str | None = None
    provenance: str | None = None
    created_at: str


class StructuredFact(BaseModel):
    fact_id: str
    statement: str
    source_refs: list[str]
    derivation: str
    confidence: float | None = None


class StructuredContextPackage(BaseModel):
    trace_id: str
    query: str
    selected_skill: str
    source_evidence_refs: list[str]
    structured_facts: list[StructuredFact]
    entity_summary: dict[str, object]
    metrics: dict[str, object]
    timeline_candidates: list[dict[str, object]]
    mitre_candidates: list[dict[str, object]]
    reference_facts: list[dict[str, object]] = []
    tool_outputs_summary: list[dict[str, object]]
    llm_observations: list[dict[str, object]] = []
    capability_profile_ref: str | None = None
    spl_generation_provider: str | None = None
    spl_explanation_provider: str | None = None
    spl_optimization_provider: str | None = None
    spl_guidance_provider: str | None = None
    fallback_mode: bool = False
    execution_provider: str | None = None
    source_refs: list[str] = []
    policy_context_refs: list[str]
    sop_action_hints: list[dict[str, object]] = []
    answer_constraints: list[str] = []
    mitre_grounding_refs: list[str] = []
    splunk_context_refs: list[str] = []
    tool_policy_refs: list[str] = []
    environment_grounding_refs: list[str] = []
    knowledge_ambiguity: list[str] = []
    validation_warnings: list[str] = []
    assumptions: list[str]
    warnings: list[str]
    missing_evidence: list[str]
    allowed_conclusions: list[str]
    prohibited_conclusions: list[str]
    context_quality: str
    synthesis_allowed: bool = False
    rag_approval_summary: dict[str, object] | None = None
    evidence_origin_labels: list[str] = []
    # FinalEvidenceGate debug projection (refs/counts/permissions). Kept
    # consistent with the final RunContract; see graph_node_context_finalize.
    final_evidence_gate: dict[str, object] | None = None


class ContextSufficiencyEnvelope(BaseModel):
    status: str
    answer_mode: str | None = None
    synthesis_allowed: bool
    synthesis_readiness: bool = False
    reasons: list[str]
    missing_evidence: list[str]
    human_review: HumanReviewEnvelope | None = None


class RoutePlanShadowEnvelope(BaseModel):
    enabled: bool
    mode: str
    preflight_status: str | None = None
    route_status: str | None = None
    primary_skill: str | None = None
    pattern_id: str | None = None
    candidate_available: bool = False
    candidate_reason: str | None = None
    validation_result: dict[str, object] | None = None
    validation_findings: list[str] = []
    blocking_findings: list[str] = []
    warnings: list[str] = []
    missing_slots: list[str] = []
    normalized_plan_available: bool = False
    execution_authorized: bool = False
    llm_called: bool = False
    llm_role: str | None = None
    llm_model_family: str | None = None
    llm_candidate_route_plan_available: bool = False
    llm_candidate_dropped_reasons: list[str] = []
    deterministic_route_plan_wins: bool = True
    disagreements: list[dict[str, object]] = []
    mcp_called: bool = False
    spl_generated: bool = False
    spl_executed: bool = False
    model_role: str
    reasoning_model_used: bool = False
    template_match_attempted: bool = False
    template_match_skip_reason: str | None = None
    template_match_shadow_status: str | None = None
    matched_template_id: str | None = None
    template_match_score: float | None = None
    template_match_reasons: list[str] = []
    template_mismatch_reasons: list[str] = []
    candidate_template_ids: list[str] = []
    template_production_executable: bool = False
    template_sample_only: bool = False
    template_validator_profile: str | None = None
    rendered_spl_available: bool = False
    rendered_spl_validator_approved: bool = False
    rendered_spl_execution_eligible: bool = False
    rendered_spl_sha256: str | None = None
    evidence_output_contract: dict[str, object] | None = None
    coe_synthetic_fixture: bool = True
    captured_live_run: bool = False
    production_execution: bool = False
    analyst_summary_shadow_available: bool = False
    analyst_summary_shadow_text: str | None = None
    analyst_summary_trace_bullets: list[str] = []
    analyst_summary_dropped_reasons: list[str] = []
    analyst_summary_shadow_source: str | None = None
    analyst_summary_narration_llm_called: bool = False
    intent_operation_bridge: dict[str, object] | None = None
    output_artifacts: dict[str, object] | None = None
    route_authority_compare: dict[str, object] | None = None
    question_runtime_map: dict[str, object] | None = None
    precondition_evaluation: dict[str, object] | None = None
    supporter_trace: dict[str, object] | None = None
    ood_llm_route_plan_lab: dict[str, object] | None = None
    use_case_registry_bridge: dict[str, object] | None = None
    routing_skill_resolution: dict[str, object] | None = None
    operation_audit: dict[str, object] | None = None


class AnalystResponseEnvelope(BaseModel):
    scenario_label: str | None = None
    severity_label: str | None = None
    severity_confidence: str | None = None
    severity_rationale: str | None = None
    severity_safety_note: str | None = None
    finding_title: str | None = None
    one_sentence_finding: str | None = None
    initial_assessment: list[str] = []
    status_badge: str | None = None
    splunk_status_line: str | None = None
    splunk_results_table: list[dict[str, object]] = []
    mitre_mappings: list[dict[str, object]] = []
    not_claimed: list[dict[str, object]] = []
    reference_facts: list[dict[str, object]] = []
    retrieved_playbook: dict[str, object] | None = None
    sop_guidance: dict[str, object] | None = None
    foundation_sec_analysis: str | None = None
    recommended_actions: list[str] = []
    interactive_actions: list[dict[str, object]] = []
    spl_code: str | None = None
    spl_draft_preview: dict[str, object] | None = None
    spl_unbound_constraints: list[dict[str, object]] = []
    draft_spl_code: str | None = None
    llm_spl_candidate: LlmSplCandidateEnvelope | None = None
    executed_spl: str | None = None
    execution_status: str | None = None
    response_profile: str | None = None
    key_fields: list[str] = []
    escalation_criteria: list[str] = []
    closure_conditions: list[str] = []
    review_notice: str | None = None
    evidence_summary: str | None = None
    execution_status_label: str | None = None
    spl_status: str | None = None
    hil_status: str | None = None
    missing_evidence: list[str] = []
    analyst_checklist: list[str] = []
    investigation_steps: list[str] = []
    unsupported_claims_avoid: list[str] = []
    mitre_status_summary: dict[str, list[str]] = {}
    direct_answer_summary: str | None = None
    limitations: list[str] = []
    required_evidence: list[str] = []
    spl_status_detail: dict[str, object] | None = None
    environment_hygiene: dict[str, object] | None = None
    section_order: list[str] = []
    render_sections: dict[str, bool] = {}


class FoundationSecCapturedOutput(BaseModel):
    model_role: str | None = None
    model_family: str | None = None
    model_name: str | None = None
    captured_prompt_type: str | None = None
    captured_summary: str | None = None
    useful_contribution: list[str] = []
    observed_limitations: list[str] = []


class FoundationSecGovernanceOverride(BaseModel):
    model_suggested: str | None = None
    vai_soc_governed: str | None = None
    reason: str | None = None
    rule: str | None = None


class FoundationSecGovernedAnalysis(BaseModel):
    model_signal: str | None = None
    vai_soc_decision: str | None = None
    evidence_used: list[str] = []
    evidence_refs: list[str] = []
    missing_evidence: list[str] = []
    governance_overrides: list[FoundationSecGovernanceOverride] = []
    guardrail_notes: list[str] = []


class FoundationSecGovernance(BaseModel):
    fixture_type: str | None = None
    live_llm_called: bool = False
    final_answer_source: str | None = None
    display_mode: str | None = None
    model_family: str | None = None
    captured_outputs: list[FoundationSecCapturedOutput] = []
    governed_analysis: FoundationSecGovernedAnalysis | None = None


class SessionContextStatusEnvelope(BaseModel):
    session_id: str
    used_previous_context: bool = False
    context_source_trace_id: str | None = None
    staleness: str = "missing"
    used_fields: list[str] = []
    ignored_fields: list[str] = []
    clarification_required: bool = False


class PlanningOutcomeSummary(BaseModel):
    """Analyst-safe canonical planning summary (G1) — no internal plans or secrets."""

    status: PlanningOutcomeStatus
    user_message: str
    recovery_hint: str
    category: PlanningOutcomeCategory | None = None

    @field_validator("user_message", "recovery_hint", mode="before")
    @classmethod
    def _strip_bounded_text(cls, value: object) -> str:
        return str(value or "").strip()[:500]


class PlaceholderResponse(BaseModel):
    trace_id: str
    turn_id: str | None = None
    message: str
    note: str
    demo_mode: bool = False
    evidence_origin: str | None = None
    answer_readiness: str | None = None
    no_live_customer_data: bool = False
    demo_badge: str | None = None
    environment_mode: str | None = None
    mcp_execution_mode: str | None = None
    saia_available: bool | None = None
    rag_available: bool | None = None
    fallback_active: bool | None = None
    response_packaging_status: str | None = None
    analyst_summary: str | None = None
    answer_mode: str | None = None
    response_mode: str | None = None
    synthesis_mode: str | None = None
    trace_explanation: list[str] = []
    user_query: str | None = None
    selected_skill: str | None = None
    primary_operation: str | None = None
    coverage_id: str | None = None
    route_authority: dict[str, object] | None = None
    legacy_intent_authority: bool | None = None
    routing_skill_resolution: dict[str, object] | None = None
    semantic_intent: dict[str, object] | None = None
    operation_audit: dict[str, object] | None = None
    tool_plan: list[str] | None = None
    confidence: float | None = None
    routing_mode: str | None = None
    disagreement: bool | None = None
    disagreement_reason: str | None = None
    query_understanding: QueryUnderstandingResult | None = None
    selected_use_case: UseCaseSelection | None = None
    selected_skill_chain: SkillChain | None = None
    skill_selection: SkillSelectionResult | None = None
    skill_contribution: dict[str, object] | None = None
    workflow_plan: WorkflowPlan | None = None
    candidate_spl: CandidateSplEnvelope | None = None
    spl_validation: SplValidationEnvelope | None = None
    spl_draft_preview: SplDraftPreviewEnvelope | None = None
    llm_spl_candidate: LlmSplCandidateEnvelope | None = None
    execution: ExecutionEnvelope | None = None
    human_review: HumanReviewEnvelope | None = None
    source_evidence: list[SourceEvidenceEnvelope] = []
    structured_context: StructuredContextPackage | None = None
    context_sufficiency: ContextSufficiencyEnvelope | None = None
    route_plan_shadow: RoutePlanShadowEnvelope | None = None
    analyst_response: AnalystResponseEnvelope | None = None
    environment_hygiene: dict[str, object] | None = None
    foundation_sec_governance: FoundationSecGovernance | None = None
    spl_template: dict[str, object] | None = None
    evidence_plan: dict[str, object] | None = None
    planning_decision: dict[str, object] | None = None
    llm_intent_advisory: dict[str, object] | None = None
    route_adjudication: dict[str, object] | None = None
    llm_plan_validation: dict[str, object] | None = None
    tool_plan_structured: dict[str, object] | None = None
    query_to_intent: dict[str, object] | None = None
    control_plane_trace: dict[str, object] | None = None
    answer_contract: dict[str, object] | None = None
    run_contract: dict[str, object] | None = None
    canonical_facts: dict[str, object] | None = None
    routing_contract: dict[str, object] | None = None
    blocked_action_state: dict[str, object] | None = None
    # WS3 T3.1 — deterministic read-model scorecard (never authority).
    answer_scorecard: dict[str, object] | None = None
    # WS3 T3.2 — consolidated LLM narration usage visibility (read-model).
    narration_visibility: dict[str, object] | None = None
    final_answer_validation: dict[str, object] | None = None
    mitre_decision: dict[str, object] | None = None
    mitre_mappings: list[MitreMappingDecision] | None = None
    severity_decision: SeverityDecision | None = None
    investigation_lineage: InvestigationLineage | None = None
    synthesis_status: SynthesisStatus | None = None
    answer_guard: AnswerGuardStatus | None = None
    action_capability: ActionCapability | None = None
    proposed_actions: list[dict[str, object]] | None = None
    experience_center_governance: ExperienceCenterGovernance | None = None
    governance_trace: GovernanceTrace | None = None
    # Batch 4 — additive visibility (control-plane gated; None when flag off).
    mitre_evidence_status: dict[str, str] | None = None
    spl_template_status: str | None = None
    node_trace: list[dict[str, object]] | None = None
    answer_guard_status: str | None = None
    final_answer_safety_status: str | None = None
    session_context_status: SessionContextStatusEnvelope | None = None
    # Experience Center capture/provenance surfacing (plan 2026-06-24, Tracks B2/B6).
    # Demo-time posture is always no-live-call; ec_provenance badges the captured source.
    live_mcp_called: bool | None = None
    ec_answer_source: str | None = None
    ec_provenance: dict[str, object] | None = None
    ec_stage_latencies: list[dict[str, object]] | None = None
    # G1 — safe canonical planning summary for analyst UI (no internal plans).
    planning_outcome: PlanningOutcomeSummary | None = None

    @model_validator(mode="after")
    def derive_blocked_action_state(self) -> "PlaceholderResponse":
        state = self.blocked_action_state or _derive_blocked_action_state(
            human_review=self.human_review,
            execution=self.execution,
            run_contract=self.run_contract,
            query_to_intent=self.query_to_intent,
        )
        if state is None:
            return self
        self.blocked_action_state = state
        trace = dict(self.control_plane_trace or {})
        trace["blocked_action_state"] = state
        self.control_plane_trace = trace
        return self


def _model_dump(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        payload = dump()
        if isinstance(payload, dict):
            return payload
    return {}


def _nested_dict(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _derive_blocked_action_state(
    *,
    human_review: object,
    execution: object,
    run_contract: dict[str, object] | None,
    query_to_intent: dict[str, object] | None,
) -> dict[str, object] | None:
    review = _model_dump(human_review)
    execution_payload = _model_dump(execution)
    contract = run_contract if isinstance(run_contract, dict) else {}
    intent = query_to_intent if isinstance(query_to_intent, dict) else {}
    signals = _nested_dict(intent, "query_signals")

    action_shaped = bool(
        signals.get("action_or_containment_shaped")
        or signals.get("block_or_contain")
        or signals.get("disable_or_enforce")
    )
    review_reason = str(review.get("reason") or "")
    if not action_shaped and review_reason != "unsafe_action_blocked":
        return None

    execution_status = str(
        execution_payload.get("status")
        or contract.get("execution_status")
        or ""
    )
    execution_block_reason = str(execution_payload.get("block_reason") or "")
    if review_reason == "unsafe_action_blocked":
        block_class = "policy_governance"
        banner = "Containment/enforcement blocked by governance. No action was performed."
    elif bool(contract.get("mcp_needed_for_live_answer")) and not bool(contract.get("mcp_allowed")):
        block_class = "mcp_disabled_or_unavailable"
        banner = "Live action path unavailable. MCP execution is disabled or not allowed."
    elif bool(contract.get("effective_hil_required")):
        block_class = "missing_required_evidence_or_slots"
        banner = "Action blocked pending required evidence, slots, or human review."
    elif execution_status in {"blocked", "requires_human_review"}:
        block_class = "execution_gate"
        banner = "Action blocked by execution gate."
    else:
        return None

    routing = _nested_dict(contract, "routing")
    safe_message = str(review.get("safe_message_for_user") or banner)
    return {
        "visible": True,
        "status": "blocked",
        "action_requested": "containment_or_enforcement"
        if signals.get("block_or_contain") or signals.get("disable_or_enforce")
        else "execution",
        "block_class": block_class,
        "reason": review_reason or execution_block_reason or block_class,
        "banner": banner,
        "safe_message": safe_message,
        "allowed_actions": _str_list(review.get("allowed_actions")),
        "execution_authorized": bool(contract.get("execution_authorized")),
        "mcp_allowed": bool(contract.get("mcp_allowed")),
        "effective_hil_required": bool(contract.get("effective_hil_required")),
        "route_preserved": True,
        "canonical_skill": routing.get("canonical_skill"),
        "canonical_sources": [
            "run_contract",
            "human_review",
            "execution",
            "query_signals",
        ],
    }
