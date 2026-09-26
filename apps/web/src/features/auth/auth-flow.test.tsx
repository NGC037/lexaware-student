import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import { authApi, type MeResponse } from "../../api/auth";
import { AuthProvider } from "../../app/auth/AuthProvider";
import { ThemeProvider } from "../../app/theme/ThemeProvider";
import { markOnboardingCompleteThisTab } from "../../app/auth/onboarding-state";
import { ProtectedRoute } from "../../app/auth/RouteAccess";
import { AuthenticatedLayout } from "../../shared/layout/AuthenticatedLayout";
import { LoginPage } from "./LoginPage";
import { RegisterPage } from "./RegisterPage";

vi.mock("../../api/auth", () => ({ authApi: { register: vi.fn(), login: vi.fn(), me: vi.fn(), logout: vi.fn() } }));
const api = vi.mocked(authApi);
const userProfile: MeResponse = { id: "student-1", email: "student@example.test", display_name: "Sam Student", roles: ["student"], status: "active", session_expires_at: "2030-01-01T00:00:00Z" };
const unauthorized = () => new ApiError(401, { message: "Authentication required" });

function renderRegister() { return render(<MemoryRouter><RegisterPage /></MemoryRouter>); }
function renderWithSession(children: React.ReactNode, initial = "/login") {
  return render(<MemoryRouter initialEntries={[initial]}><AuthProvider><Routes>
    <Route path="/login" element={children} />
    <Route path="/onboarding" element={<h1>Onboarding destination</h1>} />
    <Route path="/app" element={<h1>Application destination</h1>} />
    <Route path="/" element={<h1>Public home</h1>} />
  </Routes></AuthProvider></MemoryRouter>);
}

describe("registration, login, and protected session flows", () => {
  beforeEach(() => {
    sessionStorage.clear(); vi.clearAllMocks();
    api.me.mockRejectedValue(unauthorized());
  });
  afterEach(cleanup);

  it("validates registration and confirms through the backend response without an email enumeration claim", async () => {
    const user = userEvent.setup();
    api.register.mockResolvedValue({ email: "student@example.test", message: "Registration received. If your email is eligible and not already registered, your account has been created. You may now log in." });
    renderRegister();
    await user.type(screen.getByLabelText("Name (optional)"), "Sam Student");
    await user.type(screen.getByLabelText("Email"), "student@example.test");
    await user.type(screen.getByLabelText("Password"), "UncommonPassphrase78");
    await user.type(screen.getByLabelText("Confirm password"), "UncommonPassphrase78");
    await user.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByRole("heading", { name: "Check what to do next" })).toBeInTheDocument();
    expect(api.register).toHaveBeenCalledWith({ email: "student@example.test", password: "UncommonPassphrase78", display_name: "Sam Student" });
    expect(screen.getByText(/same confirmation whether or not an address was already registered/i)).toBeInTheDocument();
    expect(screen.queryByText("UncommonPassphrase78")).not.toBeInTheDocument();
  });

  it("catches password mismatch before sending credentials", async () => {
    const user = userEvent.setup(); renderRegister();
    await user.type(screen.getByLabelText("Email"), "student@example.test");
    await user.type(screen.getByLabelText("Password"), "LongEnoughPassphrase1");
    await user.type(screen.getByLabelText("Confirm password"), "LongEnoughPassphrase2");
    await user.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The passwords do not match");
    expect(api.register).not.toHaveBeenCalled();
  });

  it("prevents duplicate registration submissions while the request is pending", async () => {
    const user = userEvent.setup();
    let finish: ((result: { email: string; message: string }) => void) | undefined;
    api.register.mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
    renderRegister();
    await user.type(screen.getByLabelText("Email"), "student@example.test");
    await user.type(screen.getByLabelText("Password"), "LongEnoughPassphrase1");
    await user.type(screen.getByLabelText("Confirm password"), "LongEnoughPassphrase1");
    const submit = screen.getByRole("button", { name: "Create account" });
    await user.click(submit);
    expect(submit).toBeDisabled();
    await user.click(submit);
    expect(api.register).toHaveBeenCalledOnce();
    finish?.({ email: "student@example.test", message: "Registration received." });
    expect(await screen.findByRole("heading", { name: "Check what to do next" })).toBeInTheDocument();
  });

  it("shows a safe network error and preserves the registration address", async () => {
    const user = userEvent.setup(); api.register.mockRejectedValue(new TypeError("socket ECONNRESET with internal details")); renderRegister();
    await user.type(screen.getByLabelText("Email"), "student@example.test");
    await user.type(screen.getByLabelText("Password"), "LongEnoughPassphrase1");
    await user.type(screen.getByLabelText("Confirm password"), "LongEnoughPassphrase1");
    await user.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("We couldn’t reach LexAware");
    expect(screen.getByLabelText("Email")).toHaveValue("student@example.test");
    expect(screen.queryByText(/ECONNRESET|internal details/i)).not.toBeInTheDocument();
  });

  it("logs in, verifies /me, and navigates to onboarding for this tab", async () => {
    const user = userEvent.setup(); api.me.mockRejectedValueOnce(unauthorized()).mockResolvedValueOnce(userProfile); api.login.mockResolvedValue(userProfile);
    renderWithSession(<LoginPage />);
    await user.type(screen.getByLabelText("Email"), "student@example.test");
    await user.type(screen.getByLabelText("Password"), "CorrectHorseBatteryStaple");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("heading", { name: "Onboarding destination" })).toBeInTheDocument();
    expect(api.login).toHaveBeenCalledWith({ email: "student@example.test", password: "CorrectHorseBatteryStaple" });
    expect(api.me).toHaveBeenCalledTimes(2);
  });

  it("clears the password and safely reports invalid credentials while retaining email", async () => {
    const user = userEvent.setup(); api.login.mockRejectedValue(new ApiError(401, { message: "Invalid email or password" })); renderWithSession(<LoginPage />);
    await user.type(screen.getByLabelText("Email"), "student@example.test");
    await user.type(screen.getByLabelText("Password"), "WrongPassword123");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The email or password is incorrect");
    expect(screen.getByLabelText("Email")).toHaveValue("student@example.test");
    expect(screen.getByLabelText("Password")).toHaveValue("");
  });

  it("recovers from a login network failure without exposing internal error text", async () => {
    const user = userEvent.setup(); api.login.mockRejectedValue(new TypeError("ECONNRESET db.internal")); renderWithSession(<LoginPage />);
    await user.type(screen.getByLabelText("Email"), "student@example.test");
    await user.type(screen.getByLabelText("Password"), "CorrectHorseBatteryStaple");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("We couldn’t reach LexAware");
    expect(screen.queryByText(/ECONNRESET|db.internal/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveValue("student@example.test");
    expect(screen.getByLabelText("Password")).toHaveValue("");
  });

  it("redirects unauthenticated visitors away from /app", async () => {
    render(<MemoryRouter initialEntries={["/app"]}><AuthProvider><Routes>
      <Route element={<ProtectedRoute />}><Route path="/app" element={<h1>Private app</h1>} /></Route><Route path="/login" element={<h1>Sign in route</h1>} />
    </Routes></AuthProvider></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Sign in route" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Private app" })).not.toBeInTheDocument();
  });

  it("allows authenticated users into /app after tab onboarding and logs out through the API", async () => {
    const user = userEvent.setup(); markOnboardingCompleteThisTab(userProfile.id); api.me.mockResolvedValue(userProfile); api.logout.mockResolvedValue({ message: "Successfully logged out" });
    render(<MemoryRouter initialEntries={["/app"]}><ThemeProvider><AuthProvider><Routes>
      <Route element={<ProtectedRoute />}><Route element={<AuthenticatedLayout />}><Route path="/app" element={<h1>Private app</h1>} /></Route></Route><Route path="/" element={<h1>Public home</h1>} /><Route path="/login" element={<h1>Sign in</h1>} />
    </Routes></AuthProvider></ThemeProvider></MemoryRouter>);
    await user.click(await screen.findByRole("button", { name: "Log out" }));
    expect(await screen.findByRole("heading", { name: "Public home" })).toBeInTheDocument();
    await waitFor(() => expect(api.logout).toHaveBeenCalledOnce());
  });
});
