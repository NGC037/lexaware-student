import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { helpApi, knowledgeApi, type HelpResource, type StudentArticle } from "../../api/student-content";
import { AuthContext, type AuthContextValue } from "../../app/auth/auth-context";
import { ThemeProvider } from "../../app/theme/ThemeProvider";
import { MemoryRouter, Route, Routes } from "react-router";
import { AppHomePage } from "./AppHomePage";
import { AuthenticatedLayout } from "../../shared/layout/AuthenticatedLayout";

vi.mock("../../api/student-content", () => ({
  helpApi: { list: vi.fn() },
  knowledgeApi: { searchArticles: vi.fn() },
}));

const profile = { id: "dashboard-user", email: "student@example.test", display_name: "Asha Student", roles: ["student"], status: "active", session_expires_at: null };
const article: StudentArticle = {
  id: "article-1", slug: "student-rights", title: "Understanding student protections", category: "education", topic: "student rights", audience: "students",
  summary: "A reviewed overview of student protections.", applicability_notes: null, escalation_guidance: null,
  jurisdiction: { id: "jurisdiction-1", code: "IN", name: "India", parent_id: null }, effective_from: null, last_reviewed_at: "2026-01-10T00:00:00Z",
  source_title: "Official source", source_publisher: "Public authority", source_url: "https://example.test/source", source_citation: null,
};
const resource: HelpResource = {
  id: "resource-1", name: "Student Support Centre", category: "support", resource_type: "counselling", assistance_type: "student support", contact_method: "multiple",
  description: "Confidential student support.", contact_url: "https://example.test/help", phone: "+91 12345 67890", contact_email: "help@example.test",
  jurisdiction: { code: "IN", name: "India" }, source_title: "Verified directory", source_publisher: null,
  source_url: "https://example.test/directory", source_citation: null, source_retrieved_at: "2026-01-01T00:00:00Z",
  verified_at: "2026-01-10T00:00:00Z", status: "verified_current",
};

const context: AuthContextValue = {
  session: { status: "authenticated", user: profile },
  refreshSession: vi.fn(), signIn: vi.fn(), signOut: vi.fn(),
};

function renderDashboard() {
  return render(<MemoryRouter initialEntries={["/app"]}><ThemeProvider><AuthContext.Provider value={context}><Routes><Route element={<AuthenticatedLayout />}><Route path="/app" element={<AppHomePage />} /></Route></Routes></AuthContext.Provider></ThemeProvider></MemoryRouter>);
}

describe("authenticated student dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.documentElement.dataset.theme = "light";
    vi.mocked(helpApi.list).mockResolvedValue([resource]);
    vi.mocked(knowledgeApi.searchArticles).mockResolvedValue([article]);
  });
  afterEach(() => { cleanup(); localStorage.clear(); });

  it("uses the current profile and displays real verified support contacts", async () => {
    renderDashboard();
    expect(await screen.findByRole("heading", { name: /Asha Student/ })).toBeInTheDocument();
    const support = screen.getByRole("region", { name: "Need help finding a next step?" });
    expect(await within(support).findByText("Student Support Centre")).toBeInTheDocument();
    expect(within(support).getByText("Verified directory", { exact: false })).toBeInTheDocument();
    expect(within(support).getByRole("link", { name: /Call/ })).toHaveAttribute("href", "tel:+911234567890");
  });

  it("searches current student guidance and shows its source", async () => {
    const user = userEvent.setup();
    renderDashboard();
    const field = screen.getByRole("textbox", { name: "Search reviewed student guidance" });
    await user.type(field, "internship agreement");
    await user.click(screen.getByRole("button", { name: "Search published guidance" }));
    expect(await screen.findByRole("heading", { name: "Understanding student protections" })).toBeInTheDocument();
    expect(knowledgeApi.searchArticles).toHaveBeenCalledWith("internship agreement", expect.any(AbortSignal));
    expect(screen.getByRole("link", { name: /View source: Official source/ })).toHaveAttribute("href", article.source_url);
  });

  it("keeps empty search results truthful and safe source links HTTP-only", async () => {
    vi.mocked(knowledgeApi.searchArticles).mockResolvedValue([{ ...article, source_url: "javascript:alert(1)" }]);
    const user = userEvent.setup();
    renderDashboard();
    await user.type(screen.getByRole("textbox", { name: "Search reviewed student guidance" }), "rights");
    await user.click(screen.getByRole("button", { name: "Search published guidance" }));
    expect(await screen.findByRole("heading", { name: article.title })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /View source/ })).not.toBeInTheDocument();
    vi.mocked(knowledgeApi.searchArticles).mockResolvedValue([]);
    await user.clear(screen.getByRole("textbox", { name: "Search reviewed student guidance" }));
    await user.type(screen.getByRole("textbox", { name: "Search reviewed student guidance" }), "no match");
    await user.click(screen.getByRole("button", { name: "Search published guidance" }));
    expect(await screen.findByRole("heading", { name: "No published guidance matched" })).toBeInTheDocument();
  });

  it("recovers from search and support failures with separate retry controls", async () => {
    vi.mocked(knowledgeApi.searchArticles).mockRejectedValueOnce(new Error("network"));
    vi.mocked(helpApi.list).mockRejectedValueOnce(new Error("network"));
    const user = userEvent.setup();
    renderDashboard();
    await screen.findByRole("heading", { name: "Support contacts are temporarily unavailable" });
    await user.type(screen.getByRole("textbox", { name: "Search reviewed student guidance" }), "housing");
    await user.click(screen.getByRole("button", { name: "Search published guidance" }));
    expect(await screen.findByRole("heading", { name: "Search is temporarily unavailable" })).toBeInTheDocument();
    vi.mocked(knowledgeApi.searchArticles).mockResolvedValue([article]);
    await user.click(screen.getAllByRole("button", { name: "Try again" })[0]!);
    expect(await screen.findByRole("heading", { name: article.title })).toBeInTheDocument();
    vi.mocked(helpApi.list).mockResolvedValue([resource]);
    await user.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.getByText("Student Support Centre")).toBeInTheDocument());
  });

  it("provides working dashboard anchors, honest unavailable actions, and theme control", async () => {
    const user = userEvent.setup();
    renderDashboard();
    await screen.findByText("Student Support Centre");
    await user.click(screen.getByRole("link", { name: /Find reviewed help/ }));
    expect(window.location.hash).toBe("#dashboard-support");
    expect(screen.queryByText("Coming soon")).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /My Documents/ }).some((link) => link.getAttribute("href") === "/app/documents")).toBe(true);
    expect(screen.getAllByRole("link", { name: /Complaint guidance/ }).some((link) => link.getAttribute("href") === "/app/complaints")).toBe(true);
    expect(screen.getByRole("link", { name: /Guided legal awareness/ })).toHaveAttribute("href", "/app/assistant");
    await user.selectOptions(screen.getByRole("combobox", { name: "Color theme" }), "dark");
    await waitFor(() => expect(document.documentElement).toHaveAttribute("data-theme", "dark"));
  });

  it("shows a loading state while the governed help endpoint is pending", () => {
    vi.mocked(helpApi.list).mockReturnValue(new Promise(() => undefined));
    renderDashboard();
    expect(screen.getByRole("status", { name: "Loading verified support contacts" })).toBeInTheDocument();
  });

  it("does not invent support contacts when the governed directory is empty", async () => {
    vi.mocked(helpApi.list).mockResolvedValue([]);
    renderDashboard();
    expect(await screen.findByRole("heading", { name: "No current contacts are listed" })).toBeInTheDocument();
    expect(screen.getByText(/contact your local emergency service/i)).toBeInTheDocument();
  });
});
