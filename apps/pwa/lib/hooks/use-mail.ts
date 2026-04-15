'use client';

import { useQuery, useMutation, useQueryClient, useInfiniteQuery } from '@tanstack/react-query';
import { useAuthStore } from '@/store/auth-store';
import * as mailApi from '@/lib/api/mail';

export const mailKeys = {
  all: ['mail'] as const,
  lists: () => [...mailKeys.all, 'list'] as const,
  list: (params: mailApi.ListMailParams) => [...mailKeys.lists(), params] as const,
  thread: (id: string) => [...mailKeys.all, 'thread', id] as const,
  aiSummary: (id: string) => [...mailKeys.all, 'ai-summary', id] as const,
  briefing: (accountId?: string) => [...mailKeys.all, 'briefing', accountId] as const,
};

export function useMailList(params: Omit<mailApi.ListMailParams, 'page'> = {}) {
  const { activeAccountId, linkedAccounts } = useAuthStore();
  // Fall back to the first linked account when activeAccountId is stale/null —
  // otherwise the request goes out with no accountId and the API returns 400.
  const effectiveAccountId =
    params.accountId ?? activeAccountId ?? linkedAccounts[0]?.id ?? undefined;

  return useInfiniteQuery({
    queryKey: mailKeys.list({ ...params, accountId: effectiveAccountId }),
    queryFn: ({ pageParam = 1 }) =>
      mailApi.listMail({
        ...params,
        accountId: effectiveAccountId,
        page: pageParam as number,
      }),
    enabled: !!effectiveAccountId,
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.hasMore ? lastPage.page + 1 : undefined,
  });
}

function useEffectiveAccountId(): string | undefined {
  const { activeAccountId, linkedAccounts } = useAuthStore();
  return activeAccountId ?? linkedAccounts[0]?.id ?? undefined;
}

export function useThread(threadId: string) {
  const accountId = useEffectiveAccountId();
  return useQuery({
    queryKey: [...mailKeys.thread(threadId), accountId],
    queryFn: () => mailApi.getThread(threadId, accountId),
    enabled: !!threadId && !!accountId,
  });
}

export function useAiSummary(threadId: string) {
  const accountId = useEffectiveAccountId();
  return useQuery({
    queryKey: [...mailKeys.aiSummary(threadId), accountId],
    queryFn: () => mailApi.getAiSummary(threadId, accountId),
    enabled: !!threadId && !!accountId,
  });
}

export function useRequestAiDraft(threadId: string) {
  const queryClient = useQueryClient();
  const accountId = useEffectiveAccountId();
  return useMutation({
    mutationFn: () => mailApi.requestAiDraft(threadId, accountId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: mailKeys.thread(threadId) });
    },
  });
}

export function useMarkRead() {
  const queryClient = useQueryClient();
  const accountId = useEffectiveAccountId();
  return useMutation({
    mutationFn: (id: string) => mailApi.markRead(id, accountId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: mailKeys.lists() });
    },
  });
}

/**
 * Mark every message in a thread as read. Matches Gmail's "open = read"
 * behavior — the detail page fires this on mount.
 */
export function useMarkThreadRead() {
  const queryClient = useQueryClient();
  const accountId = useEffectiveAccountId();
  return useMutation({
    mutationFn: (threadId: string) => mailApi.markThreadRead(threadId, accountId),
    onSuccess: (_data, threadId) => {
      queryClient.invalidateQueries({ queryKey: mailKeys.lists() });
      queryClient.invalidateQueries({ queryKey: mailKeys.thread(threadId) });
    },
  });
}

export function useDailyBriefing() {
  const { activeAccountId } = useAuthStore();
  return useQuery({
    queryKey: mailKeys.briefing(activeAccountId ?? undefined),
    queryFn: () => mailApi.getDailyBriefing(activeAccountId ?? undefined),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
