import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { complaintApi, governedHelpApi, knowledgeApi } from "./student-content";

describe("knowledge API client", () => {
  const fetchMock = vi.fn();
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockImplementation(() => Promise.resolve(new Response("[]", { status: 200, headers: { "Content-Type": "application/json" } })));
  });
  afterEach(() => { vi.unstubAllGlobals(); });

  it("maps student list filters to the existing published-articles endpoint", async () => {
    await knowledgeApi.listArticles({ q: "  student rights  ", category: "education", jurisdiction: "IN-DL", limit: 12, offset: 24 });
    const [input, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const url = new URL(input);
    expect(url.pathname).toBe("/api/v1/knowledge/articles");
    expect(url.searchParams.get("audience")).toBe("students");
    expect(url.searchParams.get("q")).toBe("student rights");
    expect(url.searchParams.get("category")).toBe("education");
    expect(url.searchParams.get("jurisdiction")).toBe("IN-DL");
    expect(url.searchParams.get("limit")).toBe("12");
    expect(url.searchParams.get("offset")).toBe("24");
    expect(init.credentials).toBe("include");
  });

  it("uses browse defaults and safely encodes a detail slug", async () => {
    await knowledgeApi.listArticles({ q: "  " });
    await knowledgeApi.getArticle("private path/slug");
    const browseUrl = new URL(fetchMock.mock.calls[0]?.[0] as string);
    const detailUrl = new URL(fetchMock.mock.calls[1]?.[0] as string);
    expect(browseUrl.searchParams.has("q")).toBe(false);
    expect(browseUrl.searchParams.get("limit")).toBe("12");
    expect(browseUrl.searchParams.get("offset")).toBe("0");
    expect(detailUrl.pathname).toBe("/api/v1/knowledge/articles/private%20path%2Fslug");
  });

  it("uses existing category and jurisdiction discovery routes", async () => {
    await knowledgeApi.listCategories("IN");
    await knowledgeApi.listJurisdictions();
    expect(new URL(fetchMock.mock.calls[0]?.[0] as string).pathname).toBe("/api/v1/knowledge/categories");
    expect(new URL(fetchMock.mock.calls[0]?.[0] as string).searchParams.get("jurisdiction")).toBe("IN");
    expect(new URL(fetchMock.mock.calls[1]?.[0] as string).pathname).toBe("/api/v1/knowledge/jurisdictions");
  });

  it("uses only the governed student complaint browse and detail endpoints", async () => {
    await complaintApi.list({ category: " conduct ", jurisdiction: "IN-DL", limit: 50, offset: 25 });
    await complaintApi.get("guide / one");
    const listUrl = new URL(fetchMock.mock.calls[0]?.[0] as string);
    expect(listUrl.pathname).toBe("/api/v1/complaints/guides");
    expect(listUrl.searchParams.get("audience")).toBe("students");
    expect(listUrl.searchParams.get("category")).toBe("conduct");
    expect(listUrl.searchParams.get("jurisdiction")).toBe("IN-DL");
    expect(listUrl.searchParams.get("limit")).toBe("50");
    expect(listUrl.searchParams.get("offset")).toBe("25");
    expect(new URL(fetchMock.mock.calls[1]?.[0] as string).pathname).toBe("/api/v1/complaints/guides/guide%20%2F%20one");
  });

  it("maps help filters to the governed verified resource endpoint", async () => {
    await governedHelpApi.list({ category: "support", jurisdiction: "IN-DL", assistance_type: "legal", limit: 50 });
    const url = new URL(fetchMock.mock.calls[0]?.[0] as string);
    expect(url.pathname).toBe("/api/v1/help");
    expect(url.searchParams.get("category")).toBe("support");
    expect(url.searchParams.get("jurisdiction")).toBe("IN-DL");
    expect(url.searchParams.get("assistance_type")).toBe("legal");
    expect(url.searchParams.get("limit")).toBe("50");
  });
});
