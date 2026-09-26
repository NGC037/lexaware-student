import { useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { useAuth } from "../../app/auth/auth-context";
import { Brand } from "../components/Brand";
import { Button } from "../components/Button";
import { ThemeControl } from "../theme/ThemeControl";

export function AuthenticatedLayout() {
  const { session, signOut } = useAuth();
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const user = session.status === "authenticated" ? session.user : null;

  async function logout() {
    if (busy) return;
    setBusy(true); setError(false);
    try { await signOut(); navigate("/", { replace: true }); }
    catch { setError(true); }
    finally { setBusy(false); }
  }

  return <div className="app-site"><header className="app-header"><div className="page-container app-header__inner"><Brand to="/app" /><nav aria-label="Workspace navigation"><NavLink end to="/app">Home</NavLink><Link to="/onboarding">Getting started</Link>{location.pathname === "/app" && <a href="#dashboard-support">Support</a>}</nav><div className="app-header__actions"><ThemeControl /><span className="app-header__user">{user?.display_name || user?.email}</span><Button disabled={busy} onClick={() => void logout()} variant="outline">{busy ? "Signing out…" : "Log out"}</Button></div></div></header>
    {error && <p className="logout-error" role="alert">We couldn’t end your session. Check your connection and try again.</p>}
    <main id="main-content" tabIndex={-1}><Outlet /></main><footer className="site-footer app-site__footer"><div className="page-container site-footer__bottom"><span>LexAware Student</span><span>Legal awareness and guided support, not legal advice.</span></div></footer></div>;
}
