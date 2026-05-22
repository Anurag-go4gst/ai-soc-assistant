import { getApiBaseUrl } from '@/lib/runtimeMode';
import type { AuthResponse, HealthResponse, PlaceholderResponse } from '../types/api';

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
