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
}

export interface EcAnalystPayload {
  finding_title?: string | null;
  one_sentence_finding?: string | null;
  direct_answer_summary?: string | null;
  severity_label?: string | null;
  recommended_actions?: string[];
  splunk_results_table?: Array<Record<string, unknown>>;
  mitre_mappings?: Array<Record<string, unknown>>;
  key_fields?: string[];
  analyst_checklist?: string[];
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
  ec_projection: EcProjection;
  ec_actions: EcActionRecord[];
  ec_followups: EcFollowUpChip[];
  ec_session_state: EcSessionState;
  ec_provenance: Record<string, unknown>;
}

export interface EcScenarioSummary {
  scenario_id: string;
  label: string;
  category: string;
  query: string;
  expected_skill: string;
}
