import { createContext, useContext } from "react";
import type { MeResponse } from "../../api/auth";

export type SessionState =
  | { status: "loading" }
  | { status: "authenticated"; user: MeResponse }
  | { status: "unauthenticated"; reason?: "expired" | "signed-out" }
  | { status: "error" };
export type AuthContextValue = {
  session: SessionState;
  refreshSession: (signal?: AbortSignal) => Promise<SessionState>;
  signIn: (email: string, password: string) => Promise<MeResponse>;
  signOut: () => Promise<void>;
};
export const AuthContext = createContext<AuthContextValue | null>(null);
export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
