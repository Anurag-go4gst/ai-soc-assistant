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
