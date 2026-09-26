import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import { knowledgeApi, type StudentArticle, type StudentArticleDetail } from "../../api/student-content";
import { MemoryRouter, Route, Routes } from "react-router";
import { RightsExplorerPage } from "./RightsExplorerPage";
import { StudentArticlePage } from "./StudentArticlePage";

vi.mock("../../api/student-content", () => ({
  knowledgeApi: { listArticles: vi.fn(), listCategories: vi.fn(), listJurisdictions: vi.fn(), getArticle: vi.fn(), searchArticles: vi.fn() },
  helpApi: { list: vi.fn() },
}));

const article: StudentArticle = {
  id: "article-id", slug: "student-protections", title: "Student protections", category: "education", topic: "student rights", audience: "students",
  summary: "An overview of published protections.", applicability_notes: "Rules may vary by location.", escalation_guidance: null,
  jurisdiction: { id: "jurisdiction-id", code: "IN", name: "India", parent_id: null }, effective_from: "2025-01-01T00:00:00Z",
  last_reviewed_at: "2026-01-10T00:00:00Z", source_title: "Official source", source_publisher: "Public authority",
  source_url: "https://example.test/source", source_citation: "Section 4",
};
const detail: StudentArticleDetail = {
  id: article.id, slug: article.slug, title: article.title, category: article.category, topic: article.topic, audience: article.audience,
  jurisdiction: article.jurisdiction, effective_from: article.effective_from, last_reviewed_at: article.last_reviewed_at,
  version_number: 3, summary: article.summary, content: "Read this source.\nDo not treat it as a conclusion.",
  applicability_notes: article.applicability_notes, escalation_guidance: "Check the cited source.",
  source: { id: "source-id", jurisdiction_id: "jurisdiction-id", title: "Official source", publisher: "Public authority", source_url: "https://example.test/source", citation: "Section 4", retrieved_at: "2026-01-02T00:00:00Z", effective_from: null, effective_until: null, is_active: true },
};
const categories = [{ category: "education", article_count: 1 }];
const jurisdictions = [{ id: "jurisdiction-id", code: "IN", name: "India", parent_id: null }];

function renderAt(path = "/app/rights") {
  return render(<MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/app/rights" element={<RightsExplorerPage />} />
    <Route path="/app/rights/:slug" element={<StudentArticlePage />} />
  </Routes></MemoryRouter>);
}

describe("Rights Explorer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(knowledgeApi.listArticles).mockResolvedValue([article]);
    vi.mocked(knowledgeApi.listCategories).mockResolvedValue(categories);
    vi.mocked(knowledgeApi.listJurisdictions).mockResolvedValue(jurisdictions);
    vi.mocked(knowledgeApi.getArticle).mockResolvedValue(detail);
  });
  afterEach(() => cleanup());

  it("loads governed student guidance, exposes backend filters, and submits search and filters", async () => {
    const user = userEvent.setup();
    renderAt();
    expect(await screen.findByRole("heading", { name: article.title })).toBeInTheDocument();
    expect(screen.getByText("Official source", { exact: false })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /View source/ })).toHaveAttribute("href", article.source_url);
    expect(screen.getByRole("option", { name: "education" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "India" })).toBeInTheDocument();

    await user.type(screen.getByRole("searchbox", { name: "Search guidance" }), "student rights");
    await user.selectOptions(screen.getByRole("combobox", { name: "Category" }), "education");
    await user.selectOptions(screen.getByRole("combobox", { name: "Jurisdiction" }), "IN");
    await user.click(screen.getByRole("button", { name: "Apply filters" }));
    await waitFor(() => expect(knowledgeApi.listArticles).toHaveBeenLastCalledWith(
      { q: "student rights", category: "education", jurisdiction: "IN", limit: 12, offset: 0 }, expect.any(AbortSignal),
    ));
  });

  it("loads the next result page using the backend offset and appends it", async () => {
    const firstPage = Array.from({ length: 12 }, (_, index) => ({
      ...article, id: "article-" + index, slug: "article-" + index, title: "Result " + index,
    }));
    vi.mocked(knowledgeApi.listArticles).mockReset()
      .mockResolvedValueOnce(firstPage).mockResolvedValueOnce([article]);
    const user = userEvent.setup();
    renderAt();
    expect(await screen.findByRole("heading", { name: "Result 0" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Load more guidance" }));
    expect(await screen.findByRole("heading", { name: article.title })).toBeInTheDocument();
    await waitFor(() => expect(knowledgeApi.listArticles).toHaveBeenLastCalledWith(
      { q: "", category: "", jurisdiction: "", limit: 12, offset: 12 }, expect.any(AbortSignal),
    ));
  });
  it("shows the loading state and truthful empty state", async () => {
    vi.mocked(knowledgeApi.listArticles).mockResolvedValueOnce([]);
    renderAt();
    expect(screen.getByRole("heading", { name: "Loading published guidance" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "No guidance matched these filters" })).toBeInTheDocument();
  });

  it("keeps API errors generic and retries the list", async () => {
    vi.mocked(knowledgeApi.listArticles).mockRejectedValueOnce(new Error("private backend exception"));
    renderAt();
    expect(await screen.findByRole("heading", { name: "Guidance is temporarily unavailable" })).toBeInTheDocument();
    expect(screen.queryByText("private backend exception")).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: article.title })).toBeInTheDocument();
  });

  it("opens published detail with source, freshness, applicability, and plain text content", async () => {
    const user = userEvent.setup();
    renderAt("/app/rights/student-protections");
    expect(await screen.findByRole("heading", { name: article.title })).toBeInTheDocument();
    expect(screen.getByText(/Read this source/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Applicability" })).toBeInTheDocument();
    expect(screen.getByText("Source retrieved")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open original source/ })).toHaveAttribute("href", article.source_url);
    expect(document.querySelector("script")).toBeNull();
    await user.click(screen.getByRole("link", { name: /All guidance/ }));
    expect(await screen.findByRole("heading", { name: "Published guidance" })).toBeInTheDocument();
  });

  it("handles an unavailable article without revealing backend details", async () => {
    vi.mocked(knowledgeApi.getArticle).mockRejectedValue(new ApiError(404, { message: "private backend detail" }));
    renderAt("/app/rights/archived");
    expect(await screen.findByRole("heading", { name: "This guidance is not currently available" })).toBeInTheDocument();
    expect(screen.queryByText("private backend detail")).not.toBeInTheDocument();
  });
});
