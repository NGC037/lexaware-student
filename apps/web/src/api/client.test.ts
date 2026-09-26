import { beforeEach, describe, expect, it, vi } from "vitest";
import { authApi } from "./auth";
import { normalizeError, request, requestBlob } from "./client";

describe("API client foundations", () => {
  beforeEach(() => { vi.stubGlobal("fetch", vi.fn()); document.cookie = "lexaware_csrf=token%2Bvalue; path=/"; });
  it("normalizes FastAPI validation details without losing field data", () => {
    const error = normalizeError(422, { detail: [{ loc: ["body", "email"], msg: "Invalid email", type: "value_error" }] });
    expect(error.message).toBe("Invalid email"); expect(error.status).toBe(422); expect(error.fields).toHaveLength(1);
  });
  it("normalizes assistant errors and correlation IDs", () => {
    const error = normalizeError(429, { error: { code: "rate_limited", message: "Try again shortly" } }, "request-123");
    expect(error.message).toBe("Try again shortly"); expect(error.code).toBe("rate_limited"); expect(error.correlationId).toBe("request-123");
  });
  it("uses cookie credentials and adds CSRF only on unsafe requests", async () => {
    const fetchMock = vi.mocked(fetch); fetchMock.mockImplementation(async () => new Response(JSON.stringify({ ok: true }), { status: 200 }));
    await request("/health"); expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ credentials: "include", method: "GET" });
    expect(new Headers(fetchMock.mock.calls[0]?.[1]?.headers).has("X-CSRF-Token")).toBe(false);
    await request("/auth/logout", { method: "POST", body: {} });
    expect(fetchMock.mock.calls[1]?.[0]).toContain("/api/v1/auth/logout");
    expect(new Headers(fetchMock.mock.calls[1]?.[1]?.headers).get("X-CSRF-Token")).toBe("token+value");
  });
  it("uses the backend-issued CSRF response when calling logout", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation(async (input) => String(input).endsWith("/auth/csrf")
      ? new Response(JSON.stringify({ csrf_token: "fresh-token" }), { status: 200 })
      : new Response(JSON.stringify({ message: "Successfully logged out" }), { status: 200 }));
    await authApi.logout();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/auth/csrf");
    expect(new Headers(fetchMock.mock.calls[1]?.[1]?.headers).get("X-CSRF-Token")).toBe("fresh-token");
  });
  it("returns authenticated binary responses without JSON parsing", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(new Response("%PDF-1.4", { status: 200, headers: { "Content-Type": "application/pdf" } }));
    const blob = await requestBlob("/documents/document-id/download");
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/api/v1/documents/document-id/download");
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ credentials: "include", method: "GET" });
    expect(blob).toBeInstanceOf(Blob);
    expect(blob.type).toBe("application/pdf");
  });
});
