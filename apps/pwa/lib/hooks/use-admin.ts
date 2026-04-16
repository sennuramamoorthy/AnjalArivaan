'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as adminApi from '@/lib/api/admin';

export const adminKeys = {
  all: ['admin'] as const,
  users: (params: Parameters<typeof adminApi.listUsers>[0]) =>
    [...adminKeys.all, 'users', params] as const,
  auditLogs: (params: Parameters<typeof adminApi.listAuditLogs>[0]) =>
    [...adminKeys.all, 'audit-logs', params] as const,
  auditEvent: (id: string) => [...adminKeys.all, 'audit-event', id] as const,
  systemHealth: () => [...adminKeys.all, 'system-health'] as const,
};

export function useAdminUsers(params: Parameters<typeof adminApi.listUsers>[0] = {}) {
  return useQuery({
    queryKey: adminKeys.users(params),
    queryFn: () => adminApi.listUsers(params),
  });
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: adminApi.CreateUserPayload) => adminApi.createUser(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: adminKeys.all });
    },
  });
}

export function useSuspendUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => adminApi.suspendUser(userId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: adminKeys.all });
    },
  });
}

export function useActivateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => adminApi.activateUser(userId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: adminKeys.all });
    },
  });
}

export function useAuditLogs(params: Parameters<typeof adminApi.listAuditLogs>[0] = {}) {
  return useQuery({
    queryKey: adminKeys.auditLogs(params),
    queryFn: () => adminApi.listAuditLogs(params),
  });
}

export function useSystemHealth() {
  return useQuery({
    queryKey: adminKeys.systemHealth(),
    queryFn: () => adminApi.getSystemHealth(),
    refetchInterval: 30_000,
  });
}
