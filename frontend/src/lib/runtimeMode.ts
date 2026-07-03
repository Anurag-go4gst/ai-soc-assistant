export const DEFAULT_API_BASE_URL = '/api';

export function getApiBaseUrl() {
  const configured = import.meta.env.VITE_API_BASE_URL as string | undefined;
  if (configured) {
    return configured.replace(/\/$/, '');
  }
  return DEFAULT_API_BASE_URL;
}
