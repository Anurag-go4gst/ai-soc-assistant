import { getApiBaseUrl } from '@/lib/runtimeMode';
import type { AuthResponse, HealthResponse, KnowledgeCollection, KnowledgeDocument, KnowledgeEntry, PlaceholderResponse, ProviderDraftCheckRequest, ProviderDraftCheckResult, ProviderSettingsStatus, SettingsStatus } from '../types/api';

const API_BASE_URL = getApiBaseUrl();

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

export async function sendChatMessage(message: string): Promise<PlaceholderResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ message }),
  });
  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.status}`);
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
