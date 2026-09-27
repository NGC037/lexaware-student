import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import { complaintApi, type ComplaintGuide } from "../../api/student-content";
import { ComplaintGuidePage, ComplaintGuidesPage } from "./ComplaintGuidancePage";

vi.mock("../../api/student-content", () => ({ complaintApi: { list: vi.fn(), get: vi.fn() } }));

const guide: ComplaintGuide = {
  id: "guide-1", slug: "student-conduct", version_number: 1, title: "Understanding a conduct concern", category: "conduct", audience: "students",
  short_description: "Governed guide summary.", jurisdiction: { id: "jurisdiction-1", code: "IN", name: "India" },
  guidance_steps: [
    { position: 2, section: "preserve_evidence", title: "Keep relevant records", instruction: "Consider preserving relevant records." },
    { position: 1, section: "immediate_safety", title: "Consider safety first", instruction: "Review the source guidance for your circumstances." },
  ], reviewed_at: "2026-09-01T00:00:00Z",
};

function renderAt(path: string, page: React.ReactNode) {
  return render(<MemoryRouter initialEntries={[path]}><Routes><Route path="/app/complaints" element={page} /><Route path="/app/complaints/:slug" element={<ComplaintGuidePage />} /></Routes></MemoryRouter>);
}

describe("complaint guidance pages", () => {
  beforeEach(() => { vi.mocked(complaintApi.list).mockReset(); vi.mocked(complaintApi.get).mockReset(); });
  afterEach(cleanup);

  it("guides a student through ordered steps with readable section names and previous/next controls", async () => {
    vi.mocked(complaintApi.get).mockResolvedValue(guide);
    const user = userEvent.setup();
    renderAt("/app/complaints/student-conduct", <ComplaintGuidePage />);
    expect(await screen.findByRole("heading", { name: guide.title })).toBeInTheDocument();
    expect(screen.queryByText("immediate_safety")).not.toBeInTheDocument();
    expect(screen.getByText(/Reviewed .*2026/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Start guide" }));
    expect(screen.getByText("Step 1 of 2")).toBeInTheDocument();
    expect(screen.getByText("Immediate safety")).toBeInTheDocument();
    expect(screen.queryByText("Keep relevant records")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Step 2 of 2")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Keep relevant records" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Previous" }));
    expect(screen.getByRole("heading", { name: "Consider safety first" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Finish guide" }));
    expect(screen.getByRole("heading", { name: "Guide complete" })).toBeInTheDocument();
  });

  it("loads the real student list contract, applies supported filters, and links to details", async () => {
    vi.mocked(complaintApi.list).mockResolvedValue([guide]);
    const user = userEvent.setup();
    renderAt("/app/complaints", <ComplaintGuidesPage />);
    expect(await screen.findByRole("link", { name: guide.title })).toHaveAttribute("href", "/app/complaints/student-conduct");
    await user.type(screen.getByRole("textbox", { name: "Category" }), "conduct");
    await user.type(screen.getByRole("textbox", { name: "Jurisdiction code" }), "IN");
    await user.click(screen.getByRole("button", { name: "Apply filters" }));
    await waitFor(() => expect(complaintApi.list).toHaveBeenLastCalledWith({ category: "conduct", jurisdiction: "IN", limit: 50 }, expect.any(AbortSignal)));
  });

  it("announces loading and a truthful empty state", async () => {
    vi.mocked(complaintApi.list).mockResolvedValue([]);
    renderAt("/app/complaints", <ComplaintGuidesPage />);
    expect(screen.getByRole("heading", { name: "Loading published guides" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "No published guides found" })).toBeInTheDocument();
  });

  it("shows a generic error and retries the list", async () => {
    vi.mocked(complaintApi.list).mockRejectedValueOnce(new Error("database password leaked")).mockResolvedValueOnce([guide]);
    const user = userEvent.setup();
    renderAt("/app/complaints", <ComplaintGuidesPage />);
    expect(await screen.findByRole("heading", { name: "Complaint guidance is temporarily unavailable" })).toBeInTheDocument();
    expect(screen.queryByText(/database password/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: guide.title })).toBeInTheDocument();
  });

  it("distinguishes an unavailable or unpublished detail from a service failure", async () => {
    vi.mocked(complaintApi.get).mockRejectedValue(new ApiError(404, { message: "private backend detail" }));
    renderAt("/app/complaints/no-longer-published", <ComplaintGuidePage />);
    expect(await screen.findByRole("heading", { name: "This guide is not currently available" })).toBeInTheDocument();
    expect(screen.queryByText(/private backend detail/)).not.toBeInTheDocument();
  });
});
