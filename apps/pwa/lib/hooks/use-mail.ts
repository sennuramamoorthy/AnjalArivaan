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
  const { activeAccountId } = useAuthStore();

  return useInfiniteQuery({
    queryKey: mailKeys.list({ ...params, accountId: params.accountId ?? activeAccountId ?? undefined }),
    queryFn: ({ pageParam = 1 }) =>
      mailApi.listMail({
        ...params,
        accountId: params.accountId ?? activeAccountId ?? undefined,
        page: pageParam as number,
      }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.hasMore ? lastPage.page + 1 : undefined,
  });
}

export function useThread(threadId: string) {
  return useQuery({
    queryKey: mailKeys.thread(threadId),
    queryFn: () => mailApi.getThread(threadId),
    enabled: !!threadId,
  });
}

export function useAiSummary(threadId: string) {
  return useQuery({
    queryKey: mailKeys.aiSummary(threadId),
    queryFn: () => mailApi.getAiSummary(threadId),
    enabled: !!threadId,
  });
}

export function useRequestAiDraft(threadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => mailApi.requestAiDraft(threadId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: mailKeys.thread(threadId) });
    },
  });
}

export function useMarkRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: mailApi.markRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: mailKeys.lists() });
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
