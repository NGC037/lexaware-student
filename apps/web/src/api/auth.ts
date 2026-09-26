import { request } from "./client";

export type RegisterRequest = { email: string; password: string; display_name?: string };
export type RegisterResponse = { message: string; email: string };
export type LoginRequest = { email: string; password: string };
export type UserResponse = { id: string; email: string; display_name: string | null; roles: string[]; status: string };
export type MeResponse = UserResponse & { session_expires_at: string | null };
type CsrfResponse = { csrf_token: string };
type MessageResponse = { message: string };

export const authApi = {
  register(input: RegisterRequest) {
    return request<RegisterResponse>("/auth/register", { method: "POST", body: input });
  },
  login(input: LoginRequest) {
    return request<UserResponse>("/auth/login", { method: "POST", body: input });
  },
  me(signal?: AbortSignal) {
    return request<MeResponse>("/auth/me", { signal });
  },
  async logout() {
    // The backend requires the readable CSRF cookie and matching header for cookie sessions.
    const { csrf_token } = await request<CsrfResponse>("/auth/csrf");
    return request<MessageResponse>("/auth/logout", { method: "POST", body: {}, headers: { "X-CSRF-Token": csrf_token } });
  },
};
