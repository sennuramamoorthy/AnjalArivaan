import { apiClient } from './client';

export type UrgencyLevel = 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface EmailSender {
  name: string;
  email: string;
  avatarUrl?: string;
}

export interface EmailSummary {
  id: string;
  threadId: string;
  from: EmailSender;
  subject: string;
  preview: string;
  receivedAt: string;
  isRead: boolean;
  urgencyLevel: UrgencyLevel;
  hasAttachment: boolean;
  linkedAccountId: string;
  linkedAccount: string;
  labels: string[];
}

export interface EmailMessage {
  id: string;
  from: EmailSender;
  to: EmailSender[];
  cc?: EmailSender[];
  subject: string;
  bodyHtml: string;
  bodyText: string;
  receivedAt: string;
  isRead: boolean;
  hasAttachment: boolean;
  attachments?: Array<{
    id: string;
    filename: string;
    mimeType: string;
    sizeBytes: number;
  }>;
}

export interface EmailThread {
  id: string;
  subject: string;
  messages: EmailMessage[];
  urgencyLevel: UrgencyLevel;
  linkedAccount: string;
}

export interface AiDraft {
  draftText: string;
  modelId: string;
  promptTemplateId: string;
  retrievedChunkCount: number;
  contextSources: Array<{
    type: 'email' | 'document';
    id: string;
    snippet: string;
  }>;
}

export interface AiSummary {
  summary: string;
  keyPoints: string[];
  urgencyReason?: string;
  modelId: string;
  generatedAt: string;
  retrievedChunkCount: number;
}

export interface ListMailParams {
  accountId?: string;
  filter?: 'all' | 'urgent' | 'unread' | 'government';
  search?: string;
  page?: number;
  pageSize?: number;
}

export interface ListMailResponse {
  emails: EmailSummary[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}

export function listMail(params: ListMailParams = {}) {
  return apiClient.get<ListMailResponse>('/api/v1/mail', {
    params: {
      accountId: params.accountId,
      filter: params.filter,
      search: params.search,
      page: params.page ?? 1,
      pageSize: params.pageSize ?? 20,
    },
  });
}

export function getMail(id: string) {
  return apiClient.get<EmailSummary>(`/api/v1/mail/${id}`);
}

export function getThread(threadId: string) {
  return apiClient.get<EmailThread>(`/api/v1/mail/threads/${threadId}`);
}

export function getAiSummary(threadId: string) {
  return apiClient.get<AiSummary>(`/api/v1/mail/threads/${threadId}/ai-summary`);
}

export function requestAiDraft(threadId: string) {
  return apiClient.post<AiDraft>(`/api/v1/mail/threads/${threadId}/ai-draft`);
}

export function markRead(id: string) {
  return apiClient.patch<void>(`/api/v1/mail/${id}/read`);
}

export function getDailyBriefing(accountId?: string) {
  return apiClient.get<{ content: string; generatedAt: string }>('/api/v1/briefing/daily', {
    params: { accountId },
  });
}
