import { getApiBaseUrl } from '@/lib/runtimeMode';
import type { ExperienceCenterResponse, EcActionRecord, EcScenarioSummary } from '@/components/ec/types';

const API_BASE_URL = getApiBaseUrl();

async function readJson<T>(response: Response, label: string): Promise<T> {
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `${label} failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function listEcScenarios(): Promise<{ scenarios: EcScenarioSummary[]; count: number }> {
  const response = await fetch(`${API_BASE_URL}/demo/experience-center/scenarios`, { credentials: 'include' });
  return readJson(response, 'EC scenario list');
}

export async function runEcScenario(scenarioId: string, sessionId?: string): Promise<ExperienceCenterResponse> {
  const query = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : '';
  const response = await fetch(`${API_BASE_URL}/demo/scenarios/${encodeURIComponent(scenarioId)}/run${query}`, {
    method: 'POST',
    credentials: 'include',
  });
  return readJson(response, 'EC scenario run');
}

export async function followUpEcScenario(
  scenarioId: string,
  followUpId: string,
  sessionId?: string,
): Promise<ExperienceCenterResponse> {
  const response = await fetch(`${API_BASE_URL}/demo/scenarios/${encodeURIComponent(scenarioId)}/follow-up`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ follow_up_id: followUpId, session_id: sessionId ?? null }),
  });
  return readJson(response, 'EC follow-up');
}

function actionBody(action?: EcActionRecord | null, draft?: Record<string, unknown> | null) {
  return JSON.stringify({
    draft: draft ?? null,
    action: action ?? null,
  });
}

export async function prepareEcAction(body: {
  kind: string;
  label: string;
  scenario_id: string;
  session_id?: string | null;
  extra?: Record<string, unknown> | null;
}): Promise<EcActionRecord> {
  const response = await fetch(`${API_BASE_URL}/demo/ec-actions/prepare`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return readJson(response, 'EC action prepare');
}

export async function approveEcAction(actionId: string, action?: EcActionRecord): Promise<EcActionRecord> {
  const response = await fetch(`${API_BASE_URL}/demo/ec-actions/${encodeURIComponent(actionId)}/approve`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: actionBody(action),
  });
  return readJson(response, 'EC action approve');
}

export async function executeEcAction(
  actionId: string,
  draft?: Record<string, unknown> | null,
  action?: EcActionRecord,
): Promise<EcActionRecord> {
  const response = await fetch(`${API_BASE_URL}/demo/ec-actions/${encodeURIComponent(actionId)}/execute`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: actionBody(action, draft),
  });
  return readJson(response, 'EC action execute');
}

export async function verifyEcAction(actionId: string, action?: EcActionRecord): Promise<EcActionRecord> {
  const response = await fetch(`${API_BASE_URL}/demo/ec-actions/${encodeURIComponent(actionId)}/verify`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: actionBody(action),
  });
  return readJson(response, 'EC action verify');
}

export async function resolveEcQuery(query: string): Promise<{
  query: string;
  scenario_id: string | null;
  score: number;
  matched: boolean;
}> {
  const response = await fetch(`${API_BASE_URL}/demo/experience-center/resolve-query`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });
  return readJson(response, 'EC resolve query');
}
