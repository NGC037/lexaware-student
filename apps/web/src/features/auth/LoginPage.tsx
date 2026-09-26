import { useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import { Button } from "../../shared/components/Button";
import { safeLoginError } from "./form-messages";
import { useAuth } from "../../app/auth/auth-context";
import { isOnboardingCompleteThisTab } from "../../app/auth/onboarding-state";

type LoginLocationState = { registration?: { message: string; email: string }; from?: { pathname?: string }; sessionExpired?: boolean };
export function LoginPage() {
  const { signIn } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as LoginLocationState | null;
  const [email, setEmail] = useState(state?.registration?.email ?? "");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const errorRef = useRef<HTMLDivElement>(null);
  const submitting = useRef(false);

  function fail(message: string) { setError(message); requestAnimationFrame(() => errorRef.current?.focus()); }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current) return;
    setError("");
    const emailField = event.currentTarget.elements.namedItem("email");
    if (!(emailField instanceof HTMLInputElement) || !emailField.validity.valid) { fail("Enter a valid email address."); return; }
    if (!email.trim() || !password || password.length > 128) { fail("Enter your email and password to continue."); return; }
    submitting.current = true; setBusy(true);
    try {
      const user = await signIn(email.trim(), password);
      setPassword("");
      const path = isOnboardingCompleteThisTab(user.id) ? "/app" : "/onboarding";
      navigate(path, { replace: true });
    } catch (requestError) {
      setPassword(""); fail(safeLoginError(requestError));
    } finally { submitting.current = false; setBusy(false); }
  }

  return <section aria-labelledby="login-title" className="auth-card">
    <p className="eyebrow">Welcome back</p><h1 id="login-title">Sign in to LexAware</h1>
    {state?.registration && <div className="auth-success" role="status">{state.registration.message}</div>}
    {state?.sessionExpired && <div className="auth-success" role="status">Your session could not be verified. Sign in again to continue.</div>}
    {error && <div className="form-error" ref={errorRef} role="alert" tabIndex={-1}>{error}</div>}
    <form aria-busy={busy} noValidate onSubmit={(event) => void submit(event)}>
      <div className="form-field"><label htmlFor="login-email">Email</label><input autoComplete="username" id="login-email" maxLength={320} name="email" onChange={(event) => setEmail(event.target.value)} required type="email" value={email} /></div>
      <div className="form-field"><label htmlFor="login-password">Password</label><div className="password-input"><input autoComplete="current-password" id="login-password" maxLength={128} onChange={(event) => setPassword(event.target.value)} required type={showPassword ? "text" : "password"} value={password} /><button aria-label={showPassword ? "Hide password" : "Show password"} className="password-toggle" onClick={() => setShowPassword((show) => !show)} type="button">{showPassword ? "Hide" : "Show"}</button></div></div>
      <Button className="auth-card__full-button" disabled={busy} type="submit">{busy ? "Signing in…" : "Sign in"}</Button>
      {busy && <p className="form-progress" role="status">Checking your account…</p>}
    </form>
    <p className="auth-card__switch">Don’t have an account? <Link to="/register">Create one</Link></p>
    <p className="auth-card__notice">Your session is managed securely by LexAware. Password recovery is not currently available.</p>
  </section>;
}
