'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '@/store/auth-store';
import * as authApi from '@/lib/api/auth';

export const accountKeys = {
  all: ['accounts'] as const,
  linked: () => [...accountKeys.all, 'linked'] as const,
};

/**
 * Fetch linked accounts with full detail (status, lastSyncAt).
 */
export function useLinkedAccounts() {
  return useQuery({
    queryKey: accountKeys.linked(),
    queryFn: authApi.getLinkedAccountDetails,
  });
}

/**
 * Initiate Google OAuth flow — redirects browser to Google consent page.
 */
export function useInitiateLink() {
  return useMutation({
    mutationFn: async () => {
      const callbackUrl = `${window.location.origin}/oauth/callback`;
      return authApi.initiateAccountLink(callbackUrl);
    },
    onSuccess: (data) => {
      // Redirect to Google OAuth consent page
      window.location.href = data.authorizationUrl;
    },
  });
}

/**
 * Complete OAuth flow after Google redirects back with code + state.
 */
export function useCompleteLink() {
  const queryClient = useQueryClient();
  const { setLinkedAccounts } = useAuthStore();

  return useMutation({
    mutationFn: ({ code, state }: { code: string; state: string }) =>
      authApi.completeAccountLink(code, state),
    onSuccess: () => {
      // Invalidate so /settings refetches on landing. Fire-and-forget the store
      // refresh so the mutation resolves immediately and the UI can transition.
      queryClient.invalidateQueries({ queryKey: accountKeys.linked() });
      authApi
        .getLinkedAccounts()
        .then((accounts) => setLinkedAccounts(accounts))
        .catch(() => {
          // Non-fatal — /settings will refetch
        });
    },
  });
}

/**
 * Revoke (unlink) a linked account.
 */
export function useRevokeAccount() {
  const queryClient = useQueryClient();
  const { setLinkedAccounts } = useAuthStore();

  return useMutation({
    mutationFn: authApi.revokeLinkedAccount,
    onSuccess: async () => {
      queryClient.invalidateQueries({ queryKey: accountKeys.linked() });
      try {
        const accounts = await authApi.getLinkedAccounts();
        setLinkedAccounts(accounts);
      } catch {
        // Non-fatal
      }
    },
  });
}
