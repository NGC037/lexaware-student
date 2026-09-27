import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { operationsApi, type OperationsOverview } from "../../api/operations";
import { AdminOperationsPage } from "./AdminOperationsPage";

vi.mock("../../api/operations", () => ({ operationsApi: { overview: vi.fn(), resolveFeedback: vi.fn() } }));

const empty: OperationsOverview = {
  stale_content: [], failed_analyses: [], provider_errors: [], user_reports: [], unresolved_feedback: [],
};

describe("AdminOperationsPage", () => {
  beforeEach(() => vi.resetAllMocks());
  it("shows loading, empty state, and all five queues", async () => {
    let finish!: (value: OperationsOverview) => void;
    vi.mocked(operationsApi.overview).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
    render(<AdminOperationsPage />);
    expect(screen.getByRole("status")).toHaveTextContent(/loading operations queues/i);
    finish(empty);
    expect(await screen.findByRole("heading", { name: /admin overview/i })).toBeInTheDocument();
    for (const title of ["Stale content", "Failed analyses", "Provider errors", "User reports", "Unresolved feedback"]) {
      expect(screen.getByRole("heading", { name: new RegExp(title, "i") })).toBeInTheDocument();
    }
    expect(screen.getAllByText(/no items need attention/i)).toHaveLength(5);
  });
  it("shows a recoverable error state", async () => {
    vi.mocked(operationsApi.overview).mockRejectedValue(new Error("forbidden"));
    render(<AdminOperationsPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/could not be loaded/i);
  });
});
