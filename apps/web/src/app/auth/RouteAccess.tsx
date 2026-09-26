import { Navigate, Outlet, useLocation } from "react-router";
import { useAuth } from "./auth-context";
import { isOnboardingCompleteThisTab } from "./onboarding-state";
import { StatePanel } from "../../shared/components/StatePanel";
import { Button } from "../../shared/components/Button";

function CheckingSession() {
  return <div className="route-message"><StatePanel kind="info" title="Checking your session">One moment while we check your account securely.</StatePanel></div>;
}

export function SessionProblem() {
  const { refreshSession, session } = useAuth();
  return <div className="route-message"><StatePanel kind="error" title="We couldn’t check your session">Check your connection and try again. Passwords and session tokens are not stored in browser storage.</StatePanel><Button className="route-message__retry" disabled={session.status === "loading"} onClick={() => void refreshSession()}>{session.status === "loading" ? "Checking…" : "Try again"}</Button></div>;
}

function destination(userId: string) { return isOnboardingCompleteThisTab(userId) ? "/app" : "/onboarding"; }

export function PublicAuthRoute() {
  const { session } = useAuth();
  if (session.status === "loading") return <CheckingSession />;
  if (session.status === "error") return <SessionProblem />;
  if (session.status === "authenticated") return <Navigate replace to={destination(session.user.id)} />;
  return <Outlet />;
}

export function ProtectedRoute({ allowBeforeOnboarding = false }: { allowBeforeOnboarding?: boolean }) {
  const { session } = useAuth();
  const location = useLocation();
  if (session.status === "loading") return <CheckingSession />;
  if (session.status === "error") return <SessionProblem />;
  if (session.status === "unauthenticated") {
    if (session.reason === "signed-out") return <Navigate replace to="/" />;
    return <Navigate replace to="/login" state={{ from: location, sessionExpired: session.reason === "expired" }} />;
  }
  if (!allowBeforeOnboarding && !isOnboardingCompleteThisTab(session.user.id)) return <Navigate replace to="/onboarding" />;
  return <Outlet />;
}
