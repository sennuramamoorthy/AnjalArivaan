/**
 * Thin fetch wrapper with:
 *   - JWT attachment (access token from localStorage)
 *   - Automatic refresh on 401 (single-flight)
 *   - Typed JSON responses
 *   - Uniform error shape
 *
 * Design pattern: Facade + Strategy. Swap out `fetchImpl` for tests.
 */
import type { ApiError, TokenPair } from "@/types/api";

const ACCESS_KEY = "aa.access";
const REFRESH_KEY = "aa.refresh";

type FetchImpl = typeof fetch;

let refreshPromise: Promise<string | null> | null = null;

export class HttpError extends Error {
  status: number;
  detail: string;
  code?: string;
  constructor(status: number, detail: string, code?: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
    this.code = code;
  }
}

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

export const tokenStore = {
  getAccess(): string | null {
    return isBrowser() ? window.localStorage.getItem(ACCESS_KEY) : null;
  },
  getRefresh(): string | null {
    return isBrowser() ? window.localStorage.getItem(REFRESH_KEY) : null;
  },
  set(pair: TokenPair): void {
    if (!isBrowser()) return;
    window.localStorage.setItem(ACCESS_KEY, pair.access_token);
    window.localStorage.setItem(REFRESH_KEY, pair.refresh_token);
  },
  clear(): void {
    if (!isBrowser()) return;
    window.localStorage.removeItem(ACCESS_KEY);
    window.localStorage.removeItem(REFRESH_KEY);
  },
};

async function doRefresh(fetchImpl: FetchImpl): Promise<string | null> {
  const refresh = tokenStore.getRefresh();
  if (!refresh) return null;
  try {
    const res = await fetchImpl("/api/v1/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) {
      tokenStore.clear();
      return null;
    }
    const pair = (await res.json()) as TokenPair;
    tokenStore.set(pair);
    return pair.access_token;
  } catch {
    tokenStore.clear();
    return null;
  }
}

async function refreshSingleFlight(fetchImpl: FetchImpl): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = doRefresh(fetchImpl).finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

export interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  auth?: boolean; // default true
  fetchImpl?: FetchImpl;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  if (!query) return path;
  const u = new URL(path, isBrowser() ? window.location.origin : "http://localhost");
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null) continue;
    u.searchParams.set(k, String(v));
  }
  return isBrowser() ? `${u.pathname}${u.search}` : u.toString();
}

export async function request<T>(
  path: string,
  opts: RequestOptions = {}
): Promise<T> {
  const fetchImpl = opts.fetchImpl || fetch;
  const auth = opts.auth ?? true;

  const headers = new Headers(opts.headers as HeadersInit);
  if (opts.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (auth) {
    const tok = tokenStore.getAccess();
    if (tok) headers.set("Authorization", `Bearer ${tok}`);
  }

  const url = buildUrl(path, opts.query);
  const init: RequestInit = {
    ...opts,
    headers,
    body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
  };

  let res = await fetchImpl(url, init);

  if (res.status === 401 && auth) {
    const newToken = await refreshSingleFlight(fetchImpl);
    if (newToken) {
      headers.set("Authorization", `Bearer ${newToken}`);
      res = await fetchImpl(url, { ...init, headers });
    }
  }

  if (!res.ok) {
    let detail = res.statusText;
    let code: string | undefined;
    try {
      const body = (await res.json()) as ApiError;
      detail = body.detail || detail;
      code = body.code;
    } catch {
      /* body was not JSON */
    }
    throw new HttpError(res.status, detail, code);
  }

  if (res.status === 204) return undefined as T;
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return (await res.json()) as T;
  }
  return (await res.text()) as unknown as T;
}

/** SWR-compatible fetcher. */
export const swrFetcher = <T>(path: string) => request<T>(path);
