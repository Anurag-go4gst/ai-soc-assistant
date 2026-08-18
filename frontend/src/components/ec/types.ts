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

export interface EcAnalystPayload {
  finding_title?: string | null;
  one_sentence_finding?: string | null;
  direct_answer_summary?: string | null;
  direct_answer_line?: string | null;
  assessment?: string | null;
  what_we_found?: string | null;
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
  scenario_id: string;
  trace_id: string;
  message: string;
  analyst_summary?: string | null;
  analyst?: EcAnalystPayload | null;
  analyst_response?: EcAnalystPayload | null;
  selected_skill?: string | null;
  route_source?: string;
  candidate_spl?: { candidate_spl?: string; execution_eligible?: boolean } | null;
  spl_validation?: { approved?: boolean } | null;
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
