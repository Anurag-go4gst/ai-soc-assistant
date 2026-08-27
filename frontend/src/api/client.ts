import { getApiBaseUrl } from '@/lib/runtimeMode';
import type {
  AuthResponse,
  ChatAnswerFeedbackRequest,
  ChatAnswerFeedbackResponse,
  ChatReviewOptions,
  DebugReadinessResponse,
  DebugTraceBundle,
  DebugTraceTimeline,
  DebugTracesResponse,
  DemoScenariosResponse,
  HealthResponse,
  KnowledgeCollection,
  KnowledgeDocument,
  KnowledgeEntry,
  LlmConnectionVerificationResult,
  LlmSettingsDraftCheckRequest,
  LlmSettingsDraftCheckResult,
  McpConnectionVerificationResult,
  ActionProposalEnvelope,
  PlaceholderResponse,
  ProviderDraftCheckRequest,
  ProviderDraftCheckResult,
  ProviderSettingsStatus,
  QualityFlaggedTurnsResponse,
  SettingsStatus,
  SourceProfileDiscoverResponse,
  SourceProfileSaveResponse,
  SourceProfileSettingsResponse,
  AssetRegistryRecord,
  AssetRegistryResponse,
  IocRegistrySettingsResponse,
  KnowledgeExportArtifact,
  KnowledgeMappingSummary,
} from '../types/api';

const API_BASE_URL = getApiBaseUrl();

export const UNAUTHORIZED_EVENT = 'ai-soc-unauthorized';

// Endpoints whose 401 is an expected business outcome (bad login, anonymous
// probe) and must NOT bounce the user to the login screen.
const UNAUTHORIZED_BOUNCE_EXCLUDED = ['/auth/login', '/auth/me'];

// Global 401 interceptor. The SPA validates auth once on mount via the
// un-gated /auth/me probe and caches the result, so an expired session leaves
// the app rendering a logged-in shell while every gated API call returns 401.
// Catch those 401s centrally and emit an event the App listens for to force a
// re-auth, instead of each panel silently surfacing a toast.
function installUnauthorizedInterceptor(): void {
  if (typeof window === 'undefined') return;
  const flagged = window as typeof window & { __aiSocAuthInterceptor?: boolean };
  if (flagged.__aiSocAuthInterceptor) return;
  flagged.__aiSocAuthInterceptor = true;

  const originalFetch = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const response = await originalFetch(input, init);
    if (response.status === 401) {
      const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
      const isApiCall = url.includes(API_BASE_URL);
      const isExcluded = UNAUTHORIZED_BOUNCE_EXCLUDED.some((path) => url.includes(path));
      if (isApiCall && !isExcluded) {
        window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT));
      }
    }
    return response;
  };
}

installUnauthorizedInterceptor();

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`, { credentials: 'include' });
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }
  return response.json();
}

export async function getCurrentUser(): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/me`, { credentials: 'include' });
  if (!response.ok) {
    throw new Error(`Auth check failed: ${response.status}`);
  }
  return response.json();
}

export async function login(username: string, password: string): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ username, password }),
  });

  if (response.status === 401) {
    throw new Error('Invalid credentials');
  }
  if (!response.ok) {
    throw new Error(`Login failed: ${response.status}`);
  }
  return response.json();
}

export async function logout(): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/auth/logout`, {
    method: 'POST',
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error(`Logout failed: ${response.status}`);
  }
}

export async function updateUserProfile(payload: { debug_access: boolean }): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/profile`, {
    method: 'PATCH',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Profile update failed: ${response.status}`);
  }
  return response.json();
}

export async function sendChatMessage(
  message: string,
  sessionId?: string | null,
  llmSplDraftMode = false,
  executionReview?: ChatReviewOptions,
): Promise<PlaceholderResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      ...(sessionId ? { session_id: sessionId } : {}),
      ...(llmSplDraftMode ? { llm_spl_draft_mode: true } : {}),
      ...(executionReview ?? {}),
    }),
  });
  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.status}`);
  }
  return response.json();
}

export async function submitChatAnswerFeedback(payload: ChatAnswerFeedbackRequest): Promise<ChatAnswerFeedbackResponse> {
  const response = await fetch(`${API_BASE_URL}/chat/feedback`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Answer feedback save failed: ${response.status}`);
  }
  return response.json();
}

export async function getQualityFlaggedTurns(limit = 50): Promise<QualityFlaggedTurnsResponse> {
  const response = await fetch(`${API_BASE_URL}/quality/flagged-turns?limit=${encodeURIComponent(String(limit))}`, {
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error(`Quality flagged turns failed: ${response.status}`);
  }
  return response.json();
}

export interface QualitySummaryResponse {
  total_turns: number;
  flagged_turns: number;
  in_review_turns: number;
  golden_candidate_turns: number;
  flagged_rate: number;
  expectation_matrix_rows: number;
  golden_coverage: Record<string, number>;
  latest_golden_eval: Record<string, unknown>;
}

export async function getQualitySummary(): Promise<QualitySummaryResponse> {
  const response = await fetch(`${API_BASE_URL}/quality/summary`, { credentials: 'include' });
  if (!response.ok) {
    throw new Error(`Quality summary failed: ${response.status}`);
  }
  return response.json();
}

export async function getDemoScenarios(): Promise<DemoScenariosResponse> {
  const response = await fetch(`${API_BASE_URL}/demo/scenarios`, { credentials: 'include' });
  if (!response.ok) {
    throw new Error(`Demo scenarios request failed: ${response.status}`);
  }
  return response.json();
}

export async function runDemoScenario(scenarioId: string): Promise<PlaceholderResponse> {
  const response = await fetch(`${API_BASE_URL}/demo/scenarios/${encodeURIComponent(scenarioId)}/run`, {
    method: 'POST',
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error(`Demo scenario run failed: ${response.status}`);
  }
  return response.json();
}

export async function investigateAlert(alertId: string, summary?: string): Promise<PlaceholderResponse> {
  const response = await fetch(`${API_BASE_URL}/investigate`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ alert_id: alertId, summary }),
  });
  if (!response.ok) {
    throw new Error(`Investigation request failed: ${response.status}`);
  }
  return response.json();
}

export async function getSettingsStatus(): Promise<SettingsStatus> {
  const response = await fetch(`${API_BASE_URL}/settings/status`, { credentials: 'include' });
  if (!response.ok) {
    throw new Error(`Settings status failed: ${response.status}`);
  }
  return response.json();
}

export async function selectEnvProfile(profileId: string): Promise<import('@/types/api').EnvProfileSelectResult> {
  const response = await fetch(`${API_BASE_URL}/settings/env-profile`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profile_id: profileId }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Env profile select failed: ${response.status}`);
  }
  return response.json();
}

export interface LlmControlStatus {
  control_available: boolean;
  last_control_result?: Record<string, unknown> | null;
}

export async function getLlmControlStatus(): Promise<LlmControlStatus> {
  const response = await fetch(`${API_BASE_URL}/settings/llm/control-status`, { credentials: 'include' });
  if (!response.ok) {
    throw new Error(`LLM control status failed: ${response.status}`);
  }
  return response.json();
}

export interface LlmRuntimeHealth {
  reachable: boolean;
  tok_per_s: number | null;
  status: string;
  healthy: boolean;
  reason: string;
  prompt_eval_s?: number | null;
  sampled_tokens?: number;
  model?: string | null;
  threshold_tok_per_s?: number;
  control_available: boolean;
  last_control_result?: Record<string, unknown> | null;
}

export async function getLlmRuntimeHealth(): Promise<LlmRuntimeHealth> {
  const response = await fetch(`${API_BASE_URL}/settings/llm/runtime-health`, { credentials: 'include' });
  if (!response.ok) {
    throw new Error(`LLM runtime health failed: ${response.status}`);
  }
  return response.json();
}

export async function controlLlm(action: 'restart' | 'stop' | 'start'): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE_URL}/settings/llm/control`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action }),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(`LLM control (${action}) failed: ${response.status} ${(detail as { detail?: string }).detail ?? ''}`);
  }
  return response.json();
}

export interface LlmLabStatus {
  available: boolean;
  llm_enabled: boolean;
  mode: string;
  provider_configured: boolean;
  active_model: string | null;
  available_models: string[];
  disclaimer: string;
}

export interface LlmLabAnswer {
  answer: string | null;
  available: boolean;
  llm_called: boolean;
  provider: string | null;
  timed_out: boolean;
  latency_ms: number;
  disclaimer: string;
  reason: string | null;
}

export async function getLlmLabStatus(): Promise<LlmLabStatus> {
  const response = await fetch(`${API_BASE_URL}/llm-lab/status`, { credentials: 'include' });
  if (!response.ok) {
    throw new Error(`LLM lab status failed: ${response.status}`);
  }
  return response.json();
}

export async function askLlmLab(payload: {
  prompt: string;
  system_prompt?: string;
  max_tokens?: number;
}): Promise<LlmLabAnswer> {
  const response = await fetch(`${API_BASE_URL}/llm-lab/ask`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`LLM lab ask failed: ${response.status}`);
  }
  return response.json();
}

export interface LlmConnectionConfig {
  enabled: boolean;
  mode: string;
  base_url: string;
  model: string;
  api_key_configured: boolean;
  timeout_seconds: number;
  /** Foundation-Sec reasoning hop. Blank = hop off (reasoning roles use the primary). */
  reasoning_base_url: string;
  reasoning_model: string;
  source: 'override' | 'env';
}

/** Deployment endpoint preset (VPS / COE). Pre-fills the form; never auto-saves. */
export interface LlmConnectionPreset {
  id: string;
  label: string;
  description: string;
  mode: string;
  base_url: string;
  model: string;
  reasoning_base_url: string;
  reasoning_model: string;
  timeout_seconds: number;
}

export interface LlmConnectionResponse {
  connection: LlmConnectionConfig;
  supported_modes: string[];
  presets?: LlmConnectionPreset[];
}

export interface LlmConnectionSaveResult {
  saved: boolean;
  validation_errors: string[];
  connection: LlmConnectionConfig;
}

export async function getLlmConnection(): Promise<LlmConnectionResponse> {
  const response = await fetch(`${API_BASE_URL}/settings/llm/connection`, { credentials: 'include' });
  if (!response.ok) {
    throw new Error(`LLM connection load failed: ${response.status}`);
  }
  return response.json();
}

export async function saveLlmConnection(payload: {
  enabled: boolean;
  mode: string;
  base_url: string;
  model: string;
  api_key: string;
  timeout_seconds: number;
  reasoning_base_url: string;
  reasoning_model: string;
}): Promise<LlmConnectionSaveResult> {
  const response = await fetch(`${API_BASE_URL}/settings/llm/connection`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`LLM connection save failed: ${response.status}`);
  }
  return response.json();
}

export async function getProviderSettingsStatus(): Promise<ProviderSettingsStatus> {
  const response = await fetch(`${API_BASE_URL}/settings/providers/status`, { credentials: 'include' });
  if (!response.ok) {
    throw new Error(`Provider settings status failed: ${response.status}`);
  }
  return response.json();
}

export async function checkProviderDraft(payload: ProviderDraftCheckRequest): Promise<ProviderDraftCheckResult> {
  const response = await fetch(`${API_BASE_URL}/settings/providers/check`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Provider check failed: ${response.status}`);
  }
  return response.json();
}

export interface McpConnectionConfig {
  enabled: boolean;
  server_id: string;
  deployment_mode: string;
  discovery_policy: string;
  transport: string;
  auth_method: string;
  url: string;
  bearer_token_configured: boolean;
  timeout_seconds: number;
  saia_tools_enabled: boolean;
  splunk_ai_assistant_mode: string;
  allow_saved_search: boolean;
  execution_enabled: boolean;
  last_check_status?: string | null;
  last_error?: string | null;
  last_technical_detail?: string | null;
  source: 'override' | 'env';
}

export interface McpConnectionResponse {
  connection: McpConnectionConfig;
  supported_deployment_modes: string[];
  supported_discovery_policies: string[];
  supported_transports: string[];
  supported_auth_methods: string[];
}

export interface McpConnectionSaveResult {
  saved: boolean;
  validation_errors: string[];
  connection: McpConnectionConfig;
}

export async function getMcpConnection(): Promise<McpConnectionResponse> {
  const response = await fetch(`${API_BASE_URL}/settings/mcp/connection`, { credentials: 'include' });
  if (!response.ok) {
    throw new Error(`MCP connection load failed: ${response.status}`);
  }
  return response.json();
}

export async function saveMcpConnection(payload: {
  enabled: boolean;
  deployment_mode: string;
  discovery_policy: string;
  transport: string;
  auth_method: string;
  url: string;
  bearer_token: string;
  timeout_seconds: number;
  saia_tools_enabled: boolean;
  splunk_ai_assistant_mode: string;
  allow_saved_search: boolean;
  execution_enabled: boolean;
}): Promise<McpConnectionSaveResult> {
  const response = await fetch(`${API_BASE_URL}/settings/mcp/connection`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`MCP connection save failed: ${response.status}`);
  }
  return response.json();
}

export async function verifyMcpConnection(action: 'validate' | 'test' | 'discover'): Promise<McpConnectionVerificationResult> {
  const response = await fetch(`${API_BASE_URL}/settings/mcp/${action}`, {
    method: 'POST',
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error(`MCP ${action} failed: ${response.status}`);
  }
  return response.json();
}

export interface OtherMcpServerConfig {
  server_id: string;
  display_name: string;
  provider_type: string;
  enabled: boolean;
  transport: string;
  auth_method: string;
  url_configured: boolean;
  command_configured: boolean;
  auth_configured: boolean;
  timeout_seconds: number;
  execution_enabled: boolean;
  last_check_status?: string | null;
  last_error?: string | null;
  last_technical_detail?: string | null;
  discovered_tools: (string | { name: string; description?: string; capability?: string; categories?: string[]; blocked?: boolean; blocked_reason?: string | null })[];
  bearer_token_configured: boolean;
  secrets_returned: false;
}

export interface OtherMcpServersResponse {
  servers: OtherMcpServerConfig[];
  supported_provider_types: string[];
  supported_transports: string[];
  supported_auth_methods: string[];
}

export interface OtherMcpServerSaveResult {
  saved: boolean;
  validation_errors: string[];
  server: OtherMcpServerConfig | null;
}

export async function getOtherMcpServers(): Promise<OtherMcpServersResponse> {
  const response = await fetch(`${API_BASE_URL}/settings/mcp/servers`, { credentials: 'include' });
  if (!response.ok) {
    throw new Error(`MCP servers load failed: ${response.status}`);
  }
  return response.json();
}

export async function saveOtherMcpServer(payload: {
  server_id: string;
  display_name: string;
  provider_type: string;
  enabled: boolean;
  transport: string;
  auth_method: string;
  url: string;
  bearer_token: string;
  timeout_seconds: number;
  execution_enabled: boolean;
}): Promise<OtherMcpServerSaveResult> {
  const response = await fetch(`${API_BASE_URL}/settings/mcp/servers`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`MCP server save failed: ${response.status}`);
  }
  return response.json();
}

export async function deleteOtherMcpServer(serverId: string): Promise<{ deleted: boolean }> {
  const response = await fetch(`${API_BASE_URL}/settings/mcp/servers/${encodeURIComponent(serverId)}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error(`MCP server delete failed: ${response.status}`);
  }
  return response.json();
}

export async function verifyOtherMcpServer(serverId: string, action: 'test' | 'discover'): Promise<{ result: McpConnectionVerificationResult; server: OtherMcpServerConfig | null }> {
  const response = await fetch(`${API_BASE_URL}/settings/mcp/servers/${encodeURIComponent(serverId)}/${action}`, {
    method: 'POST',
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error(`MCP server ${action} failed: ${response.status}`);
  }
  return response.json();
}

export async function checkLlmSettingsDraft(payload: LlmSettingsDraftCheckRequest): Promise<LlmSettingsDraftCheckResult> {
  const response = await fetch(`${API_BASE_URL}/settings/llm/check`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`LLM settings check failed: ${response.status}`);
  }
  return response.json();
}

export async function verifyLlmConnection(action: 'validate' | 'test' | 'models'): Promise<LlmConnectionVerificationResult> {
  const response = await fetch(`${API_BASE_URL}/settings/llm/${action}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`LLM ${action} failed: ${response.status}`);
  }
  return response.json();
}

export async function getSourceProfileSettings(): Promise<SourceProfileSettingsResponse> {
  const response = await fetch(`${API_BASE_URL}/settings/source-profiles`, { credentials: 'include' });
  if (!response.ok) {
    throw new Error(`Source profile settings failed: ${response.status}`);
  }
  return response.json();
}

export async function saveSourceProfileSettings(values: Record<string, string>): Promise<SourceProfileSaveResponse> {
  const response = await fetch(`${API_BASE_URL}/settings/source-profiles`, {
    method: 'PUT',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ values }),
  });
  if (!response.ok) {
    throw new Error(`Source profile save failed: ${response.status}`);
  }
  return response.json();
}

export async function discoverSourceProfilesFromMcp(): Promise<SourceProfileDiscoverResponse> {
  const response = await fetch(`${API_BASE_URL}/settings/source-profiles/discover-from-mcp`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`MCP source discovery failed: ${response.status}`);
  }
  return response.json();
}

export async function getAssetRegistry(): Promise<AssetRegistryResponse> {
  const response = await fetch(`${API_BASE_URL}/settings/asset-registry`, { credentials: 'include' });
  if (!response.ok) {
    throw new Error(`Asset registry load failed: ${response.status}`);
  }
  return response.json();
}


export async function getIocRegistrySettings(): Promise<IocRegistrySettingsResponse> {
  const response = await fetch(`${API_BASE_URL}/settings/ioc-registry`, { credentials: 'include' });
  if (!response.ok) {
    throw new Error(`IOC registry load failed: ${response.status}`);
  }
  return response.json();
}

export async function saveAssetRegistry(assets: AssetRegistryRecord[]): Promise<AssetRegistryResponse> {
  const response = await fetch(`${API_BASE_URL}/settings/asset-registry`, {
    method: 'PUT',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ assets }),
  });
  if (!response.ok) {
    throw new Error(`Asset registry save failed: ${response.status}`);
  }
  return response.json();
}

export async function getKnowledgeMappingSummary(): Promise<KnowledgeMappingSummary> {
  const response = await fetch(`${API_BASE_URL}/knowledge/mapping-summary`, { credentials: 'include' });
  if (!response.ok) throw new Error(`Knowledge mapping summary failed: ${response.status}`);
  return response.json();
}

export interface DetectionCoverage {
  schema_role: string;
  mitre_metadata_role: string;
  technique_count: number;
  covered_count: number;
  gap_count: number;
  coverage: Record<string, string[]>;
  techniques: {
    technique_id: string;
    name: string;
    tactic: string;
    covering_use_cases: string[];
    covered: boolean;
  }[];
  gaps: { technique_id: string; name: string; tactic: string }[];
}

export async function getDetectionCoverage(): Promise<DetectionCoverage> {
  const response = await fetch(`${API_BASE_URL}/knowledge/detection-coverage`, { credentials: 'include' });
  if (!response.ok) throw new Error(`Detection coverage failed: ${response.status}`);
  return response.json();
}

export interface AtlasCoverageGap {
  schema_role: string;
  atlas_source_status: string;
  mitre_metadata_role?: string;
  technique_count: number;
  covered_count: number;
  gap_count: number;
  tactics: Record<string, number>;
  ai_only_tactics: Record<string, number>;
  multi_tactic_technique_count?: number;
  top_techniques_by_case_study_frequency: { technique_id: string; score: number; tactics: string[] }[];
  limitation: string;
}

export async function getAtlasCoverage(): Promise<AtlasCoverageGap> {
  const response = await fetch(`${API_BASE_URL}/knowledge/atlas-coverage`, { credentials: 'include' });
  if (!response.ok) throw new Error(`ATLAS coverage failed: ${response.status}`);
  return response.json();
}

export interface SplLogicCodeAnchor {
  module: string;
  symbol: string;
  line: number;
  path: string;
  display: string;
}

export interface SplLogicEntry {
  logic_id: string;
  layer: string;
  phase: string;
  rule_id: string | null;
  title: string;
  description: string;
  severity: string;
  runtime_active: boolean;
  ui_toggle_allowed: boolean;
  code: SplLogicCodeAnchor;
  triggers_classification: string | null;
  rewrite_step: string | null;
  guard_invariants: string[];
  ui_enabled: boolean;
  ui_note: string;
}

export interface SplOptimizationRegistry {
  schema_version: string;
  generated_at: string;
  phase_status: Record<string, string>;
  ui_toggle_policy: string;
  q04_or_chain_threshold: number;
  entry_count: number;
  layers: Record<string, SplLogicEntry[]>;
  entries: SplLogicEntry[];
}

export async function getSplOptimizationRegistry(): Promise<SplOptimizationRegistry> {
  const response = await fetch(`${API_BASE_URL}/knowledge/spl-optimization-registry`, { credentials: 'include' });
  if (!response.ok) throw new Error(`SPL optimization registry failed: ${response.status}`);
  return response.json();
}

export async function saveSplOptimizationRegistryOverrides(
  overrides: Record<string, { ui_enabled: boolean; ui_note?: string }>,
): Promise<{ saved: Record<string, unknown>; registry: SplOptimizationRegistry }> {
  const response = await fetch(`${API_BASE_URL}/knowledge/spl-optimization-registry/overrides`, {
    method: 'PUT',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ overrides }),
  });
  if (!response.ok) throw new Error(`SPL optimization overrides save failed: ${response.status}`);
  return response.json();
}

export async function getKnowledgeCollections(): Promise<{ collections: KnowledgeCollection[]; count: number }> {
  const response = await fetch(`${API_BASE_URL}/knowledge/collections`, { credentials: 'include' });
  if (!response.ok) throw new Error(`Knowledge collections failed: ${response.status}`);
  return response.json();
}

export async function getKnowledgeDocuments(): Promise<{ documents: KnowledgeDocument[]; count: number }> {
  const response = await fetch(`${API_BASE_URL}/knowledge/documents`, { credentials: 'include' });
  if (!response.ok) throw new Error(`Knowledge documents failed: ${response.status}`);
  return response.json();
}

export async function getKnowledgeEntries(): Promise<{ entries: KnowledgeEntry[]; count: number }> {
  const response = await fetch(`${API_BASE_URL}/knowledge/entries`, { credentials: 'include' });
  if (!response.ok) throw new Error(`Knowledge entries failed: ${response.status}`);
  return response.json();
}

export async function validateKnowledgeImport(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE_URL}/knowledge/import/validate`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`Knowledge import validation failed: ${response.status}`);
  return response.json();
}

export async function testKnowledgeRetrieval(query: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE_URL}/knowledge/retrieval/test?query=${encodeURIComponent(query)}`, { credentials: 'include' });
  if (!response.ok) throw new Error(`Knowledge retrieval test failed: ${response.status}`);
  return response.json();
}

export async function getKnowledgeImportPrompt(params: { collection_id?: string; document_type?: string; environment?: string } = {}): Promise<Record<string, unknown>> {
  const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value)).toString();
  const response = await fetch(`${API_BASE_URL}/knowledge/import/prompt-template${query ? `?${query}` : ''}`, { credentials: 'include' });
  if (!response.ok) throw new Error(`Knowledge import prompt failed: ${response.status}`);
  return response.json();
}

export async function saveKnowledgeDraft(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE_URL}/knowledge/import/save-draft`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`Knowledge save draft failed: ${response.status}`);
  return response.json();
}

export async function publishKnowledgeImport(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE_URL}/knowledge/import/publish`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`Knowledge publish failed: ${response.status}`);
  return response.json();
}

export async function downloadKnowledgeExport(
  artifact: KnowledgeExportArtifact,
  fileFormat: 'json' | 'csv',
): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/knowledge/exports/${artifact}?file_format=${fileFormat}`, {
    credentials: 'include',
  });
  if (!response.ok) throw new Error(`Knowledge export failed: ${response.status}`);
  return response.blob();
}

export async function getDebugTraces(params?: {
  limit?: number;
  entrypoint?: string;
  status?: string;
  since?: string;
}): Promise<DebugTracesResponse> {
  const search = new URLSearchParams();
  if (params?.limit != null) search.set('limit', String(params.limit));
  if (params?.entrypoint) search.set('entrypoint', params.entrypoint);
  if (params?.status) search.set('status', params.status);
  if (params?.since) search.set('since', params.since);
  const query = search.toString();
  const response = await fetch(`${API_BASE_URL}/debug/traces${query ? `?${query}` : ''}`, {
    credentials: 'include',
  });
  if (response.status === 404) throw new Error('Debug API disabled (404)');
  if (response.status === 403) throw new Error('Debug API forbidden for this role (403)');
  if (!response.ok) throw new Error(`Debug traces failed: ${response.status}`);
  return response.json();
}

export async function getDebugTraceTimeline(traceId: string): Promise<DebugTraceTimeline> {
  const response = await fetch(`${API_BASE_URL}/debug/traces/${encodeURIComponent(traceId)}`, {
    credentials: 'include',
  });
  if (response.status === 404) throw new Error('Trace not found (404)');
  if (response.status === 403) throw new Error('Debug API forbidden for this role (403)');
  if (!response.ok) throw new Error(`Debug trace failed: ${response.status}`);
  return response.json();
}

export async function getDebugTraceBundle(traceId: string): Promise<DebugTraceBundle> {
  const response = await fetch(`${API_BASE_URL}/debug/traces/${encodeURIComponent(traceId)}/bundle`, {
    credentials: 'include',
  });
  if (response.status === 404) throw new Error('Trace not found (404)');
  if (response.status === 403) throw new Error('Debug API forbidden for this role (403)');
  if (!response.ok) throw new Error(`Debug bundle failed: ${response.status}`);
  return response.json();
}

export async function getDebugReadiness(): Promise<DebugReadinessResponse> {
  const response = await fetch(`${API_BASE_URL}/debug/readiness`, { credentials: 'include' });
  if (response.status === 404) throw new Error('Debug API disabled (404)');
  if (response.status === 403) throw new Error('Debug API forbidden for this role (403)');
  if (!response.ok) throw new Error(`Debug readiness failed: ${response.status}`);
  return response.json();
}

export async function approveAction(actionId: string): Promise<ActionProposalEnvelope> {
  const response = await fetch(`${API_BASE_URL}/actions/${encodeURIComponent(actionId)}/approve`, {
    method: 'POST',
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error(`Action approval failed: ${response.status}`);
  }
  return response.json();
}

export async function denyAction(actionId: string): Promise<ActionProposalEnvelope> {
  const response = await fetch(`${API_BASE_URL}/actions/${encodeURIComponent(actionId)}/deny`, {
    method: 'POST',
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error(`Action denial failed: ${response.status}`);
  }
  return response.json();
}
