import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./client";
import { documentsApi, type DocumentSummary } from "./documents";

describe("private document API client", () => {
  const fetchMock = vi.fn();
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockImplementation(() => Promise.resolve(new Response("[]", { status: 200, headers: { "Content-Type": "application/json" } })));
  });
  afterEach(() => { vi.unstubAllGlobals(); document.cookie = "lexaware_csrf=; Max-Age=0; path=/"; });

  it("lists documents through the authenticated shared client", async () => {
    await documentsApi.list();
    const [input, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new URL(input).pathname).toBe("/api/v1/documents");
    expect(init.credentials).toBe("include");
    expect(init.method).toBe("GET");
  });

  it("sends multipart uploads with the backend's file field and shared CSRF cookie", async () => {
    document.cookie = "lexaware_csrf=document-csrf; path=/";
    const file = new File(["%PDF-1.4"], "agreement.pdf", { type: "application/pdf" });
    await documentsApi.upload(file);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("include");
    expect(new Headers(init.headers).get("X-CSRF-Token")).toBe("document-csrf");
    expect(new Headers(init.headers).has("Content-Type")).toBe(false);
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get("file")).toBeInstanceOf(File);
  });

  it("decodes the typed upload result", async () => {
    const document: DocumentSummary = {
      id: "document-id", original_filename: "agreement.pdf", media_type: "application/pdf", size_bytes: 200,
      status: "validated", malware_scan_state: "not_configured", page_count: 1, document_type: null,
      classification_confidence: null, needs_ocr: false, job_status: "queued", attempts: 0,
      created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z",
    };
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ document, duplicate: false, detail: "Upload accepted." }), { status: 202 }));
    const result = await documentsApi.upload(new File(["pdf"], "agreement.pdf", { type: "application/pdf" }));
    expect(result.document).toEqual(document);
    expect(result.duplicate).toBe(false);
  });

  it("normalizes not-found and conflict errors for safe UI mapping", async () => {
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Document not found." }), { status: 404 }));
    await expect(documentsApi.get("missing")).rejects.toMatchObject({ name: "ApiError", status: 404 } satisfies Partial<ApiError>);
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ detail: "The report is not available yet." }), { status: 409 }));
    await expect(documentsApi.report("document-id")).rejects.toMatchObject({ name: "ApiError", status: 409 } satisfies Partial<ApiError>);
  });

  it("uses protected endpoints for retry and deletion", async () => {
    document.cookie = "lexaware_csrf=document-csrf; path=/";
    await documentsApi.retry("document-id");
    await documentsApi.delete("document-id");
    expect(new URL((fetchMock.mock.calls[0] as [string, RequestInit])[0]).pathname).toBe("/api/v1/documents/document-id/retry");
    expect(new Headers((fetchMock.mock.calls[0] as [string, RequestInit])[1].headers).get("X-CSRF-Token")).toBe("document-csrf");
    expect((fetchMock.mock.calls[1] as [string, RequestInit])[1].method).toBe("DELETE");
  });
});
