import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { governedHelpApi, type GovernedHelpResource } from "../../api/student-content";
import { HelpDirectoryPage } from "./HelpDirectoryPage";

vi.mock("../../api/student-content", () => ({ governedHelpApi: { list: vi.fn() } }));

const resource: GovernedHelpResource = {
  id: "resource-1", name: "Student support service", category: "support", resource_type: "counselling service", assistance_type: "student support",
  contact_method: "multiple", description: "A governed service description.", contact_url: "https://service.example.test/contact", phone: "+91 123 456",
  contact_email: "contact@example.test", jurisdiction: { code: "IN", name: "India" }, source_title: "Service source", source_publisher: "Public institution",
  source_url: "https://source.example.test", source_citation: "Service directory", source_retrieved_at: "2026-08-10T00:00:00Z", verified_at: "2026-09-01T00:00:00Z", status: "verified_current",
};

describe("Help Directory", () => {
  beforeEach(() => vi.mocked(governedHelpApi.list).mockReset());
  afterEach(cleanup);

  it("renders governed resource, contact, jurisdiction and source details", async () => {
    vi.mocked(governedHelpApi.list).mockResolvedValue([resource]);
    render(<HelpDirectoryPage />);
    expect(await screen.findByRole("heading", { name: resource.name })).toBeInTheDocument();
    expect(screen.getByText("A governed service description.")).toBeInTheDocument();
    expect(screen.getByText(/Verified .*2026/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Call \+91 123 456/ })).toHaveAttribute("href", "tel:+91123456");
    expect(screen.getByRole("link", { name: /Email contact@example.test/ })).toHaveAttribute("href", "mailto:contact%40example.test");
    expect(screen.getByRole("link", { name: "Visit resource website" })).toHaveAttribute("href", resource.contact_url);
    expect(screen.getByRole("link", { name: "View source" })).toHaveAttribute("href", "https://source.example.test/");
  });

  it("only makes HTTP(S) contact and source URLs actionable", async () => {
    vi.mocked(governedHelpApi.list).mockResolvedValue([{ ...resource, contact_url: "javascript:alert(1)", source_url: "data:text/html,bad" }]);
    render(<HelpDirectoryPage />);
    await screen.findByRole("heading", { name: resource.name });
    expect(screen.queryByRole("link", { name: /Visit resource website/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "View source" })).not.toBeInTheDocument();
  });

  it("uses only supported filters and presents loading, empty, generic error and retry states", async () => {
    vi.mocked(governedHelpApi.list).mockResolvedValueOnce([]).mockRejectedValueOnce(new Error("private database detail")).mockResolvedValueOnce([resource]);
    const user = userEvent.setup();
    render(<HelpDirectoryPage />);
    expect(screen.getByRole("heading", { name: "Loading verified resources" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "No verified resources found" })).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "Category" }), "support");
    await user.type(screen.getByRole("textbox", { name: "Jurisdiction code" }), "IN");
    await user.type(screen.getByRole("textbox", { name: "Assistance type" }), "student support");
    await user.click(screen.getByRole("button", { name: "Apply filters" }));
    await waitFor(() => expect(governedHelpApi.list).toHaveBeenLastCalledWith({ category: "support", jurisdiction: "IN", assistance_type: "student support", limit: 50 }, expect.any(AbortSignal)));
    expect(await screen.findByRole("heading", { name: "The help directory is temporarily unavailable" })).toBeInTheDocument();
    expect(screen.queryByText(/private database detail/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: resource.name })).toBeInTheDocument();
  });
});
