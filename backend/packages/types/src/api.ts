export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
  meta?: {
    page?: number;
    pageSize?: number;
    total?: number;
    traceId: string;
  };
}

export interface PaginationQuery {
  page?: number;
  pageSize?: number;
  cursor?: string;
}

// ── Auth API ──────────────────────────────────────────────────────────────────
export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
}

export interface LoginRequest {
  email: string;
  password: string;
  mfaCode?: string;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
}

export interface MfaSetupResponse {
  secret: string;
  qrCodeUri: string;
  backupCodes: string[];
}

// ── Mail API ──────────────────────────────────────────────────────────────────
export interface MailListQuery extends PaginationQuery {
  accountId?: string;
  urgencyLevel?: string;
  isRead?: boolean;
  searchQuery?: string;
}

export interface AiDraftRequest {
  mailId: string;
  threadId: string;
  instructions?: string;
}

export interface AiDraftResponse {
  draft: string;
  sources: Array<{ chunkId: string; excerpt: string; score: number }>;
  modelId: string;
  promptTemplateId: string;
  traceId: string;
}
