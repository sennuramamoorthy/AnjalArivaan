import { apiClient } from './client';

/**
 * Admin API — wraps /api/v1/admin/* endpoints. All calls require the caller
 * to hold SUPER_ADMIN or DEPT_ADMIN role (enforced server-side).
 */

export type UserRole =
  | 'SUPER_ADMIN'
  | 'DEPT_ADMIN'
  | 'VC'
  | 'REGISTRAR'
  | 'DEAN'
  | 'HOD'
  | 'STAFF'
  | 'USER';
export type UserStatus = 'ACTIVE' | 'SUSPENDED' | 'PENDING_VERIFICATION' | 'PENDING';

export interface AdminUser {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  status: UserStatus;
  mfaEnabled: boolean;
  createdAt: string;
}

export interface AuditEvent {
  id: string;
  actor: string;
  action: string;
  target?: string;
  before?: Record<string, unknown> | null;
  after?: Record<string, unknown> | null;
  /** Backend field — matches the `audit_events.ip_address` column. */
  ipAddress?: string | null;
  userAgent?: string | null;
  /** Backend field — the timestamp column is named `ts`. */
  ts: string;
}

export interface SystemHealth {
  database: 'ok' | 'unavailable';
  redis: 'ok' | 'unavailable';
  outboxPending: number;
  lastSyncAt: string | null;
}

export interface Paginated<T, Key extends string> {
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
  // `events` or `users` depending on endpoint — typed via generic key.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [k: string]: any;
}

// ── Users ────────────────────────────────────────────────────────────────────

export function listUsers(params: {
  role?: UserRole;
  status?: UserStatus;
  page?: number;
  pageSize?: number;
} = {}) {
  return apiClient.get<{
    users: AdminUser[];
    total: number;
    page: number;
    pageSize: number;
    hasMore: boolean;
  }>('/api/v1/admin/users', {
    params: {
      role: params.role,
      status: params.status,
      page: params.page ?? 1,
      pageSize: params.pageSize ?? 50,
    },
  });
}

export interface CreateUserPayload {
  email: string;
  name: string;
  role: UserRole;
  password: string;
}

export function createUser(payload: CreateUserPayload) {
  return apiClient.post<AdminUser>('/api/v1/admin/users', payload);
}

export function suspendUser(userId: string) {
  return apiClient.post<{ success: boolean; status: UserStatus }>(
    `/api/v1/admin/users/${userId}/suspend`,
  );
}

export function activateUser(userId: string) {
  return apiClient.post<{ success: boolean; status: UserStatus }>(
    `/api/v1/admin/users/${userId}/activate`,
  );
}

// ── Audit logs ───────────────────────────────────────────────────────────────

export function listAuditLogs(params: {
  actor?: string;
  action?: string;
  page?: number;
  pageSize?: number;
} = {}) {
  return apiClient.get<{
    events: AuditEvent[];
    total: number;
    page: number;
    pageSize: number;
    hasMore: boolean;
  }>('/api/v1/admin/audit-logs', {
    params: {
      actor: params.actor,
      action: params.action,
      page: params.page ?? 1,
      pageSize: params.pageSize ?? 50,
    },
  });
}

export function getAuditLog(eventId: string) {
  return apiClient.get<AuditEvent>(`/api/v1/admin/audit-logs/${eventId}`);
}

// ── System health ───────────────────────────────────────────────────────────

export function getSystemHealth() {
  return apiClient.get<SystemHealth>('/api/v1/admin/system-health');
}
