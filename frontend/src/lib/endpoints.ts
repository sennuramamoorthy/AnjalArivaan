/**
 * Typed API client — one method per backend endpoint.
 * Pattern: Facade over fetch; also keeps all URL paths in one place so
 * route changes don't scatter across 20 components.
 */
import { request } from "./api";
import type {
  BriefingResponse,
  ContactOut,
  DraftReplyResponse,
  LinkedAccountOut,
  MailMessageOut,
  MailThreadOut,
  MeetingOut,
  MfaSetup,
  OutOfOfficeOut,
  ResourceOut,
  SearchHit,
  SignatureOut,
  TaskOut,
  TaskState,
  TokenPair,
  TravelPlanOut,
  UserOut,
} from "@/types/api";

// ---------- auth ---------------------------------------------------------
export const authApi = {
  signup: (payload: {
    email: string;
    password: string;
    full_name: string;
    designation?: string;
    department?: string;
  }) =>
    request<UserOut>("/api/v1/auth/signup", {
      method: "POST",
      body: payload,
      auth: false,
    }),
  login: (payload: { email: string; password: string; totp?: string }) =>
    request<TokenPair>("/api/v1/auth/login", {
      method: "POST",
      body: payload,
      auth: false,
    }),
  me: () => request<UserOut>("/api/v1/auth/me"),
  setupMfa: () =>
    request<MfaSetup>("/api/v1/auth/mfa/setup", { method: "POST" }),
  verifyMfa: (totp: string) =>
    request<{ verified: boolean }>("/api/v1/auth/mfa/verify", {
      method: "POST",
      body: { totp },
    }),
};

// ---------- accounts -----------------------------------------------------
export const accountsApi = {
  list: () => request<LinkedAccountOut[]>("/api/v1/accounts"),
  startOAuth: () =>
    request<{ authorization_url: string; state: string }>(
      "/api/v1/accounts/oauth/start",
      { method: "POST" }
    ),
  revoke: (id: number) =>
    request<void>(`/api/v1/accounts/${id}/revoke`, { method: "POST" }),
};

// ---------- mail ---------------------------------------------------------
export const mailApi = {
  list: (params: { account_id: number; is_urgent?: boolean; size?: number }) =>
    request<MailMessageOut[]>("/api/v1/mail", { query: params }),
  thread: (threadId: string, account_id: number) =>
    request<MailThreadOut>(`/api/v1/mail/threads/${threadId}`, {
      query: { account_id },
    }),
  draftReply: (payload: {
    account_id: number;
    thread_id: string;
    tone?: "formal" | "friendly" | "concise";
    instructions?: string;
  }) =>
    request<DraftReplyResponse>("/api/v1/mail/draft-reply", {
      method: "POST",
      body: payload,
    }),
  summarizeThread: (payload: { account_id: number; thread_id: string }) =>
    request<{ summary: string; model: string }>(
      "/api/v1/mail/summarize-thread",
      { method: "POST", body: payload }
    ),
};

// ---------- meetings -----------------------------------------------------
export const meetingsApi = {
  list: (params: { account_id: number; from?: string; to?: string }) =>
    request<MeetingOut[]>("/api/v1/meetings", { query: params }),
  create: (payload: {
    account_id: number;
    title: string;
    description?: string;
    start_at: string;
    end_at: string;
    attendees: string[];
    resource_ids?: number[];
  }) =>
    request<MeetingOut>("/api/v1/meetings", { method: "POST", body: payload }),
  cancel: (id: number, account_id: number) =>
    request<MeetingOut>(`/api/v1/meetings/${id}/cancel`, {
      method: "POST",
      query: { account_id },
    }),
};

export const resourcesApi = {
  list: () => request<ResourceOut[]>("/api/v1/resources"),
  create: (payload: Omit<ResourceOut, "id">) =>
    request<ResourceOut>("/api/v1/resources", { method: "POST", body: payload }),
};

// ---------- tasks --------------------------------------------------------
export const tasksApi = {
  list: (params: {
    account_id: number;
    state?: TaskState;
    assignee_email?: string;
  }) => request<TaskOut[]>("/api/v1/tasks", { query: params }),
  create: (payload: {
    account_id: number;
    title: string;
    description?: string;
    assignee_email: string;
    due_at?: string;
  }) =>
    request<TaskOut>("/api/v1/tasks", { method: "POST", body: payload }),
  transition: (id: number, state: TaskState) =>
    request<TaskOut>(`/api/v1/tasks/${id}/transition`, {
      method: "POST",
      body: { state },
    }),
};

// ---------- travel -------------------------------------------------------
export const travelApi = {
  list: (params: { account_id: number }) =>
    request<TravelPlanOut[]>("/api/v1/travel", { query: params }),
  create: (payload: {
    account_id: number;
    destination: string;
    purpose: string;
    depart_at: string;
    return_at: string;
    mode: string;
  }) =>
    request<TravelPlanOut>("/api/v1/travel", { method: "POST", body: payload }),
  submit: (id: number) =>
    request<TravelPlanOut>(`/api/v1/travel/${id}/submit`, { method: "POST" }),
  approve: (id: number) =>
    request<TravelPlanOut>(`/api/v1/travel/${id}/approve`, { method: "POST" }),
  reject: (id: number, reason: string) =>
    request<TravelPlanOut>(`/api/v1/travel/${id}/reject`, {
      method: "POST",
      body: { reason },
    }),
};

// ---------- contacts -----------------------------------------------------
export const contactsApi = {
  list: (account_id: number) =>
    request<ContactOut[]>("/api/v1/contacts", { query: { account_id } }),
  create: (account_id: number, payload: Omit<ContactOut, "id">) =>
    request<ContactOut>("/api/v1/contacts", {
      method: "POST",
      query: { account_id },
      body: payload,
    }),
  createSignature: (
    account_id: number,
    payload: { label: string; html_body: string; is_default?: boolean }
  ) =>
    request<SignatureOut>("/api/v1/contacts/signature", {
      method: "POST",
      query: { account_id },
      body: payload,
    }),
  setDefaultSignature: (account_id: number, signature_id: number) =>
    request<SignatureOut>(
      `/api/v1/contacts/signature/${signature_id}/default`,
      { method: "POST", query: { account_id } }
    ),
  setOoo: (
    account_id: number,
    payload: {
      enabled: boolean;
      subject: string;
      body: string;
      start_at?: string;
      end_at?: string;
    }
  ) =>
    request<OutOfOfficeOut>("/api/v1/contacts/ooo", {
      method: "POST",
      query: { account_id },
      body: payload,
    }),
};

// ---------- briefing / search -------------------------------------------
export const briefingApi = {
  today: (account_id: number) =>
    request<BriefingResponse>("/api/v1/briefing/today", {
      query: { account_id },
    }),
};

export const searchApi = {
  query: (params: {
    q: string;
    account_id: number;
    sources?: string;
    size?: number;
  }) => request<SearchHit[]>("/api/v1/search", { query: params }),
};
