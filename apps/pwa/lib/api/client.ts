import { generateTraceId } from '@/lib/utils';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:4001';

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public traceId: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
}

/**
 * The identity service wraps all responses in an envelope:
 *   { success: boolean, data: T, error?: { code, message }, meta: { traceId } }
 *
 * This interface models that envelope so we can unwrap it.
 */
interface ApiEnvelope<T> {
  success: boolean;
  data?: T;
  error?: { code: string; message: string };
  meta?: { traceId: string };
}

function getAccessToken(): string | null {
  try {
    const raw = localStorage.getItem('anjal-auth');
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { state?: { accessToken?: string } };
    return parsed?.state?.accessToken ?? null;
  } catch {
    return null;
  }
}

function buildUrl(path: string, params?: Record<string, string | number | boolean | undefined>): string {
  const url = new URL(path, BASE_URL);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined) url.searchParams.set(k, String(v));
    });
  }
  return url.toString();
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { params, ...init } = options;
  const traceId = generateTraceId();
  const token = getAccessToken();

  const headers = new Headers(init.headers);
  headers.set('Content-Type', 'application/json');
  headers.set('X-Trace-ID', traceId);
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const res = await fetch(buildUrl(path, params), { ...init, headers });

  if (!res.ok) {
    let code = 'UNKNOWN_ERROR';
    let message = res.statusText;
    try {
      const body = (await res.json()) as ApiEnvelope<unknown>;
      code = body.error?.code ?? code;
      message = body.error?.message ?? message;
    } catch {
      // ignore JSON parse failure
    }

    // Auto-redirect to login on 401 — clears stale session
    if (res.status === 401 && !path.includes('/auth/login')) {
      try {
        localStorage.removeItem('anjal-auth');
      } catch {
        // ignore storage errors
      }
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    }

    throw new ApiError(res.status, code, message, traceId);
  }

  if (res.status === 204) return undefined as T;

  const body = (await res.json()) as ApiEnvelope<T> | T;

  // Unwrap the { success, data, meta } envelope if present
  if (
    body !== null &&
    typeof body === 'object' &&
    'success' in body &&
    'data' in body
  ) {
    const envelope = body as ApiEnvelope<T>;
    if (!envelope.success) {
      throw new ApiError(
        res.status,
        envelope.error?.code ?? 'UNKNOWN_ERROR',
        envelope.error?.message ?? 'Request failed',
        envelope.meta?.traceId ?? traceId,
      );
    }
    return envelope.data as T;
  }

  return body as T;
}

export const apiClient = {
  get: <T>(path: string, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'GET' }),

  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, {
      ...options,
      method: 'POST',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),

  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, {
      ...options,
      method: 'PUT',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),

  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, {
      ...options,
      method: 'PATCH',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),

  delete: <T>(path: string, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'DELETE' }),
};
