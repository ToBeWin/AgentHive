import { type AuthTokenResponse, apiGet, apiPost } from "./core";

export interface SetupStatusResponse {
  initialized: boolean;
  tenant_count: number;
  setup_available: boolean;
  message: string | null;
  diagnostics: Record<string, unknown>;
}

export interface LogoutResponse {
  message: string;
}

export interface BootstrapRequest {
  tenant_name: string;
  tenant_slug: string;
  admin_email: string;
  admin_password: string;
  admin_full_name: string;
}

export interface BootstrapResponse {
  tenant_id: string;
  admin_user_id: string;
  message: string;
  auth: AuthTokenResponse;
}

export interface LoginRequest {
  tenant_slug: string;
  email: string;
  password: string;
}

export const authApi = {
  getSetupStatus: () => apiGet<SetupStatusResponse>("/api/v1/auth/setup-status", { token: null }),
  bootstrap: (payload: BootstrapRequest) =>
    apiPost<BootstrapResponse, BootstrapRequest>("/api/v1/auth/bootstrap", payload, { token: null }),
  login: (payload: LoginRequest) =>
    apiPost<AuthTokenResponse, LoginRequest>("/api/v1/auth/login", payload, { token: null }),
  refresh: () => apiPost<AuthTokenResponse, Record<string, never>>("/api/v1/auth/refresh", {}),
  logout: () => apiPost<LogoutResponse, Record<string, never>>("/api/v1/auth/logout", {}),
};
