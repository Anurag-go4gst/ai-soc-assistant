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
  user_query?: string | null;
  selected_skill?: string | null;
  tool_plan?: string[] | null;
  confidence?: number | null;
  routing_mode?: string | null;
  disagreement?: boolean | null;
  disagreement_reason?: string | null;
  routing_trace?: RoutingTraceEnvelope | null;
  workflow_plan?: WorkflowPlan | null;
  candidate_spl?: CandidateSplEnvelope | null;
  spl_validation?: SplValidationEnvelope | null;
  execution?: ExecutionEnvelope | null;
  human_review?: HumanReviewEnvelope | null;
  source_evidence?: SourceEvidenceEnvelope[];
  structured_context?: StructuredContextPackage | null;
  context_sufficiency?: ContextSufficiencyEnvelope | null;
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
}

export interface SplValidationEnvelope {
  approved: boolean;
  normalized_spl?: string | null;
  reject_reasons: string[];
  warnings: string[];
  enforced_limits: Record<string, unknown>;
  policy_version: string;
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
  collection_status: 'collected' | 'blocked' | 'failed' | 'skipped' | 'requires_human_review' | string;
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
  policy_context_refs: string[];
  assumptions: string[];
  warnings: string[];
  missing_evidence: string[];
  allowed_conclusions: string[];
  prohibited_conclusions: string[];
  context_quality: 'sufficient' | 'partial' | 'insufficient' | 'blocked' | string;
  synthesis_allowed: boolean;
}

export interface ContextSufficiencyEnvelope {
  status: 'pass' | 'partial' | 'fail' | 'requires_human_review' | string;
  synthesis_allowed: boolean;
  reasons: string[];
  missing_evidence: string[];
  human_review?: HumanReviewEnvelope | null;
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
    last_ingestion_status: string;
    direct_to_llm?: boolean;
    final_synthesis_enabled?: boolean;
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
