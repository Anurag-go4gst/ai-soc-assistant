export const DEFAULT_API_BASE_URL = '/api';

export function getApiBaseUrl() {
  const configured = import.meta.env.VITE_API_BASE_URL as string | undefined;
  if (configured) {
    return configured.replace(/\/$/, '');
  }
  return window.location.port === '3010' ? 'http://localhost:8010/api' : DEFAULT_API_BASE_URL;
}
