/**
 * Auth use-cases the UI calls into. Thin orchestration on top of /lib/api.
 */
import { request, tokenStore } from "@/lib/api";
import type { MfaSetup, TokenPair, UserOut } from "@/types/api";

export async function signup(payload: {
  email: string;
  password: string;
  full_name: string;
  designation?: string | null;
  phone_e164?: string | null;
}): Promise<UserOut> {
  return request<UserOut>("/api/v1/auth/signup", {
    method: "POST",
    body: payload,
    auth: false,
  });
}

export async function login(payload: {
  email: string;
  password: string;
  totp?: string | null;
}): Promise<TokenPair> {
  const pair = await request<TokenPair>("/api/v1/auth/login", {
    method: "POST",
    body: payload,
    auth: false,
  });
  tokenStore.set(pair);
  return pair;
}

export async function logout(): Promise<void> {
  tokenStore.clear();
}

export async function me(): Promise<UserOut> {
  return request<UserOut>("/api/v1/auth/me");
}

export async function startMfa(): Promise<MfaSetup> {
  return request<MfaSetup>("/api/v1/auth/mfa/setup", { method: "POST" });
}

export async function verifyMfa(totp: string): Promise<{ verified: boolean }> {
  return request<{ verified: boolean }>("/api/v1/auth/mfa/verify", {
    method: "POST",
    body: { totp },
  });
}

export function isAuthenticated(): boolean {
  return tokenStore.getAccess() !== null;
}
