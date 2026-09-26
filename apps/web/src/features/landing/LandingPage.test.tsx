import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { ThemeProvider } from "../../app/theme/ThemeProvider";
import { SiteHeader } from "../../shared/layout/SiteHeader";
import { LandingPage } from "./LandingPage";

function renderWithShell(ui: React.ReactNode) { return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>); }
describe("frontend foundation", () => {
  afterEach(cleanup);
  beforeEach(() => localStorage.clear());
  it("presents the student-focused promise and legal boundary", () => {
    renderWithShell(<LandingPage />);
    expect(screen.getByRole("heading", { level: 1, name: /know your rights/i })).toBeInTheDocument();
    expect(screen.getByText(/information, not legal advice/i)).toBeInTheDocument();
    expect(screen.getByText(/does not provide those tools yet/i)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /explore support/i }).length).toBeGreaterThan(0);
  });
  it("exposes a keyboard-operable mobile navigation toggle", async () => {
    const user = userEvent.setup(); renderWithShell(<SiteHeader />);
    const toggle = screen.getByRole("button", { name: "Open navigation menu" });
    for (let index = 0; index < 7; index += 1) await user.tab();
    expect(toggle).toHaveFocus(); await user.keyboard("{Enter}");
    expect(screen.getByRole("button", { name: "Close navigation menu" })).toHaveAttribute("aria-expanded", "true");
    const mobileNav = screen.getByRole("navigation", { name: "Mobile navigation" });
    await user.click(within(mobileNav).getByRole("link", { name: "How it works" }));
    expect(screen.getByRole("button", { name: "Open navigation menu" })).toHaveAttribute("aria-expanded", "false");
  });
  it("persists explicit theme choice and clears it on system preference", async () => {
    const user = userEvent.setup(); renderWithShell(<><SiteHeader /><div /></>);
    const select = screen.getByRole("combobox", { name: "Color theme" });
    await user.selectOptions(select, "dark"); expect(document.documentElement).toHaveAttribute("data-theme", "dark"); expect(localStorage.getItem("lexaware-theme")).toBe("dark");
    await user.selectOptions(select, "system"); expect(localStorage.getItem("lexaware-theme")).toBeNull();
  });
});
