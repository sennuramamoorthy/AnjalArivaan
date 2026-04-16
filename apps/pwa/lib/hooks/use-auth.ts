'use client';

import * as React from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/auth-store';
import * as authApi from '@/lib/api/auth';

export function useLogin() {
  const { setUser, setTokens, setLinkedAccounts } = useAuthStore();
  const router = useRouter();

  return useMutation({
    mutationFn: authApi.login,
    onSuccess: async (data) => {
      // Store token first so subsequent API calls are authenticated
      setTokens(data.accessToken);

      // Decode user info from JWT payload (sub, email, role)
      const payload = authApi.decodeTokenPayload(data.accessToken);
      if (payload) {
        setUser({
          id: payload.sub,
          name: payload.email.split('@')[0],
          email: payload.email,
          role: payload.role,
        });
      }

      try {
        const accounts = await authApi.getLinkedAccounts();
        setLinkedAccounts(accounts);
      } catch {
        // Non-fatal — user can link accounts later
      }

      router.push('/dashboard');
    },
  });
}

export function useVerifyMfa() {
  const { setUser, setTokens, setLinkedAccounts } = useAuthStore();
  const router = useRouter();

  return useMutation({
    mutationFn: authApi.verifyMfa,
    onSuccess: async (data) => {
      setTokens(data.accessToken);

      const payload = authApi.decodeTokenPayload(data.accessToken);
      if (payload) {
        setUser({
          id: payload.sub,
          name: payload.email.split('@')[0],
          email: payload.email,
          role: payload.role,
        });
      }

      try {
        const accounts = await authApi.getLinkedAccounts();
        setLinkedAccounts(accounts);
      } catch {
        // Non-fatal
      }
      router.push('/dashboard');
    },
  });
}

export function useLogout() {
  const { logout } = useAuthStore();
  const router = useRouter();

  return useMutation({
    mutationFn: authApi.logout,
    onSettled: () => {
      logout();
      router.push('/login');
    },
  });
}

export function useSetupMfa() {
  return useMutation({
    mutationFn: authApi.setupMfa,
  });
}

export function useVerifyMfaSetup() {
  return useMutation({
    mutationFn: authApi.verifyMfaSetup,
  });
}

// ── Profile ───────────────────────────────────────────────────────────────

export function useProfile() {
  const { accessToken } = useAuthStore();
  return useQuery({
    queryKey: ['profile'],
    queryFn: () => authApi.getProfile(),
    enabled: !!accessToken,
    staleTime: 60 * 1000,
  });
}

export function useUpdateProfile() {
  return useMutation({
    mutationFn: authApi.updateProfile,
  });
}

// ── Signatures ────────────────────────────────────────────────────────────

export function useSignatures(accountId?: string) {
  const { accessToken } = useAuthStore();
  return useQuery({
    queryKey: ['signatures', accountId],
    queryFn: () => authApi.listSignatures(accountId),
    enabled: !!accessToken && !!accountId,
  });
}

/** Returns the default signature for the given account (or undefined). */
export function useDefaultSignature(accountId?: string) {
  const { data: signatures } = useSignatures(accountId);
  return React.useMemo(
    () => signatures?.find((s) => s.isDefault) ?? signatures?.[0] ?? null,
    [signatures],
  );
}

export function useCreateSignature() {
  return useMutation({ mutationFn: authApi.createSignature });
}

export function useUpdateSignature() {
  return useMutation({
    mutationFn: ({ sigId, data }: { sigId: string; data: authApi.UpdateSignaturePayload }) =>
      authApi.updateSignature(sigId, data),
  });
}

export function useDeleteSignature() {
  return useMutation({
    mutationFn: authApi.deleteSignature,
  });
}
