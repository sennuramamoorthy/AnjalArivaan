'use client';

import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from '@/store/auth-store';
import * as searchApi from '@/lib/api/search';

export const searchKeys = {
  all: ['search'] as const,
  hybrid: (params: searchApi.SearchParams) =>
    [...searchKeys.all, 'hybrid', params] as const,
};

interface UseSearchOptions {
  q: string;
  type?: searchApi.SearchDocType;
  limit?: number;
}

/**
 * Hybrid BM25 + vector search over the user's active linked account.
 * Disables itself when the query is empty — the caller is expected to
 * debounce the input (see ``/search`` page).
 */
export function useSearch({ q, type = 'all', limit = 20 }: UseSearchOptions) {
  const { activeAccountId, linkedAccounts } = useAuthStore();
  const accountId = activeAccountId ?? linkedAccounts[0]?.id ?? undefined;
  const trimmed = q.trim();

  return useQuery({
    queryKey: searchKeys.hybrid({
      accountId: accountId ?? '',
      q: trimmed,
      type,
      limit,
    }),
    queryFn: () =>
      searchApi.hybridSearch({
        accountId: accountId!,
        q: trimmed,
        type,
        limit,
      }),
    enabled: !!accountId && trimmed.length >= 2,
    staleTime: 30 * 1000,
  });
}
