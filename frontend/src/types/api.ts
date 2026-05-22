export interface HealthResponse {
  status: string;
  service: string;
}

export interface AuthResponse {
  authenticated: boolean;
  username?: string | null;
  role?: string | null;
}

export interface PlaceholderResponse {
  trace_id: string;
  message: string;
  note: string;
}

export interface SettingsStatus {
  mcp: {
    enabled: boolean;
    mode: 'mock' | 'live' | string;
    base_url_configured: boolean;
    token_configured: boolean;
    allowed_tools: string[];
    allowed_indexes: string[];
    allowed_sourcetypes: string[];
    timeout_seconds: number;
    max_rows: number;
    last_check_status: string;
  };
  rag: {
    enabled: boolean;
    mode: string;
    vault_path: string;
    approved_documents: number;
    draft_documents: number;
    vector_store: string;
    keyword_index: string;
    knowledge_graph: string;
    chunk_size: number;
    chunk_overlap: number;
    embedding_model: string;
    last_ingestion_status: string;
  };
  llm: {
    enabled: boolean;
    mode: string;
    primary_model: string;
    reasoning_enabled: boolean;
    instruct_endpoint_configured: boolean;
    reasoning_endpoint_configured: boolean;
    temperature: number;
    timeout_seconds: number;
    max_context_tokens: number;
  };
  routing: {
    mode: string;
    llm_planner_enabled: boolean;
    shadow_router_enabled: boolean;
    compare_node_enabled: boolean;
    adjudicator_policy: string;
    confidence_thresholds: { high: number; medium: number; low: number };
    fallback_policy: string;
  };
  safeguards: {
    spl_validator_enabled: boolean;
    blocked_spl_commands: string[];
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
    audit_index: string;
    recent_trace: string | null;
    planner_deterministic_mismatch_count: number;
    fallback_count: number;
  };
}
