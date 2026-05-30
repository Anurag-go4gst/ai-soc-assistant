from pydantic import BaseModel

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
    tool_outputs_summary: list[dict[str, object]]
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


class ContextSufficiencyEnvelope(BaseModel):
    status: str
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


class AnalystResponseEnvelope(BaseModel):
    scenario_label: str | None = None
    severity_label: str | None = None
    finding_title: str | None = None
    one_sentence_finding: str | None = None
    status_badge: str | None = None
    splunk_status_line: str | None = None
    splunk_results_table: list[dict[str, object]] = []
    mitre_mappings: list[dict[str, object]] = []
    retrieved_playbook: dict[str, object] | None = None
    sop_guidance: dict[str, object] | None = None
    foundation_sec_analysis: str | None = None
    recommended_actions: list[str] = []
    spl_code: str | None = None
    key_fields: list[str] = []
    escalation_criteria: list[str] = []
    closure_conditions: list[str] = []
    review_notice: str | None = None


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


class PlaceholderResponse(BaseModel):
    trace_id: str
    message: str
    note: str
    demo_mode: bool = False
    evidence_origin: str | None = None
    no_live_customer_data: bool = False
    demo_badge: str | None = None
    environment_mode: str | None = None
    mcp_execution_mode: str | None = None
    saia_available: bool | None = None
    rag_available: bool | None = None
    fallback_active: bool | None = None
    analyst_summary: str | None = None
    trace_explanation: list[str] = []
    user_query: str | None = None
    selected_skill: str | None = None
    tool_plan: list[str] | None = None
    confidence: float | None = None
    routing_mode: str | None = None
    disagreement: bool | None = None
    disagreement_reason: str | None = None
    query_understanding: QueryUnderstandingResult | None = None
    selected_use_case: UseCaseSelection | None = None
    selected_skill_chain: SkillChain | None = None
    skill_selection: SkillSelectionResult | None = None
    workflow_plan: WorkflowPlan | None = None
    candidate_spl: CandidateSplEnvelope | None = None
    spl_validation: SplValidationEnvelope | None = None
    execution: ExecutionEnvelope | None = None
    human_review: HumanReviewEnvelope | None = None
    source_evidence: list[SourceEvidenceEnvelope] = []
    structured_context: StructuredContextPackage | None = None
    context_sufficiency: ContextSufficiencyEnvelope | None = None
    route_plan_shadow: RoutePlanShadowEnvelope | None = None
    analyst_response: AnalystResponseEnvelope | None = None
    foundation_sec_governance: FoundationSecGovernance | None = None
    spl_template: dict[str, object] | None = None
    mitre_mappings: list[MitreMappingDecision] | None = None
    severity_decision: SeverityDecision | None = None
    investigation_lineage: InvestigationLineage | None = None
    synthesis_status: SynthesisStatus | None = None
    answer_guard: AnswerGuardStatus | None = None
    action_capability: ActionCapability | None = None
    experience_center_governance: ExperienceCenterGovernance | None = None
    governance_trace: GovernanceTrace | None = None
