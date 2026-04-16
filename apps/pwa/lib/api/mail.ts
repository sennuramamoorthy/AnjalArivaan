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

/** Gmail system folder slugs accepted by GET /api/v1/mail */
export type MailFolder =
  | 'inbox'
  | 'sent'
  | 'drafts'
  | 'trash'
  | 'starred'
  | 'important'
  | 'all';

export type MailSort = 'newest' | 'oldest' | 'sender' | 'subject';

export interface ListMailParams {
  accountId?: string;
  folder?: MailFolder;
  filter?: 'all' | 'urgent' | 'unread' | 'government';
  search?: string;
  sort?: MailSort;
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
      folder: params.folder ?? 'inbox',
      filter: params.filter,
      search: params.search,
      sort: params.sort ?? 'newest',
      page: params.page ?? 1,
      pageSize: params.pageSize ?? 20,
    },
  });
}

export function getMail(id: string, accountId?: string) {
  return apiClient.get<EmailSummary>(`/api/v1/mail/${id}`, { params: { accountId } });
}

export function getThread(threadId: string, accountId?: string) {
  return apiClient.get<EmailThread>(`/api/v1/mail/threads/${threadId}`, {
    params: { accountId },
  });
}

export function getAiSummary(threadId: string, accountId?: string) {
  return apiClient.get<AiSummary>(`/api/v1/mail/threads/${threadId}/ai-summary`, {
    params: { accountId },
  });
}

export function requestAiDraft(
  threadId: string,
  accountId?: string,
  instructions?: string,
  context?: { subject?: string; to?: string },
) {
  return apiClient.post<AiDraft>(
    `/api/v1/mail/threads/${threadId}/ai-draft`,
    {
      instructions: instructions ?? '',
      ...(context?.subject ? { subject: context.subject } : {}),
      ...(context?.to ? { to: context.to } : {}),
    },
    { params: { accountId } },
  );
}

export function markRead(id: string, accountId?: string) {
  return apiClient.patch<void>(`/api/v1/mail/${id}/read`, undefined, {
    params: { accountId },
  });
}

export type ComposeMode = 'reply' | 'replyAll' | 'forward' | 'compose';

export interface SendReplyPayload {
  to: string[];
  cc?: string[];
  bcc?: string[];
  subject: string;
  bodyText: string;
  bodyHtml?: string;
  mode: ComposeMode;
  inReplyTo?: string;
  references?: string[];
}

export function sendReply(
  threadId: string,
  payload: SendReplyPayload,
  accountId?: string,
) {
  return apiClient.post<{ success: boolean; messageId?: string; threadId?: string }>(
    `/api/v1/mail/threads/${threadId}/send`,
    payload,
    { params: { accountId } },
  );
}

export function markThreadRead(threadId: string, accountId?: string) {
  return apiClient.patch<{ success: boolean; updated: number }>(
    `/api/v1/mail/threads/${threadId}/read`,
    undefined,
    { params: { accountId } },
  );
}

export function getDailyBriefing(accountId?: string) {
  return apiClient.get<{ content: string; generatedAt: string }>('/api/v1/briefing/daily', {
    params: { accountId },
  });
}
