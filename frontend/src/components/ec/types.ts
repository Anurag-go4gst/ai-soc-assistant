export interface EcSourceEvidenceItem {
  evidence_id: string;
  source_type: string;
  source_name: string;
  preview_rows?: Array<Record<string, unknown>>;
  provenance?: string | null;
  tool_name?: string | null;
  query_or_request_summary?: string | null;
  executed_spl?: string | null;
  warnings?: string[];
}

export interface EcProvenanceStamp {
  kind: string;
  detail?: string | null;
}

export interface EcProjectionView {
  title: string;
  summary: string;
  items: string[];
  provenance: EcProvenanceStamp;
}

export interface EcProjection {
  understanding: EcProjectionView;
  resource_plan: EcProjectionView;
  phase_contract: EcProjectionView;
  evidence_state: EcProjectionView;
  investigation_outcome: EcProjectionView;
  provenance: EcProvenanceStamp;
}

export interface EcFollowUpChip {
  follow_up_id: string;
  label: string;
  advances_state: boolean;
  group?: 'continue' | 'action';
  leads_to_action?: boolean;
}

export interface EcSessionState {
  session_id?: string | null;
  family: string;
  scenario_id: string;
  turn: number;
  pending_action_id?: string | null;
  awaiting_external: boolean;
  applied_follow_up_ids: string[];
}

export interface EcActionRecord {
  action_id: string;
  kind: string;
  label: string;
  state: string;
  provenance: string;
  production_side_effect: boolean;
  receipt?: Record<string, unknown> | null;
  verify_result?: Record<string, unknown> | null;
  draft?: Record<string, unknown> | null;
}

export interface EcVpnGatewayPostureRow {
  gateway: string;
  site: string;
  version: string;
  affected: boolean;
  health: string;
  active_sessions?: number;
  wan_mgmt_listener?: string;
}

export interface EcCapabilityPlanRow {
  integration: string;
  status: string;
  detail: string;
}

export interface EcAgilusPatchStatus {
  product: string;
  patch_id: string;
  patch_title: string;
  targets: string[];
  status: 'ANALYZED' | 'READY_TO_SUBMIT' | 'AWAITING_CALLBACK' | 'APPLIED';
  job_id?: string | null;
  ticket_id?: string | null;
  detail: string;
}

export interface EcInvestigationPhaseStep {
  id: string;
  title: string;
  status: string;
  plan_summary: string;
  action_label?: string;
  follow_up_id?: string;
  connector_mode?: string;
  connector_available?: boolean;
  fallback_label?: string;
  executed?: boolean;
  detail?: string | null;
  spl_preview?: string | null;
  hil_action?: boolean;
  bullets?: string[];
}

export interface EcAgentStepFinding {
  headline_finding?: string;
  headlines_by_status?: Partial<Record<string, string>>;
  key_evidence?: string[];
  affected_entities?: string[];
  quantitative_summary?: Record<string, string | number>;
  confidence?: string;
  caveat?: string;
  evidence_sources?: Array<{
    source: string;
    evidence_id?: string;
    provenance?: string;
    tool?: string;
  }>;
  details?: Record<string, unknown>;
  attention_state?: 'NORMAL' | 'ATTENTION' | 'RISK' | 'NO_MATCH' | 'INFORMATIONAL';
}

export interface EcAgentPlanStep {
  id: string;
  title: string;
  summary?: string;
  follow_up_id?: string | null;
  tools?: string[];
  selected?: boolean;
  optional?: boolean;
  default_selected?: boolean;
  status?: string;
  result?: string | null;
  finding?: EcAgentStepFinding | null;
  provenance?: string;
  added_by_agent?: boolean;
  reason?: string;
  hil_required?: boolean;
  /** CIO layer — why this step exists (investigation and remediation). */
  rationale?: string;
  /** Show the rationale line (only for non-obvious steps). */
  why_visible?: boolean;
  /** Investigation: the decision this step informs. */
  decides?: string;
  /** Investigation: what is lost without it. */
  if_skipped?: string;
  /** Remediation: whether and how the action can be undone. */
  reversible?: string;
  /** Remediation: who must approve it. */
  approver?: string;
  /** Remediation: the risk of not doing it. */
  risk_if_skipped?: string;
  tool_ids?: string[];
  /** Remediation: analyst-facing state, e.g. "Pending approval", "Requested", "Verified". */
  status_label?: string;
  /** Incident action before approval: policy priority, and the analyst's choice. */
  priority_control?: EcPriorityControl;
}

export interface EcPriorityControl {
  policy_priority: string;
  policy_rule: string;
  policy_basis: string;
  options: string[];
  selected: string;
  reason: string;
}

/** Priority the analyst sends with approval; a change from policy carries a reason. */
export interface EcPriorityOverride {
  priority: string;
  reason: string;
}

/** A ticket as ITSM holds it after the action that created (or updated) it ran. */
export interface EcTicketRecord {
  number: string;
  type: string;
  state: string;
  priority?: string;
  threat_assessment?: string;
  category?: string;
  configuration_item?: string;
  assignment_group?: string;
  short_description?: string;
  description?: string;
  work_note?: string;
  attachment?: string;
  opened?: string;
  updated?: string;
  opened_by?: string;
  updated_by?: string;
  parent?: string | null;
  related?: string[];
}

export interface EcEmailDelivery {
  sent: boolean;
  line: string;
  to_address?: string | null;
  cc_addresses?: string[];
  cc_not_copied?: string[];
  message_id?: string | null;
}

/** Incident priority (from the deterministic policy) kept apart from the threat assessment. */
export interface EcAssessment {
  incident_priority: string;
  priority_rule: string;
  priority_basis: string;
  threat_assessment: string;
  priority_override?: { policy_priority: string; reason: string } | null;
}

export interface EcExecutiveBrief {
  verdict: string;
  business_impact?: string;
  risk_from?: string;
  risk_to?: string;
  confidence?: string;
  would_change_if?: string;
  decision_needed?: string;
  will_not_do?: string;
}

export interface EcRagPassage {
  entry_id: string;
  label: string;
  citation: string;
  doc_title: string;
  doc_version: string;
  approval_status: string;
  confidence: number;
  excerpt: string;
  used: boolean;
  used_for?: string;
}

export interface EcRagTrace {
  question: string;
  collections: string[];
  retrieval_mode?: string;
  top_confidence?: number;
  direct_to_llm?: boolean;
  excluded: Array<{ reason: string; count: number }>;
  excluded_total: number;
  passages: EcRagPassage[];
  answer: {
    headline: string;
    sentences: Array<{ text: string; citations: string[] }>;
    gaps: string[];
  };
  governance?: string[];
}

export interface EcStoryThread {
  thread_id: string;
  day: number;
  total_days: number;
  title: string;
  verdict_so_far: string;
  next?: { scenario_id: string; label: string } | null;
}

export interface EcToolFabricEntry {
  tool_id: string;
  name: string;
  role: string;
  kind: string;
  demo_fixture: boolean;
  used: boolean;
}

export interface EcAgentWorkflowPayload {
  lifecycle: string;
  phase?: 'plan' | 'investigation_complete' | 'remediation';
  opening_narrative?: string;
  brief?: {
    what_i_know?: string[];
    objective?: string[];
  };
  action_plan?: {
    summary?: string;
    steps?: string[];
  };
  investigation_plan?: {
    editable?: boolean;
    summary?: string;
    primary_cta?: string;
    secondary_cta?: string;
    steps?: EcAgentPlanStep[];
  };
  investigation_results?: {
    header?: string;
    steps?: EcAgentPlanStep[];
  };
  investigation_summary?: {
    title?: string;
    steps_completed?: number;
    steps_total?: number;
    metrics?: Array<{ label: string; value: string | number }>;
  } | null;
  normalized_state?: {
    affected_asset_ids?: string[];
    anomalous_asset_ids?: string[];
    patch_id?: string;
    patch_scope_asset_ids?: string[];
    compromise_status?: string;
  };
  remediation_plan?: {
    editable?: boolean;
    summary?: string;
    primary_cta?: string;
    secondary_cta?: string;
    visible?: boolean;
    steps?: EcAgentPlanStep[];
    error?: string | null;
  };
  remediation_summary?: {
    title?: string;
    steps_completed?: number;
    steps_total?: number;
    plan_steps?: string;
    metrics?: Array<{ label: string; value: string | number }>;
  } | null;
  remediation_conclusion?: {
    title?: string;
    headline?: string;
    narrative_points?: string[];
  } | null;
  remediation_results?: {
    header?: string;
    steps?: EcAgentPlanStep[];
  };
  execution_progress?: {
    phase?: string;
    header?: string;
    steps?: EcAgentPlanStep[];
  };
  hil_prompt?: {
    title?: string;
    body?: string;
    approve_label?: string;
    skip_label?: string;
    approve_follow_up_id?: string;
    skip_follow_up_id?: string;
    connector?: string;
    connection_trace?: Array<{ label: string; status: string }>;
  } | null;
  remediation_offer?: {
    title?: string;
    body?: string;
    yes_label?: string;
    no_label?: string;
    yes_follow_up_id?: string;
    no_follow_up_id?: string;
  } | null;
  unconfirmed?: string[];
  missing_evidence?: string[];
  executive_summary?: string[];
  executive_brief?: EcExecutiveBrief | null;
  tool_fabric?: EcToolFabricEntry[];
  rag_trace?: EcRagTrace | null;
  investigation_conclusion?: {
    title?: string;
    headline?: string;
    narrative?: string;
    narrative_points?: string[];
    exposure?: string;
    compromise?: string;
    confidence?: number;
    findings?: string[];
    evidence_summary?: Array<{ source: string; detail: string; provenance: string }>;
    assessment?: EcAssessment | null;
    /** Knowledge-base passages the answer cites. */
    sources?: string[];
  } | null;
  next_step_cta?: {
    label?: string;
    follow_up_id?: string;
  } | null;
  final_summary?: {
    title?: string;
    headline?: string;
    severity?: string;
    affected?: string;
    compromise?: string;
    completed?: string[];
    in_progress?: string[];
    deferred?: string[];
    risk_from?: string;
    risk_to?: string;
    risk_note?: string;
    assessment?: EcAssessment | null;
    actions?: Array<{
      title: string;
      status: string;
      status_label: string;
      result?: string | null;
      ticket?: EcTicketRecord | null;
      email?: { to: string; subject: string; body: string; status?: string } | null;
      email_delivery?: EcEmailDelivery | null;
    }>;
  } | null;
  verification?: Array<{ item: string; status: string; detail: string }>;
}

export interface EcAffectedSystem {
  system: string;
  role?: string;
  activity: string;
  first_seen: string;
  last_seen: string;
  allowed_denied: string;
  auth_correlation: string;
  identity_auth_context?: string;
  risk_note: string;
}

export interface EcEvidenceStateItem {
  id: string;
  label: string;
  status: string;
  provenance: string;
  detail?: string;
}

export interface EcSplSearch {
  search_id: string;
  label: string;
  earliest: string;
  latest: string;
  candidate_spl: string;
  normalized_spl?: string | null;
  approved: boolean;
  reject_reasons: string[];
  provenance: string;
}

export interface EcSplGovernance {
  user_request: string;
  time_range_supplied: boolean;
  environment_governance: string;
  why: string;
  searches: EcSplSearch[];
  controls: string[];
  validation: {
    engine: string;
    provenance: string;
    search_1_approved: boolean;
    search_2_approved: boolean;
    override: boolean;
  };
  evidence_merge: string;
  production_mcp_executed: boolean;
  spl_not_required: boolean;
}

export interface EcInvestigationOutcomePayload {
  disposition: string;
  confirmed: string[];
  supported: string[];
  unconfirmed: string[];
  missing_evidence: string[];
  mitre?: Array<Record<string, string>>;
  closure_summary?: string | null;
}

export interface EcSiemCoverageRow {
  investigation_need: string;
  siem_status: string;
  decision: string;
}

export interface EcSiemCoverageAssessment {
  siem: string;
  coverage_status: string;
  existing_content?: Array<Record<string, unknown>>;
  required_evidence?: Array<Record<string, unknown>>;
  generated_searches?: Array<Record<string, unknown>>;
  remaining_gaps?: string[];
  coverage_rows?: EcSiemCoverageRow[];
}

export interface EcSiemToolTrace {
  purpose: string;
  capability: string;
  mcp_tool: string;
  mode?: string;
  detail?: string | null;
  candidate_spl?: string | null;
  normalized_spl?: string | null;
  validator_status?: string | null;
  exact_call_authorization?: string | null;
  provenance?: string;
}

export interface EcAttackChainStep {
  label: string;
  status: string;
  detail?: string | null;
}

export interface EcEvidenceFindingRow {
  investigation_point: string;
  finding: string;
  evidence_basis: string;
}

export interface EcDetectionOpportunity {
  status: string;
  title: string;
  summary: string;
  recommended_action: string;
  deploy_status?: string;
  notes?: string | null;
}

export interface EcTelemetrySourceRow {
  source: string;
  status: string;
  detail?: string | null;
}

export interface EcInvestigationScope {
  time_range: string;
  telemetry_queried?: string[];
  telemetry_sources?: EcTelemetrySourceRow[];
  scope_note?: string | null;
}

export interface EcInvestigationPivot {
  title: string;
  subject?: string | null;
  summary: string;
}

export interface EcActionReadinessRow {
  action: string;
  state: string;
}

export interface EcEvidenceReuseRow {
  evidence_id: string;
  label: string;
  origin: string;
  status: string;
  detail?: string | null;
}

export interface EcResourceCompositionRow {
  resource: string;
  role: string;
  mode: string;
  note?: string;
}

export interface EcAnalystTextSegment {
  type: 'text' | 'evidence_link';
  text: string;
  evidence_id?: string;
  title?: string | null;
}

export interface EcAnalystPayload {
  finding_title?: string | null;
  /** Findings added by follow-up chips on non-agent answers, newest last. */
  follow_up_findings?: string[] | null;
  one_sentence_finding?: string | null;
  direct_answer_summary?: string | null;
  direct_answer_line?: string | null;
  assessment?: string | null;
  what_we_found?: string | null;
  what_we_found_segments?: EcAnalystTextSegment[] | null;
  severity_label?: string | null;
  recommended_actions?: string[];
  splunk_results_table?: Array<Record<string, unknown>>;
  mitre_mappings?: Array<Record<string, unknown>>;
  key_fields?: string[];
  analyst_checklist?: string[];
  affected_systems?: EcAffectedSystem[];
  important_evidence?: string[];
  unconfirmed_findings?: string[];
  missing_evidence?: string[];
  spl_code?: string | null;
  spl_status?: string | null;
  spl_status_detail?: Record<string, unknown> | null;
  review_notice?: string | null;
  response_profile?: string | null;
}

export interface ExperienceCenterResponse {
  ec_story_thread?: EcStoryThread | null;
  scenario_id: string;
  trace_id: string;
  message: string;
  analyst_summary?: string | null;
  analyst?: EcAnalystPayload | null;
  analyst_response?: EcAnalystPayload | null;
  selected_skill?: string | null;
  route_source?: string;
  candidate_spl?: { candidate_spl?: string; execution_eligible?: boolean } | null;
  spl_validation?: { approved?: boolean; warnings?: string[] } | null;
  source_evidence?: EcSourceEvidenceItem[];
  ec_projection: EcProjection;
  ec_actions: EcActionRecord[];
  ec_followups: EcFollowUpChip[];
  ec_session_state: EcSessionState;
  ec_provenance: Record<string, unknown>;
  ec_search_governance_policy?: Record<string, unknown>;
  ec_spl_governance?: EcSplGovernance;
  ec_affected_systems?: EcAffectedSystem[];
  ec_investigation_outcome?: EcInvestigationOutcomePayload;
  ec_evidence_state?: EcEvidenceStateItem[];
  ec_layer2_path?: string[];
  production_side_effect?: boolean;
  ec_email?: {
    to?: string;
    subject?: string;
    mandatory_fields?: Record<string, unknown>;
    status?: string;
    inbound?: string;
  };
  ec_workflow_state?: string;
  ec_workflow_path?: string[];
  ec_impact_legend?: string[];
  ec_status_summary?: string;
  ec_applicability?: Array<{ key?: string; status: string; reason?: string }>;
  ec_conflict?: { status?: string; sources?: string[] };
  ec_ticket_id?: string;
  ec_execution_journey?: EcExecutionJourney | null;
  ec_siem_coverage?: EcSiemCoverageAssessment;
  ec_siem_tool_traces?: EcSiemToolTrace[];
  ec_attack_chain?: EcAttackChainStep[];
  ec_evidence_findings?: EcEvidenceFindingRow[];
  ec_detection_opportunity?: EcDetectionOpportunity;
  ec_investigation_scope?: EcInvestigationScope;
  ec_investigation_pivot?: EcInvestigationPivot;
  ec_action_readiness?: EcActionReadinessRow[];
  ec_recommended_investigations?: string[];
  ec_evidence_reuse?: EcEvidenceReuseRow[];
  ec_resource_composition?: EcResourceCompositionRow[];
  ec_continuity_policy?: Record<string, unknown>;
  ec_spl_governance_summary?: string;
  ec_gap_spl_notice?: string;
  ec_gap_spl_layer2_only?: boolean;
  ec_executive_summary?: string[];
  ec_opening_briefing?: string;
  ec_vpn_gateway_posture?: EcVpnGatewayPostureRow[];
  ec_capability_plan?: EcCapabilityPlanRow[];
  ec_agilus_patch?: EcAgilusPatchStatus | null;
  ec_investigation_phases?: EcInvestigationPhase[];
  ec_agent_workflow?: EcAgentWorkflowPayload | null;
  ec_agent_lifecycle?: string;
}

export interface EcInvestigationPhase {
  phase: string;
  title: string;
  steps: EcInvestigationPhaseStep[];
}

export interface EcExecutionResource {
  system: string;
  operation: string;
  mode?: 'read' | 'write' | 'knowledge';
}

export interface EcExecutionStage {
  id: string;
  title: string;
  description?: string;
  activity?: string[];
  semantic_type?: string;
  resource?: EcExecutionResource | null;
  duration_ms_hint?: number | null;
  evidence_added?: string[];
  outcome_change?: string | null;
  action_state?: string | null;
  provenance?: string;
}

export interface EcExecutionJourney {
  journey_id: string;
  kind: 'initial' | 'follow_up' | 'action';
  header: string;
  follow_up_id?: string | null;
  action_id?: string | null;
  stages: EcExecutionStage[];
}

export interface EcScenarioSummary {
  scenario_id: string;
  label: string;
  category: string;
  query: string;
  canonical_query?: string;
  aliases?: string[];
  expected_skill: string;
}
