export interface HealthResponse {
  status: string;
  service: string;
}

export interface AuthResponse {
  authenticated: boolean;
  username?: string | null;
  role?: string | null;
}

export interface SessionContextStatusEnvelope {
  session_id: string;
  used_previous_context?: boolean;
  context_source_trace_id?: string | null;
  staleness?: string;
  used_fields?: string[];
  ignored_fields?: string[];
  clarification_required?: boolean;
}

export interface PlaceholderResponse {
  turn_id?: string | null;
  trace_id: string;
  message: string;
  note: string;
  demo_mode?: boolean;
  evidence_origin?: string | null;
  answer_readiness?: string | null;
  no_live_customer_data?: boolean;
  demo_badge?: string | null;
  environment_mode?: string | null;
  mcp_execution_mode?: string | null;
  saia_available?: boolean | null;
  rag_available?: boolean | null;
  fallback_active?: boolean | null;
  response_packaging_status?: 'answer_ready' | 'packaging' | 'deterministic_fallback' | 'llm_skipped' | 'llm_timeout' | 'blocked_review_required' | string | null;
  analyst_summary?: string | null;
  response_mode?: string | null;
  synthesis_mode?: string | null;
  trace_explanation?: string[];
  user_query?: string | null;
  selected_skill?: string | null;
  primary_operation?: string | null;
  coverage_id?: string | null;
  route_authority?: Record<string, unknown> | null;
  legacy_intent_authority?: boolean | null;
  routing_skill_resolution?: Record<string, unknown> | null;
  semantic_intent?: Record<string, unknown> | null;
  operation_audit?: Record<string, unknown> | null;
  tool_plan?: string[] | null;
  confidence?: number | null;
  routing_mode?: string | null;
  disagreement?: boolean | null;
  disagreement_reason?: string | null;
  routing_trace?: RoutingTraceEnvelope | null;
  query_understanding?: QueryUnderstandingResult | null;
  selected_use_case?: UseCaseSelection | null;
  selected_skill_chain?: SkillChain | null;
  skill_selection?: SkillSelectionResult | null;
  workflow_plan?: WorkflowPlan | null;
  candidate_spl?: CandidateSplEnvelope | null;
  spl_validation?: SplValidationEnvelope | null;
  spl_draft_preview?: SplDraftPreviewEnvelope | null;
  llm_spl_candidate?: LlmSplCandidateEnvelope | null;
  execution?: ExecutionEnvelope | null;
  human_review?: HumanReviewEnvelope | null;
  source_evidence?: SourceEvidenceEnvelope[];
  structured_context?: StructuredContextPackage | null;
  context_sufficiency?: ContextSufficiencyEnvelope | null;
  route_plan_shadow?: RoutePlanShadowEnvelope | null;
  analyst_response?: AnalystResponseEnvelope | null;
  foundation_sec_governance?: FoundationSecGovernance | null;
  spl_template?: Record<string, unknown> | null;
  evidence_plan?: Record<string, unknown> | null;
  route_adjudication?: Record<string, unknown> | null;
  llm_plan_validation?: Record<string, unknown> | null;
  query_to_intent?: Record<string, unknown> | null;
  control_plane_trace?: Record<string, unknown> | null;
  answer_contract?: Record<string, unknown> | null;
  final_answer_validation?: Record<string, unknown> | null;
  mitre_decision?: Record<string, unknown> | null;
  mitre_mappings?: MitreMappingDecision[] | null;
  severity_decision?: SeverityDecision | null;
  investigation_lineage?: InvestigationLineage | null;
  synthesis_status?: SynthesisStatus | null;
  answer_guard?: AnswerGuardStatus | null;
  action_capability?: ActionCapability | null;
  experience_center_governance?: ExperienceCenterGovernance | null;
  governance_trace?: ExperienceCenterGovernance | null;
  mitre_evidence_status?: Record<string, string> | null;
  spl_template_status?: string | null;
  node_trace?: Array<Record<string, unknown>> | null;
  answer_guard_status?: string | null;
  final_answer_safety_status?: string | null;
  session_context_status?: SessionContextStatusEnvelope | null;
}

export type ChatAnswerFeedbackRating = 'up' | 'down' | 'neutral';

export interface ChatAnswerFeedbackRequest {
  turn_id: string;
  trace_id?: string | null;
  rating: ChatAnswerFeedbackRating;
  remark?: string | null;
  category?: string | null;
}

export interface ChatAnswerFeedbackResponse {
  feedback_id?: string | null;
  turn_id: string;
  trace_id?: string | null;
  rating: ChatAnswerFeedbackRating;
  remark?: string | null;
  category?: string | null;
  review_status?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  quality_status?: string | null;
}

export interface QualityFlaggedTurn {
  turn_id: string;
  trace_id?: string | null;
  created_at?: string | null;
  user_query?: string | null;
  final_message?: string | null;
  analyst_summary?: string | null;
  selected_skill?: string | null;
  selected_use_case_id?: string | null;
  answer_mode?: string | null;
  response_mode?: string | null;
  quality_status?: string | null;
  golden_candidate?: boolean | null;
  latest_feedback?: ChatAnswerFeedbackResponse | null;
  feedback?: ChatAnswerFeedbackResponse[] | null;
}

export interface QualityFlaggedTurnsResponse {
  turns: QualityFlaggedTurn[];
  count: number;
}

export interface McpEnvelopeGovernancePanel {
  available: boolean;
  origin?: string | null;
  schema_confirmed?: boolean | null;
  schema_confirmed_reason?: string | null;
  status?: string | null;
  row_count?: number | null;
  total_row_count?: number | null;
  truncated?: boolean | null;
  truncation_reason?: string | null;
  fields?: string[];
  preview_rows_count?: number | null;
  warnings?: string[];
  provenance?: string | null;
  executed_spl?: string | null;
}

export interface SeverityGovernancePanel {
  severity_label: string;
  why_severity_title: string;
  why_severity: string[];
  why_not_higher_title: string;
  why_not_higher: string[];
  priority_note?: string | null;
}

export interface PipelineStageStatus {
  stage_id: string;
  label: string;
  status: string;
}

export interface SkillsOperationsGovernancePanel {
  intent_skill: string;
  legacy_router_skill: string;
  runtime_operation?: string | null;
  runtime_operation_note: string;
  pipeline_stages: PipelineStageStatus[];
}

export interface CompletionStatusGovernancePanel {
  completed: string[];
  gated_wip: string[];
}

export interface ExperienceCenterGovernance {
  mcp_envelope?: McpEnvelopeGovernancePanel | null;
  severity?: SeverityGovernancePanel | null;
  skills_operations: SkillsOperationsGovernancePanel;
  completion_status: CompletionStatusGovernancePanel;
}

export type RequestedOutputType =
  | 'investigation'
  | 'spl'
  | 'sop'
  | 'mitre_mapping'
  | 'summary'
  | 'note'
  | 'action_plan'
  | 'clarification';

export type OutputTemplate =
  | 'investigation_answer'
  | 'spl_response'
  | 'sop_response'
  | 'mitre_mapping_response'
  | 'clarification_response'
  | 'note_response';

export interface QueryEntities {
  asset: string[];
  host: string[];
  user: string[];
  source_ip: string[];
  destination_ip: string[];
  time_window?: string | null;
  index: string[];
  sourcetype: string[];
  alert_id: string[];
  event_type: string[];
}

export interface QueryUnderstandingResult {
  raw_query: string;
  normalized_query: string;
  primary_intent: string;
  secondary_intents: string[];
  requested_output_type: RequestedOutputType;
  output_template: OutputTemplate;
  entities: QueryEntities;
  ambiguity_flags: string[];
  confidence: number;
  clarification_needed: boolean;
  clarification_question?: string | null;
  mapped_use_case_ids: string[];
}

export interface UseCaseSelection {
  use_case_id: string;
  display_name: string;
  category: string;
  primary_skill: string;
  confidence: number;
  matched_patterns: string[];
  default_spl_template?: string | null;
  output_template: string;
  required_sources: string[];
  optional_sources: string[];
  action_capability_tier: number;
}

export interface SkillChain {
  chain_id: string;
  selected_skill: string;
  stages: string[];
  routable_skill: string;
  pipeline_stages: string[];
  alternatives: string[];
  selection_reason: string;
}

export interface SkillSelectionResult {
  selected_skill: string;
  selected_use_case_id?: string | null;
  selected_chain: SkillChain;
  decision_source: string;
  selection_status: string;
  rule_based_skill: string;
  registry_primary_skill?: string | null;
  llm_assisted_skill?: string | null;
  alternatives: string[];
  policy_notes: string[];
}

export interface MitreMappingDecision {
  technique_id: string;
  name: string;
  tactic: string;
  status: 'confirmed' | 'supported' | 'candidate' | 'requires_validation' | string;
  why: string;
  evidence_requirements: string[];
  source_refs: string[];
  recommended_pivots: string[];
}

export interface SeverityDecision {
  use_case_id?: string | null;
  severity_label: string;
  matched_rules: string[];
  why_not_higher: string[];
  missing_evidence: string[];
  source_refs: string[];
  recommended_priority: string;
  allowed_action_tier: number;
}

export interface LineageStage {
  stage_id: string;
  status: string;
  visible_label: string;
  explanation: string;
  technical_output: Record<string, unknown>;
  produced_answer_sections: string[];
  current_mode_source: 'live' | 'scenario' | 'config' | 'derived' | 'planned' | string;
  production_equivalent: string;
}

export interface InvestigationLineage {
  lineage_id: string;
  stages: LineageStage[];
  summary: string;
}

export interface RoutePlanShadowEnvelope {
  enabled: boolean;
  mode: string;
  analyst_summary_shadow_available?: boolean;
  analyst_summary_shadow_text?: string | null;
  analyst_summary_trace_bullets?: string[];
  analyst_summary_dropped_reasons?: string[];
  analyst_summary_shadow_source?: string | null;
  analyst_summary_narration_llm_called?: boolean;
  execution_authorized?: boolean;
  spl_executed?: boolean;
  mcp_called?: boolean;
  [key: string]: unknown;
}

export interface SynthesisStatus {
  enabled: boolean;
  status: string;
  provider?: string | null;
  model?: string | null;
  reason: string;
  allowed_inputs: string[];
}

export interface AnswerGuardStatus {
  enabled: boolean;
  guard_status: string;
  passed_checks: string[];
  failed_checks: string[];
  blocked_reason?: string | null;
  analyst_review_required: boolean;
  reason: string;
}

export interface ActionCapability {
  current_tier: number;
  tier_label: string;
  allowed_actions: string[];
  unavailable_actions: string[];
  hil_required: boolean;
  audit_required: boolean;
  reason: string;
}

export interface SplDraftPreviewEnvelope {
  draft_spl: string;
  draft_status: string;
  draft_source: string;
  detection_family: string;
  assumptions: string[];
  required_source_fields: string[];
  source_profile_missing: boolean;
  governed_template_missing: boolean;
  validator_status: string;
  review_required: boolean;
  execution_enabled: boolean;
  warning: string;
  not_catalog_approved_notice: string;
}

export interface LlmSplCandidateEnvelope {
  llm_spl_candidate: string;
  llm_spl_candidate_status: string;
  llm_spl_confidence_score: number;
  llm_spl_confidence_label: string;
  detection_family?: string | null;
  quality_status?: string | null;
  validator_status?: string | null;
  quality_findings?: Array<Record<string, unknown>>;
  validation_findings?: string[];
  assumptions?: string[];
  required_fields?: string[];
  missing_details?: string[];
  clarifying_questions?: string[];
  validation_notes?: string[];
  soc_std_rules_applied?: string[];
  risk_notes?: string[];
  execution_eligible?: boolean;
  governed?: boolean;
  catalog_approved?: boolean;
  execution_enabled?: boolean;
  review_required?: boolean;
  provider?: string | null;
  model?: string | null;
  latency_ms?: number | null;
}

export interface AnalystResponseEnvelope {
  scenario_label?: string | null;
  severity_label?: string | null;
  severity_confidence?: string | null;
  severity_rationale?: string | null;
  severity_safety_note?: string | null;
  finding_title?: string | null;
  one_sentence_finding?: string | null;
  status_badge?: string | null;
  splunk_status_line?: string | null;
  splunk_results_table?: Record<string, unknown>[];
  mitre_mappings?: Record<string, unknown>[];
  not_claimed?: Record<string, unknown>[];
  retrieved_playbook?: Record<string, unknown> | null;
  sop_guidance?: Record<string, unknown> | null;
  foundation_sec_analysis?: string | null;
  recommended_actions?: string[];
  spl_code?: string | null;
  draft_spl_code?: string | null;
  spl_draft_preview?: SplDraftPreviewEnvelope | null;
  llm_spl_candidate?: LlmSplCandidateEnvelope | null;
  executed_spl?: string | null;
  execution_status?: string | null;
  response_profile?: string | null;
  key_fields?: string[];
  escalation_criteria?: string[];
  closure_conditions?: string[];
  review_notice?: string | null;
  evidence_summary?: string | null;
  execution_status_label?: string | null;
  spl_status?: string | null;
  hil_status?: string | null;
  missing_evidence?: string[];
  analyst_checklist?: string[];
  investigation_steps?: string[];
  unsupported_claims_avoid?: string[];
  mitre_status_summary?: Record<string, string[]>;
  direct_answer_summary?: string | null;
  limitations?: string[];
  required_evidence?: string[];
  spl_status_detail?: {
    template_status?: string;
    generation_status?: string;
    generation?: string;
    review_required?: boolean;
    block_reason?: string | null;
    reason?: string;
    reason_display?: string;
    required_fields?: string[];
    template_id?: string;
  } | null;
  section_order?: string[];
  render_sections?: Record<string, boolean>;
}

export interface FoundationSecCapturedOutput {
  model_role?: string | null;
  model_family?: string | null;
  model_name?: string | null;
  captured_prompt_type?: string | null;
  captured_summary?: string | null;
  useful_contribution?: string[];
  observed_limitations?: string[];
}

export interface FoundationSecGovernanceOverride {
  model_suggested?: string | null;
  vai_soc_governed?: string | null;
  reason?: string | null;
  rule?: string | null;
}

export interface FoundationSecGovernedAnalysis {
  model_signal?: string | null;
  vai_soc_decision?: string | null;
  evidence_used?: string[];
  evidence_refs?: string[];
  missing_evidence?: string[];
  governance_overrides?: FoundationSecGovernanceOverride[];
  guardrail_notes?: string[];
}

export interface FoundationSecGovernance {
  fixture_type?: string | null;
  live_llm_called?: boolean;
  final_answer_source?: string | null;
  display_mode?: string | null;
  model_family?: string | null;
  captured_outputs?: FoundationSecCapturedOutput[];
  governed_analysis?: FoundationSecGovernedAnalysis | null;
}

export interface DemoScenarioSummary {
  scenario_id: string;
  label: string;
  category: 'Investigate' | 'Knowledge / SOP' | 'Generate SPL' | 'MITRE Mapping' | 'Air-gapped Mode' | string;
  query: string;
  environment_mode: string;
  demo_badge: string;
  expected_skill: string;
  expected_sources: string[];
  expected_sufficiency_mode: string;
  mcp_execution_mode: 'disabled' | 'mock_success' | 'not_required' | string;
  saia_available: boolean;
  rag_available: boolean;
  evidence_origin: string;
  no_live_customer_data: boolean;
}

export interface DemoScenariosResponse {
  demo_mode: boolean;
  evidence_origin: string;
  no_live_customer_data: boolean;
  scenarios: DemoScenarioSummary[];
  count: number;
}

export interface RoutingTraceEnvelope {
  deterministic_skill?: string | null;
  deterministic_confidence?: number | null;
  deterministic_tool_plan?: string[] | null;
  llm_shadow_skill?: string | null;
  llm_shadow_confidence?: number | null;
  llm_shadow_tool_plan?: string[] | null;
  comparison_status?: 'agree' | 'disagree' | string | null;
  comparison_reason?: string | null;
}

export interface WorkflowStep {
  order: number;
  name: string;
  status: string;
  required_connectors: string[];
  safety_gates: string[];
}

export interface WorkflowPlan {
  trace_id: string;
  skill: string;
  tool_plan: string[];
  status: string;
  execution_enabled: boolean;
  steps: WorkflowStep[];
  required_connectors: string[];
  safety_gates: string[];
  required_sources?: string[];
  available_sources?: string[];
  missing_sources?: string[];
  message: string;
}

export interface CandidateSplEnvelope {
  trace_id: string;
  skill: string;
  user_query: string;
  candidate_spl: string;
  generation_mode: string;
  confidence: number;
  assumptions: string[];
  warnings: string[];
  selected_candidate_spl_provider?: string | null;
  reason?: string | null;
  saia_available?: boolean | null;
  saia_usable?: boolean | null;
  fallback_required?: boolean | null;
  capability_profile?: Record<string, unknown> | null;
  spl_template_status?: string | null;
}

export interface SplValidationEnvelope {
  approved: boolean;
  normalized_spl?: string | null;
  reject_reasons: string[];
  warnings: string[];
  enforced_limits: Record<string, unknown>;
  policy_version: string;
  selected_candidate_spl_provider?: string | null;
  candidate_provider_reason?: string | null;
  saia_available?: boolean | null;
  fallback_required?: boolean | null;
  spl_explanation_provider?: string | null;
  spl_optimization_provider?: string | null;
  spl_guidance_provider?: string | null;
  optimization_applied?: boolean | null;
  capability_profile?: Record<string, unknown> | null;
  spl_template_status?: string | null;
}

export interface ExecutionEnvelope {
  status: 'blocked' | 'requires_human_review' | 'skipped' | 'executed' | 'failed' | string;
  execution_intent: string;
  selected_mcp_server?: string | null;
  selected_mcp_tool?: string | null;
  tool_selection_status: 'selected' | 'blocked' | 'unavailable' | 'requires_human_review' | string;
  tool_selection_reason: string;
  executed_spl?: string | null;
  result_count: number;
  results_preview: Record<string, unknown>[];
  block_reason?: string | null;
  duration_ms: number;
  evidence_source?: string | null;
  execution_status_label?: string | null;
  saved_search_name?: string | null;
}

export interface HumanReviewEnvelope {
  required: boolean;
  review_type: string;
  reason: string;
  reviewer_role: 'analyst' | 'soc_lead' | 'platform_admin' | 'security_admin' | string;
  allowed_actions: string[];
  safe_message_for_user: string;
  sop_reference?: string | null;
  sop_excerpt?: string | null;
  sop_action_hint?: string | null;
}

export interface SourceEvidenceEnvelope {
  evidence_id: string;
  trace_id: string;
  source_type: string;
  source_name: string;
  tool_name?: string | null;
  collection_status: 'collected' | 'blocked' | 'failed' | 'skipped' | 'requires_human_review' | 'no_match' | 'ambiguous' | string;
  query_or_request_summary?: string | null;
  executed_spl?: string | null;
  result_count: number;
  fields_returned: string[];
  preview_rows: Record<string, unknown>[];
  raw_result_hash?: string | null;
  raw_result_stored: boolean;
  time_range?: string | null;
  warnings: string[];
  sensitivity_flags: string[];
  tool_category?: string | null;
  provider_used?: string | null;
  saved_search_name?: string | null;
  output_type?: string | null;
  provenance?: string | null;
  created_at: string;
}

export interface StructuredFact {
  fact_id: string;
  statement: string;
  source_refs: string[];
  derivation: string;
  confidence?: number | null;
}

export interface StructuredContextPackage {
  trace_id: string;
  query: string;
  selected_skill: string;
  source_evidence_refs: string[];
  structured_facts: StructuredFact[];
  entity_summary: Record<string, unknown>;
  metrics: Record<string, unknown>;
  timeline_candidates: Record<string, unknown>[];
  mitre_candidates: Record<string, unknown>[];
  tool_outputs_summary: Record<string, unknown>[];
  capability_profile_ref?: string | null;
  spl_generation_provider?: string | null;
  spl_explanation_provider?: string | null;
  spl_optimization_provider?: string | null;
  spl_guidance_provider?: string | null;
  fallback_mode?: boolean;
  execution_provider?: string | null;
  source_refs?: string[];
  policy_context_refs: string[];
  sop_action_hints?: Record<string, unknown>[];
  answer_constraints?: string[];
  mitre_grounding_refs?: string[];
  splunk_context_refs?: string[];
  tool_policy_refs?: string[];
  environment_grounding_refs?: string[];
  knowledge_ambiguity?: string[];
  validation_warnings?: string[];
  assumptions: string[];
  warnings: string[];
  missing_evidence: string[];
  allowed_conclusions: string[];
  prohibited_conclusions: string[];
  context_quality: 'sufficient' | 'partial' | 'insufficient' | 'blocked' | string;
  synthesis_allowed: boolean;
}

export type ContextSufficiencyMode =
  | 'full_answer'
  | 'partial_answer'
  | 'analyst_review_required'
  | 'spl_review_only'
  | 'knowledge_only_answer'
  | 'blocked_by_policy'
  | 'insufficient_evidence';

export interface ContextSufficiencyEnvelope {
  status: ContextSufficiencyMode | string;
  synthesis_allowed: boolean;
  synthesis_readiness: boolean;
  reasons: string[];
  missing_evidence: string[];
  human_review?: HumanReviewEnvelope | null;
}

export interface LlmGovernanceProvider {
  provider_id: string;
  provider_type: string;
  base_url_configured: boolean;
  api_key_configured: boolean;
  default_model_configured: boolean;
  model_name?: string | null;
  max_context_tokens?: number;
  max_output_tokens?: number;
  timeout_seconds?: number;
  temperature?: number;
  top_p?: number;
  supports_json_mode?: boolean;
  supports_model_listing?: boolean;
  deployment_mode?: string;
  policy_allowed?: boolean;
  enabled: boolean;
}

export interface LlmGovernanceRoleMapping {
  role: string;
  provider: string | null;
  model: string | null;
  enabled: boolean;
  preferred_provider?: string;
  preferred_model?: string;
  mode?: string;
  output?: string;
  authority?: string;
  validator_required?: boolean | string;
  strict_json?: boolean;
  temperature?: number;
  max_input_tokens?: number;
  max_output_tokens?: number;
  execution_eligible?: boolean;
  fallback_used?: boolean;
  degraded_role_separation?: boolean;
}

export interface LlmRoleSuitability {
  provider_id: string;
  model_family: string;
  checks: Record<string, string>;
}

export interface LlmGovernanceStatus {
  llm_enabled: boolean;
  llm_mode: string;
  cloud_allowed: boolean;
  cloud_requested: boolean;
  airgap_enforced: boolean;
  default_provider: string | null;
  default_model: string | null;
  final_synthesis_enabled: boolean;
  answer_guard_enabled: boolean;
  context_sufficiency_required: boolean;
  limits: {
    timeout_seconds: number;
    max_input_tokens: number;
    max_output_tokens: number;
    temperature: number;
    streaming: boolean;
  };
  safety: {
    log_prompts: boolean;
    log_responses: boolean;
    redact_secrets: boolean;
    require_source_refs: boolean;
    allow_insufficient_evidence_response: boolean;
  };
  providers: LlmGovernanceProvider[];
  role_mappings: LlmGovernanceRoleMapping[];
  role_suitability?: LlmRoleSuitability[];
  deterministic_authorities?: string[];
  warnings: string[];
  notes: string[];
}

export interface LlmSettingsDraftProvider {
  provider_id: string;
  provider_type?: string;
  base_url?: string;
  api_key?: string;
  model?: string;
}

export interface LlmSettingsDraftRoleMapping {
  role: string;
  provider?: string;
  model?: string;
}

export interface LlmSettingsDraftCheckRequest {
  mode: string;
  enabled: boolean;
  allow_cloud: boolean;
  airgap_enforced: boolean;
  default_provider: string;
  default_model: string;
  timeout_seconds: number;
  max_input_tokens: number;
  max_output_tokens: number;
  temperature: number;
  streaming: boolean;
  log_prompts: boolean;
  log_responses: boolean;
  redact_secrets: boolean;
  require_context_sufficiency: boolean;
  require_source_refs: boolean;
  allow_insufficient_evidence_response: boolean;
  final_synthesis_enabled: boolean;
  answer_guard_enabled: boolean;
  providers: LlmSettingsDraftProvider[];
  role_mappings?: LlmSettingsDraftRoleMapping[];
}

export interface LlmSettingsDraftCheckResult {
  mode: string;
  enabled: boolean;
  cloud_allowed: boolean;
  airgap_enforced: boolean;
  final_synthesis_enabled: boolean;
  answer_guard_enabled: boolean;
  context_sufficiency_required: boolean;
  providers: { provider_id: string; provider_type: string; base_url_configured: boolean; api_key_configured: boolean; default_model_configured: boolean }[];
  role_mappings?: {
    role: string;
    provider: string | null;
    model: string | null;
    enabled: boolean;
    execution_eligible: boolean;
    validator_required: boolean;
  }[];
  validation_status: 'pass' | 'fail';
  validation_errors: string[];
  warnings: string[];
  saved: boolean;
  not_persisted: boolean;
  safe_message: string;
}

export interface McpConnectionVerificationResult {
  action: string;
  status: string;
  url_configured: boolean;
  authentication_configured: boolean;
  reachable: boolean | null;
  authenticated: boolean | null;
  mcp_handshake: string;
  tools_discovered_count: number;
  splunk_core_tools_discovered_count: number;
  saia_tools_discovered_count: number;
  execution_policy: string;
  last_checked_time: string;
  failure_reason: string;
  technical_error_detail: string;
  tools: { name: string; description?: string; capability?: string; categories?: string[]; blocked?: boolean; blocked_reason?: string | null }[];
  safe_message: string;
  secrets_returned: boolean;
}

export interface LlmConnectionVerificationResult {
  action: string;
  status: string;
  base_url_configured: boolean;
  api_key_configured: boolean;
  default_model_configured: boolean;
  reachable: boolean | null;
  authenticated: boolean | null;
  model_available: boolean | 'unknown' | string;
  policy_allowed: boolean;
  final_synthesis: 'disabled' | 'enabled' | string;
  answer_guard: 'disabled' | 'enabled' | string;
  last_checked_time: string;
  failure_reason: string;
  technical_error_detail: string;
  provider_id?: string | null;
  provider_type: string;
  model?: string | null;
  models: string[];
  models_count: number;
  safe_message: string;
  secrets_returned: boolean;
}

export interface SettingsStatus {
  mcp: {
    enabled: boolean;
    mode: 'mock' | 'live' | string;
    default_server?: string;
    global_execution_enabled?: boolean;
    discovery_enabled?: boolean;
    discovery_status?: string;
    configured: boolean;
    available: boolean;
    implemented?: boolean;
    fallback?: string | null;
    status_detail: string;
    servers?: McpServerStatus[];
    base_url_configured: boolean;
    token_configured: boolean;
    allowed_tools: string[];
    allowed_indexes: string[];
    allowed_sourcetypes: string[];
    timeout_seconds: number;
    max_rows: number;
    last_check_status: string;
    environment_mode?: string;
    splunk_mcp_enabled?: boolean;
    splunk_mcp_discovery_mode?: string;
    splunk_ai_assistant_mode?: string;
    splunk_saia_tools_enabled?: boolean;
    splunk_saia_require_discovery?: boolean;
    splunk_run_query_require_validation?: boolean;
    splunk_allow_run_saved_search?: boolean;
    fallback_required?: boolean;
    discovered_core_tool_count?: number;
    discovered_saia_tool_count?: number;
    splunk_capability?: Record<string, unknown>;
  };
  rag: {
    enabled: boolean;
    mode: string;
    configured: boolean;
    available: boolean;
    implemented?: boolean;
    fallback?: string | null;
    status_detail: string;
    vault_path: string;
    approved_documents: number;
    draft_documents: number;
    vector_store: string;
    keyword_index: string;
    knowledge_graph: string;
    chunk_size: number;
    chunk_overlap: number;
    embedding_model: string;
    repository_backend_type?: string;
    retrieval_mode?: string;
    vector_backend?: string;
    reranker_model?: string;
    embedding_indexing_enabled?: boolean;
    reranker_enabled?: boolean;
    graph_expansion_enabled?: boolean;
    final_synthesis_enabled?: boolean;
    import_prompt_available?: boolean;
    import_validation_enabled?: boolean;
    manual_edit_publish_available?: boolean;
    reranker?: {
      enabled: boolean;
      provider: string;
      model: string;
      configured: boolean;
      available: boolean;
    };
    ambiguity_assist?: {
      enabled: boolean;
      provider: string | null;
      configured: boolean;
      available: boolean;
      max_candidates: number;
    };
    last_ingestion_status: string;
    soc_kb?: {
      retrieval_enabled: boolean;
      repository_backend_type?: string;
      retrieval_mode?: string;
      vector_backend?: string;
      embedding_model?: string;
      reranker_model?: string;
      embedding_indexing_enabled?: boolean;
      reranker_enabled?: boolean;
      graph_expansion_enabled?: boolean;
      collections_configured_count: number;
      documents_total_count: number;
      eligible_current_approved_document_count: number;
      draft_count: number;
      retired_rejected_count: number;
      superseded_count: number;
      validation_warning_count?: number;
      import_batch_count?: number;
      environment: string;
      direct_to_llm: boolean;
      llm_selection_enabled: boolean;
      llm_ambiguity_assist_enabled?: boolean;
      hybrid_placeholder_enabled: boolean;
      graph_placeholder_enabled: boolean;
    };
    soc_kb_retrieval_enabled?: boolean;
    collections_configured_count?: number;
    documents_total_count?: number;
    eligible_current_approved_document_count?: number;
    draft_count?: number;
    retired_rejected_count?: number;
    superseded_count?: number;
    validation_warning_count?: number;
    import_batch_count?: number;
    environment?: string;
    direct_to_llm?: boolean;
    llm_selection_enabled?: boolean;
    llm_ambiguity_assist_enabled?: boolean;
    hybrid_placeholder_enabled?: boolean;
    graph_placeholder_enabled?: boolean;
  };
  llm: {
    enabled: boolean;
    mode: string;
    providers_configured?: string[];
    default_provider?: string;
    router_provider?: string;
    synthesis_provider?: string;
    reasoning_provider?: string;
    teacher_provider?: string;
    global_concurrency?: number;
    concurrency_per_provider?: number;
    health_canary_enabled?: boolean;
    tool_recommendation_enabled?: boolean;
    direct_mcp_tool_calling_enabled?: boolean;
    role_resolution?: Record<string, string | null>;
    providers?: LlmProviderStatus[];
    configured: boolean;
    available: boolean;
    implemented?: boolean;
    fallback?: string | null;
    status_detail: string;
    primary_model: string;
    reasoning_enabled: boolean;
    instruct_endpoint_configured: boolean;
    reasoning_endpoint_configured: boolean;
    temperature: number;
    timeout_seconds: number;
    max_context_tokens: number;
    governance?: LlmGovernanceStatus;
  };
  embeddings: {
    enabled: boolean;
    mode: string;
    configured: boolean;
    available: boolean;
    detail: string;
    model: string;
  };
  telemetry: {
    enabled: boolean;
    mode: string;
    configured: boolean;
    available: boolean;
    detail: string;
    sink: string;
    database_telemetry_enabled: boolean;
    splunk_write_enabled: boolean;
    splunk_sink_status: string;
    message: string;
  };
  routing: {
    mode: string;
    deterministic_router_enabled: boolean;
    llm_shadow_router_enabled: boolean;
    compare_logging_enabled: boolean;
    disagreement_logging_sink: string;
    db_disagreement_logging_enabled: boolean;
    chat_query_endpoint_wired: boolean;
    workflow_planner_enabled: boolean;
    workflow_planner_execution_enabled: boolean;
    workflow_plan_logging_enabled: boolean;
    deterministic_threshold: number;
    llm_planner_enabled: boolean;
    llm_tool_recommendation_enabled?: boolean;
    shadow_router_enabled: boolean;
    compare_node_enabled: boolean;
    adjudicator_policy: string;
    confidence_thresholds: { high: number; medium: number; low: number };
    fallback_policy: string;
  };
  safeguards: {
    spl_validator_enabled: boolean;
    blocked_spl_commands: string[];
    allowed_spl_commands?: string[];
    allowed_indexes?: string[];
    allowed_sourcetypes?: string[];
    max_result_limit?: number;
    time_range_required: boolean;
    aggregation_required: boolean;
    raw_event_dump_blocked: boolean;
    write_approval_required: boolean;
    evidence_validation_enabled: boolean;
    prompt_injection_filter_enabled: boolean;
  };
  observability: {
    telemetry_enabled: boolean;
    trace_logging_enabled: boolean;
    audit_sink_status: string;
    telemetry_sink: string;
    database_telemetry_enabled: boolean;
    splunk_write_enabled: boolean;
    splunk_sink_status: string;
    telemetry_write_failures?: number;
    recent_trace: string | null;
    planner_deterministic_mismatch_count: number;
    fallback_count: number;
    direct_llm_to_mcp_tool_calling?: boolean;
  };
}

export type ProviderTypeValue =
  | 'splunk_mcp'
  | 'generic_mcp'
  | 'security_api'
  | 'network_api'
  | 'asset_inventory'
  | 'ticketing'
  | 'rag_knowledge'
  | 'manual_input'
  | string;

export interface ProviderRegistryItem {
  provider_id: string;
  display_name: string;
  provider_type: ProviderTypeValue;
  enabled: boolean;
  status: string;
  environment_mode: string;
  available: boolean;
  auth_configured: boolean;
  discovered_operations: string[];
  allowed_operations: string[];
  blocked_operations: string[];
  discovered_operations_count: number;
  discovered_tools_count: number;
  hil_required_operations_count: number;
  hil_required_operations: string[];
  read_only_supported: boolean;
  write_supported: boolean;
  evidence_output_supported: boolean;
  fallback_required: boolean;
  warnings: string[];
  last_discovered?: string | null;
  planned: boolean;
  actions: {
    view: boolean;
    discover: boolean;
    edit: boolean;
  };
}

export interface ProviderToolStatus {
  provider_id: string;
  server_name: string;
  tool_name: string;
  category: string;
  allowed: boolean;
  blocked: boolean;
  blocked_reason?: string | null;
  requires_hil: boolean;
  execution_eligible: boolean;
  source_evidence_supported: boolean;
  description: string;
}

export interface ProviderSettingsStatus {
  providers: ProviderRegistryItem[];
  provider_types: ProviderTypeValue[];
  splunk_capability: {
    server_id?: string;
    environment_mode?: string;
    mcp_available?: boolean;
    discovery_mode?: string;
    core_splunk_tools_available?: boolean;
    saia_available?: boolean;
    saia_usable?: boolean;
    fallback_required?: boolean;
    run_query_requires_validation?: boolean;
    run_saved_search_allowed?: boolean;
    discovered_at?: string;
    [key: string]: unknown;
  };
  saia: {
    splunk_ai_assistant_mode: string;
    saia_discovered: boolean;
    saia_usable: boolean;
    fallback_active: boolean;
    features: {
      generate_spl: boolean;
      explain_spl: boolean;
      optimize_spl: boolean;
      ask_splunk_question: boolean;
    };
  };
  tool_groups: Record<string, ProviderToolStatus[]>;
  notes: string[];
}

export interface ProviderDraftCheckRequest {
  provider_id: string;
  display_name?: string;
  provider_type: string;
  environment_mode: string;
  enabled: boolean;
  discovery_mode: string;
  transport: string;
  auth_mode: string;
  base_url: string;
  auth_token?: string;
  username?: string;
  password?: string;
  notes?: string;
}

export interface ProviderDraftCheckResult {
  provider_id: string;
  provider_type: string;
  enabled: boolean;
  environment_mode: string;
  discovery_mode: string;
  transport: string;
  auth_mode: string;
  base_url_configured: boolean;
  auth_token_configured: boolean;
  username_configured?: boolean;
  password_configured?: boolean;
  validation_status: string;
  validation_errors: string[];
  connection_check: {
    status: string;
    reason: string;
    real_connection_attempted: boolean;
  };
  saved: boolean;
  not_persisted: boolean;
  safe_message: string;
}

export type KnowledgeExportArtifact =
  | 'question_runtime_map'
  | 'use_case_catalog'
  | 'soc_capability_crosswalk'
  | 'skill_coverage_matrix'
  | 'github_skill_discovery_index'
  | 'github_skill_triage_scores'
  | 'github_skill_intake_register'
  | 'proposed_use_cases_from_github'
  | 'skill_enrichment_status_matrix'
  | 'rejected_github_skills'
  | 'pending_skill_enrichment_backlog'
  | 'soc_validation_use_cases'
  | 'soc_validation_spl_templates'
  | 'soc_validation_mitre'
  | 'soc_validation_questions'
  | 'soc_validation_github_enrichment'
  | 'soc_validation_github_batch_intake'
  | 'soc_validation_rag_sop'
  | 'soc_validation_pending_backlog'
  | 'soc_validation_combination_matrix'
  | 'soc_validation_demo_scenarios';

export interface KnowledgeCollection {
  collection_id: string;
  name: string;
  purpose: string;
  environment: string;
  enabled: boolean;
  allowed_document_types: string[];
  allowed_use: string[];
  priority: number;
  owner?: string;
  description?: string;
}

export interface KnowledgeDocument {
  doc_id: string;
  collection_id: string;
  title: string;
  document_type: string;
  environment: string;
  version: string;
  revision?: string;
  status: string;
  approval_status: string;
  lifecycle_stage?: string;
  allowed_use: string[];
  risk_level?: string;
  sensitivity?: string;
  checksum_sha256?: string;
  canonical_doc_id?: string;
  is_current_version?: boolean;
  superseded_by_doc_id?: string | null;
}

export interface KnowledgeEntry {
  entry_id: string;
  doc_id: string;
  title: string;
  entry_type: string;
  source_excerpt?: string;
  source_refs?: string[];
  citation?: string;
  allowed_use?: string[];
  status?: string;
  approval_status?: string;
  risk_level?: string;
}

export interface McpServerStatus {
  name: string;
  type: string;
  enabled: boolean;
  implemented: boolean;
  configured: boolean;
  available: boolean;
  transport: string;
  url_configured: boolean;
  command_configured: boolean;
  auth_mode: string;
  auth_configured: boolean;
  execution_enabled: boolean;
  discovered_tools_count: number;
  discovered_tools_safe_names: string[];
  discovered_tools?: {
    name: string;
    description: string;
    capability: string;
    categories?: string[];
    blocked: boolean;
    blocked_reason?: string | null;
  }[];
  blocked_tools_count: number;
  blocked_tools_safe_names: string[];
  last_error?: string | null;
  splunk_app_id?: string | null;
  splunk_platform?: string | null;
  search_execution_allowed?: boolean | null;
  saia_spl_generation_allowed?: boolean | null;
  knowledge_object_discovery_allowed?: boolean | null;
  list_tools_allowed?: boolean | null;
}

export interface LlmProviderStatus {
  name: string;
  type: string;
  family: string;
  model_role: string;
  enabled: boolean;
  implemented: boolean;
  configured: boolean;
  available: boolean;
  model: string;
  base_url_configured: boolean;
  api_key_configured: boolean;
  auth_mode: string;
  context_tokens?: number | null;
  max_output_tokens?: number | null;
  supports_streaming: boolean;
  supports_json_mode: boolean;
  supports_tool_calling: boolean;
  concurrency_limit: number;
  last_error?: string | null;
}
