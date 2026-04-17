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

/**
 * Hard-delete a *revoked* linked account. The backend enforces that the
 * account must already be in REVOKED state (so Vault cleanup has run);
 * calling this on an ACTIVE account returns 409 ACCOUNT_NOT_REVOKED.
 */
export function permanentlyDeleteLinkedAccount(accountId: string) {
  return apiClient.delete<{ success: boolean }>(
    `/api/v1/accounts/linked/${accountId}/permanent`
  );
}

/**
 * Trigger a manual Gmail sync for a linked account. The backend runs the
 * sync_service in the background and returns immediately; poll linked
 * account details afterwards to see the updated `lastSyncAt`.
 */
export function syncLinkedAccount(accountId: string) {
  return apiClient.post<{ success: boolean; syncedCount?: number }>(
    `/api/v1/accounts/linked/${accountId}/sync`
  );
}

// ── User Profile ────────────────────────────────────────────────────────────

export interface UserProfile {
  id: string;
  email: string;
  role: string;
  status: string;
  mfaEnabled: boolean;
  name: string | null;
  designation: string | null;
  department: string | null;
  responsibilities: string | null;
}

export interface UpdateProfilePayload {
  designation?: string;
  department?: string;
  responsibilities?: string;
  phone?: string;
}

export function getProfile() {
  return apiClient.get<UserProfile>('/api/v1/users/me');
}

export function updateProfile(data: UpdateProfilePayload) {
  return apiClient.patch<UserProfile>('/api/v1/users/me', data);
}

// ── Signatures ──────────────────────────────────────────────────────────────

export interface Signature {
  id: string;
  accountId: string;
  name: string;
  htmlTemplate: string;
  isDefault: boolean;
  createdAt: string | null;
}

export interface CreateSignaturePayload {
  accountId: string;
  name: string;
  htmlTemplate: string;
  isDefault?: boolean;
}

export interface UpdateSignaturePayload {
  name?: string;
  htmlTemplate?: string;
  isDefault?: boolean;
}

export function listSignatures(accountId?: string) {
  return apiClient.get<Signature[]>('/api/v1/users/me/signatures', {
    params: accountId ? { accountId } : undefined,
  });
}

export function createSignature(data: CreateSignaturePayload) {
  return apiClient.post<Signature>('/api/v1/users/me/signatures', data);
}

export function updateSignature(sigId: string, data: UpdateSignaturePayload) {
  return apiClient.put<Signature>(`/api/v1/users/me/signatures/${sigId}`, data);
}

export function deleteSignature(sigId: string) {
  return apiClient.delete<{ deleted: boolean }>(`/api/v1/users/me/signatures/${sigId}`);
}
