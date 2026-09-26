import { useRef, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { authApi, type RegisterResponse } from "../../api/auth";
import { Button } from "../../shared/components/Button";
import { StatePanel } from "../../shared/components/StatePanel";
import { safeRegistrationError } from "./form-messages";

export function RegisterPage() {
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<RegisterResponse | null>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  const submitting = useRef(false);

  function fail(message: string) {
    setError(message);
    requestAnimationFrame(() => errorRef.current?.focus());
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current) return;
    setError("");
    const emailField = event.currentTarget.elements.namedItem("email");
    if (!(emailField instanceof HTMLInputElement) || !emailField.validity.valid) { fail("Enter a valid email address."); return; }
    if (password.length < 12 || password.length > 128) { fail("Use a password between 12 and 128 characters."); return; }
    if (password !== confirmPassword) { fail("The passwords do not match."); return; }

    submitting.current = true; setBusy(true);
    try {
      const response = await authApi.register({ email: email.trim(), password, ...(displayName.trim() ? { display_name: displayName.trim() } : {}) });
      setPassword(""); setConfirmPassword(""); setResult(response);
    } catch (requestError) {
      setPassword(""); setConfirmPassword(""); fail(safeRegistrationError(requestError));
    } finally { submitting.current = false; setBusy(false); }
  }

  if (result) return <section aria-labelledby="registration-result-title" className="auth-card auth-card--result">
    <p className="eyebrow">Registration received</p><h1 id="registration-result-title">Check what to do next</h1>
    <StatePanel kind="info" title="Your request was received">{result.message}</StatePanel>
    <p className="auth-card__support">For privacy, LexAware gives the same confirmation whether or not an address was already registered.</p>
    <Link className="button button--primary auth-card__full-button" state={{ registration: result }} to="/login">Continue to sign in</Link>
  </section>;

  return <section aria-labelledby="register-title" className="auth-card">
    <p className="eyebrow">A clear place to begin</p><h1 id="register-title">Create your LexAware account</h1>
    <p className="auth-card__intro">Understand your rights. Understand your documents. Take the right next step.</p>
    {error && <div className="form-error" ref={errorRef} role="alert" tabIndex={-1}>{error}</div>}
    <form aria-busy={busy} noValidate onSubmit={(event) => void submit(event)}>
      <div className="form-field"><label htmlFor="display-name">Name <span>(optional)</span></label><input autoComplete="name" id="display-name" maxLength={200} onChange={(event) => setDisplayName(event.target.value)} value={displayName} /></div>
      <div className="form-field"><label htmlFor="register-email">Email</label><input autoComplete="email" id="register-email" maxLength={320} name="email" onChange={(event) => setEmail(event.target.value)} required type="email" value={email} /></div>
      <div className="form-field"><label htmlFor="register-password">Password</label><div className="password-input"><input aria-describedby="password-guidance" autoComplete="new-password" id="register-password" maxLength={128} minLength={12} onChange={(event) => setPassword(event.target.value)} required type={showPassword ? "text" : "password"} value={password} /><button aria-label={showPassword ? "Hide password" : "Show password"} className="password-toggle" onClick={() => setShowPassword((show) => !show)} type="button">{showPassword ? "Hide" : "Show"}</button></div><small id="password-guidance">Use 12–128 characters. Commonly used passwords are rejected.</small></div>
      <div className="form-field"><label htmlFor="confirm-password">Confirm password</label><input autoComplete="new-password" id="confirm-password" maxLength={128} onChange={(event) => setConfirmPassword(event.target.value)} required type={showPassword ? "text" : "password"} value={confirmPassword} /></div>
      <Button className="auth-card__full-button" disabled={busy} type="submit">{busy ? "Creating account…" : "Create account"}</Button>
      {busy && <p className="form-progress" role="status">Sending your registration securely…</p>}
    </form>
    <p className="auth-card__switch">Already have an account? <Link to="/login">Sign in</Link></p>
    <p className="auth-card__notice">LexAware provides legal awareness and guided support. It does not replace advice from a qualified legal professional.</p>
  </section>;
}
