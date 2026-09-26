import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { authApi, type MeResponse } from "../../api/auth";
import { AuthProvider } from "../../app/auth/AuthProvider";
import { isOnboardingCompleteThisTab } from "../../app/auth/onboarding-state";
import { ProtectedRoute } from "../../app/auth/RouteAccess";
import { ThemeProvider } from "../../app/theme/ThemeProvider";
import { OnboardingPage } from "./OnboardingPage";

vi.mock("../../api/auth", () => ({ authApi: { register: vi.fn(), login: vi.fn(), me: vi.fn(), logout: vi.fn() } }));
const api = vi.mocked(authApi);
const profile: MeResponse = { id: "onboarding-user", email: "student@example.test", display_name: null, roles: ["student"], status: "active", session_expires_at: null };

function renderOnboarding() {
  return render(<MemoryRouter initialEntries={["/onboarding"]}><ThemeProvider><AuthProvider><Routes>
    <Route element={<ProtectedRoute allowBeforeOnboarding />}><Route path="/onboarding" element={<OnboardingPage />} /><Route element={<ProtectedRoute />}><Route path="/app" element={<h1>Authenticated home</h1>} /></Route></Route>
  </Routes></AuthProvider></ThemeProvider></MemoryRouter>);
}

describe("onboarding introduction", () => {
  beforeEach(() => { sessionStorage.clear(); vi.clearAllMocks(); api.me.mockResolvedValue(profile); });
  afterEach(cleanup);

  it("moves through a short, accessible introduction and marks only this tab on completion", async () => {
    const user = userEvent.setup(); renderOnboarding();
    expect(await screen.findByRole("heading", { name: "Welcome to LexAware Student" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("heading", { name: "Welcome to LexAware Student" })).toHaveFocus());
    expect(screen.getByRole("progressbar", { name: "Getting started step 1 of 4" })).toHaveAttribute("value", "1");
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByRole("heading", { name: "Information for real questions" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("heading", { name: "Information for real questions" })).toHaveFocus());
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByRole("heading", { name: "Understand the limits" })).toBeInTheDocument();
    expect(screen.getByText(/not saved to your account yet/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Continue to your account" }));
    expect(await screen.findByRole("heading", { name: "Authenticated home" })).toBeInTheDocument();
    expect(isOnboardingCompleteThisTab(profile.id)).toBe(true);
    expect(sessionStorage.getItem(`lexaware-onboarding-complete-this-tab:${profile.id}`)).toBe("true");
  });

  it("allows the informational introduction to be skipped without collecting personal data", async () => {
    const user = userEvent.setup(); renderOnboarding();
    await user.click(await screen.findByRole("button", { name: "Skip introduction" }));
    expect(await screen.findByRole("heading", { name: "Authenticated home" })).toBeInTheDocument();
    expect(isOnboardingCompleteThisTab(profile.id)).toBe(true);
  });
});
