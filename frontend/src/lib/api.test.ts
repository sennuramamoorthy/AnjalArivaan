/**
 * Tests for the fetch facade — focuses on the parts that have real logic:
 *   - HttpError parsing
 *   - tokenStore get/set/clear round-trip
 *   - request() attaches bearer, encodes JSON body, parses JSON response
 *   - request() refreshes token on 401 and retries once
 *   - request() throws HttpError with detail + code when server returns ApiError JSON
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HttpError, request, tokenStore } from "./api";

function jsonResponse(body: unknown, init: { status?: number } = {}): Response {
  return new Response(JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("HttpError", () => {
  it("carries status, detail and code", () => {
    const err = new HttpError(403, "Forbidden", "AUTHZ_DENIED");
    expect(err).toBeInstanceOf(Error);
    expect(err.status).toBe(403);
    expect(err.detail).toBe("Forbidden");
    expect(err.code).toBe("AUTHZ_DENIED");
    expect(err.message).toBe("Forbidden");
  });
});

describe("tokenStore", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("persists and reads access/refresh tokens", () => {
    expect(tokenStore.getAccess()).toBeNull();
    tokenStore.set({ access_token: "A", refresh_token: "R", token_type: "bearer" });
    expect(tokenStore.getAccess()).toBe("A");
    expect(tokenStore.getRefresh()).toBe("R");
  });

  it("clears both tokens", () => {
    tokenStore.set({ access_token: "A", refresh_token: "R", token_type: "bearer" });
    tokenStore.clear();
    expect(tokenStore.getAccess()).toBeNull();
    expect(tokenStore.getRefresh()).toBeNull();
  });
});

describe("request()", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("attaches Authorization header when an access token is present", async () => {
    tokenStore.set({ access_token: "tok-abc", refresh_token: "r", token_type: "bearer" });
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));

    await request("/api/v1/auth/me", { fetchImpl });

    const [, init] = fetchImpl.mock.calls[0];
    const headers = init.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer tok-abc");
  });

  it("omits Authorization when auth:false", async () => {
    tokenStore.set({ access_token: "tok", refresh_token: "r", token_type: "bearer" });
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));

    await request("/api/v1/auth/login", {
      method: "POST",
      body: { email: "a@b", password: "x" },
      auth: false,
      fetchImpl,
    });

    const [, init] = fetchImpl.mock.calls[0];
    const headers = init.headers as Headers;
    expect(headers.has("Authorization")).toBe(false);
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(init.body).toBe(JSON.stringify({ email: "a@b", password: "x" }));
  });

  it("encodes query params", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse([]));

    await request("/api/v1/mail", {
      query: { account_id: 7, is_urgent: true, missing: undefined },
      auth: false,
      fetchImpl,
    });

    const [url] = fetchImpl.mock.calls[0];
    expect(url).toBe("/api/v1/mail?account_id=7&is_urgent=true");
  });

  it("parses ApiError JSON and throws HttpError", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ detail: "Nope", code: "AUTH_FAILED" }, { status: 403 })
      );

    await expect(
      request("/api/v1/auth/me", { auth: false, fetchImpl })
    ).rejects.toMatchObject({
      status: 403,
      detail: "Nope",
      code: "AUTH_FAILED",
    });
  });

  it("refreshes on 401 and retries the original request once", async () => {
    tokenStore.set({ access_token: "old", refresh_token: "r1", token_type: "bearer" });

    const fetchImpl = vi
      .fn()
      // 1st call: the real request — 401
      .mockResolvedValueOnce(jsonResponse({ detail: "Expired" }, { status: 401 }))
      // 2nd call: the refresh — returns new pair
      .mockResolvedValueOnce(
        jsonResponse({ access_token: "new", refresh_token: "r2", token_type: "bearer" })
      )
      // 3rd call: retried request with the new token — ok
      .mockResolvedValueOnce(jsonResponse({ id: 1, email: "a@b" }));

    const result = await request<{ id: number }>("/api/v1/auth/me", { fetchImpl });

    expect(result).toEqual({ id: 1, email: "a@b" });
    expect(fetchImpl).toHaveBeenCalledTimes(3);
    expect(tokenStore.getAccess()).toBe("new");

    // The retried (3rd) call should carry the new bearer.
    const retriedInit = fetchImpl.mock.calls[2][1];
    expect((retriedInit.headers as Headers).get("Authorization")).toBe("Bearer new");
  });
});
