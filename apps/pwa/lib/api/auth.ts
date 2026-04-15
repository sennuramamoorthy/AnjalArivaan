import { apiClient } from './client';

export interface LoginRequest {
  email: string;
  password: string;
  mfaCode?: string;
}

/**
 * After envelope unwrapping, the identity service returns:
 *   { accessToken: string, refreshToken: string }
 *
 * When MFA is required, the response has success=false with error code MFA_REQUIRED.
 * The ApiError will be thrown, and the login form catches it.
 */
export interface LoginResponse {
  accessToken: string;
  refreshToken: string;
}

export interface MfaVerifyRequest {
  email: string;
  password: string;
  mfaCode: string;
}

export interface MfaSetupResponse {
  secret: string;
  qrCodeUri: string;
  backupCodes: string[];
}

export interface MfaSetupVerifyRequest {
  token: string;
}

export interface RefreshTokenResponse {
  accessToken: string;
  refreshToken: string;
}

export interface LinkedAccount {
  id: string;
  googleEmail: string;
  workspaceDomain: string;
  avatarUrl?: string;
  displayName?: string;
}

/**
 * Decode user info from a JWT access token (no verification — just payload).
 * The identity service embeds { sub, role, email } in the JWT.
 */
export function decodeTokenPayload(token: string): {
  sub: string;
  role: string;
  email: string;
} | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1]));
    return { sub: payload.sub, role: payload.role, email: payload.email };
  } catch {
    return null;
  }
}

export function login(data: LoginRequest) {
  return apiClient.post<LoginResponse>('/api/v1/auth/login', data);
}

export function verifyMfa(data: MfaVerifyRequest) {
  // MFA is verified by re-posting login with the mfaCode included
  return apiClient.post<LoginResponse>('/api/v1/auth/login', data);
}

export function refreshToken(token: string) {
  return apiClient.post<RefreshTokenResponse>('/api/v1/auth/refresh', {
    refreshToken: token,
  });
}

export function logout(token: string) {
  return apiClient.post<void>('/api/v1/auth/logout', {
    refreshToken: token,
  });
}

export function setupMfa() {
  return apiClient.post<MfaSetupResponse>('/api/v1/auth/mfa/setup');
}

export function verifyMfaSetup(data: MfaSetupVerifyRequest) {
  return apiClient.post<{ success: boolean }>('/api/v1/auth/mfa/verify-setup', data);
}

export function getLinkedAccounts() {
  return apiClient.get<LinkedAccount[]>('/api/v1/accounts/linked');
}

// ── Account Linking ─────────────────────────────────────────────────────────

export interface LinkedAccountDetail extends LinkedAccount {
  status: 'ACTIVE' | 'REVOKED' | 'SYNC_ERROR';
  lastSyncAt: string | null;
  createdAt: string | null;
}

export interface InitiateLinkResponse {
  authorizationUrl: string;
  state: string;
}

export function getLinkedAccountDetails() {
  return apiClient.get<LinkedAccountDetail[]>('/api/v1/accounts/linked');
}

export function initiateAccountLink(redirectUri: string) {
  return apiClient.post<InitiateLinkResponse>('/api/v1/accounts/link/initiate', {
    redirectUri,
  });
}

export function completeAccountLink(code: string, state: string) {
  return apiClient.get<LinkedAccountDetail>(
    `/api/v1/accounts/link/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`
  );
}

export function revokeLinkedAccount(accountId: string) {
  return apiClient.delete<{ success: boolean }>(`/api/v1/accounts/linked/${accountId}`);
}
