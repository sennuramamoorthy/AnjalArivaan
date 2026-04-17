import { apiClient } from './client';

export type SearchDocType = 'mail' | 'attachment' | 'all';

export interface SearchHit {
  id: string;
  score: number;
  sources: string[];
  type: 'mail' | 'attachment';
  subject?: string | null;
  filename?: string | null;
  snippet: string;
}

export interface SearchResponse {
  results: SearchHit[];
  accountId: string;
  query: string;
  type: SearchDocType;
}

export interface SearchParams {
  accountId: string;
  q: string;
  type?: SearchDocType;
  limit?: number;
}

export function hybridSearch(params: SearchParams) {
  return apiClient.get<SearchResponse>('/api/v1/search', {
    params: {
      accountId: params.accountId,
      q: params.q,
      type: params.type ?? 'all',
      limit: params.limit ?? 20,
    },
  });
}
