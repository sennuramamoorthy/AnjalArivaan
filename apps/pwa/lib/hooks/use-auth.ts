'use client';

import { useMutation } from '@tanstack/react-query';
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
