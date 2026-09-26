import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, setUnauthorizedHandler } from "../../api/client";
import { authApi } from "../../api/auth";
import { SessionEstablishmentError } from "./session-errors";
import { AuthContext, type SessionState } from "./auth-context";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<SessionState>({ status: "loading" });

  const refreshSession = useCallback(async (signal?: AbortSignal): Promise<SessionState> => {
    setSession({ status: "loading" });
    try {
      const user = await authApi.me(signal);
      const next: SessionState = { status: "authenticated", user };
      if (!signal?.aborted) setSession(next);
      return next;
    } catch (error) {
      if (signal?.aborted) return { status: "loading" };
      const next: SessionState = error instanceof ApiError && error.status === 401
        ? { status: "unauthenticated", reason: "expired" }
        : { status: "error" };
      setSession(next);
      return next;
    }
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => setSession({ status: "unauthenticated", reason: "expired" }));
    const controller = new AbortController();
    void refreshSession(controller.signal);
    return () => {
      controller.abort();
      setUnauthorizedHandler(undefined);
    };
  }, [refreshSession]);

  useEffect(() => {
    if (session.status !== "authenticated" || !session.user.session_expires_at) return;
    const expiry = Date.parse(session.user.session_expires_at);
    if (!Number.isFinite(expiry)) return;
    let timeout = 0;
    const checkExpiry = () => {
      const remaining = expiry - Date.now();
      if (remaining <= 0) { void refreshSession(); return; }
      timeout = window.setTimeout(checkExpiry, Math.min(remaining + 100, 2_147_000_000));
    };
    checkExpiry();
    return () => window.clearTimeout(timeout);
  }, [session, refreshSession]);

  const signIn = useCallback(async (email: string, password: string) => {
    try { await authApi.login({ email, password }); }
    catch (error) {
      if (error instanceof ApiError && error.status === 401) setSession({ status: "unauthenticated" });
      else if (!(error instanceof ApiError) || error.status >= 500) setSession({ status: "error" });
      throw error;
    }
    try {
      const user = await authApi.me();
      setSession({ status: "authenticated", user });
      return user;
    } catch {
      setSession({ status: "unauthenticated" });
      throw new SessionEstablishmentError();
    }
  }, []);

  const signOut = useCallback(async () => {
    try {
      await authApi.logout();
      setSession({ status: "unauthenticated", reason: "signed-out" });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setSession({ status: "unauthenticated", reason: "signed-out" });
        return;
      }
      throw error;
    }
  }, []);

  const value = useMemo(() => ({ session, refreshSession, signIn, signOut }), [session, refreshSession, signIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

