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
  const response = await fetch(`${API_BASE_URL}/demo/scenarios`, { credentials: 'include' });
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

export async function approveEcAction(actionId: string): Promise<EcActionRecord> {
  const response = await fetch(`${API_BASE_URL}/demo/ec-actions/${encodeURIComponent(actionId)}/approve`, {
    method: 'POST',
    credentials: 'include',
  });
  return readJson(response, 'EC action approve');
}

export async function executeEcAction(actionId: string): Promise<EcActionRecord> {
  const response = await fetch(`${API_BASE_URL}/demo/ec-actions/${encodeURIComponent(actionId)}/execute`, {
    method: 'POST',
    credentials: 'include',
  });
  return readJson(response, 'EC action execute');
}

export async function verifyEcAction(actionId: string): Promise<EcActionRecord> {
  const response = await fetch(`${API_BASE_URL}/demo/ec-actions/${encodeURIComponent(actionId)}/verify`, {
    method: 'POST',
    credentials: 'include',
  });
  return readJson(response, 'EC action verify');
}
