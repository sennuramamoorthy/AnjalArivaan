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

interface StoredAuth {
  state?: {
    accessToken?: string;
    refreshToken?: string;
  };
}

function readAuth(): StoredAuth['state'] | null {
  try {
    const raw = localStorage.getItem('anjal-auth');
    if (!raw) return null;
    return (JSON.parse(raw) as StoredAuth)?.state ?? null;
  } catch {
    return null;
  }
}

function getAccessToken(): string | null {
  return readAuth()?.accessToken ?? null;
}

function getRefreshToken(): string | null {
  return readAuth()?.refreshToken ?? null;
}

function writeAccessToken(access: string, refresh?: string): void {
  try {
    const raw = localStorage.getItem('anjal-auth');
    const parsed = raw ? (JSON.parse(raw) as StoredAuth) : { state: {} };
    parsed.state = {
      ...(parsed.state ?? {}),
      accessToken: access,
      ...(refresh ? { refreshToken: refresh } : {}),
    };
    localStorage.setItem('anjal-auth', JSON.stringify(parsed));
  } catch {
    // ignore storage errors
  }
}

/**
 * In-flight refresh guard. If two concurrent 401s race, we only fire one
 * POST /auth/refresh and let every other caller await the same promise.
 * This prevents the second call from burning the refresh token (the
 * backend rotates it on use).
 */
let refreshInFlight: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight;
  const refresh = getRefreshToken();
  if (!refresh) return null;
  refreshInFlight = (async () => {
    try {
      const res = await fetch(buildUrl('/api/v1/auth/refresh'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refreshToken: refresh }),
      });
      if (!res.ok) return null;
      const body = (await res.json()) as ApiEnvelope<{
        accessToken: string;
        refreshToken: string;
      }>;
      if (!body.success || !body.data?.accessToken) return null;
      writeAccessToken(body.data.accessToken, body.data.refreshToken);
      return body.data.accessToken;
    } catch {
      return null;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
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

async function request<T>(
  path: string,
  options: RequestOptions = {},
  _isRetry = false,
): Promise<T> {
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

    // On 401: try refresh-then-retry once. Only if that fails do we clear
    // the session and redirect to /login. The 15-min access-token TTL
    // used to bounce users to /login mid-session; silent refresh keeps
    // the session alive as long as the refresh token is valid.
    if (
      res.status === 401 &&
      !_isRetry &&
      !path.includes('/auth/login') &&
      !path.includes('/auth/refresh')
    ) {
      const refreshed = await refreshAccessToken();
      if (refreshed) {
        return request<T>(path, options, true);
      }
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
