export type ApiErrorBody = { message: string; code?: string; fields?: unknown };

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly correlationId?: string;
  readonly fields?: unknown;
  constructor(status: number, body: ApiErrorBody, correlationId?: string) {
    super(body.message); this.name = "ApiError"; this.status = status; this.code = body.code; this.correlationId = correlationId; this.fields = body.fields;
  }
}

const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1").replace(/\/+$/, "");
const safeMethods = new Set(["GET", "HEAD", "OPTIONS"]);
let unauthorizedHandler: (() => void) | undefined;

export function setUnauthorizedHandler(handler: (() => void) | undefined) {
  unauthorizedHandler = handler;
}
function csrfToken(): string | undefined {
  const cookie = document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith("lexaware_csrf="));
  if (!cookie) return undefined;
  try { return decodeURIComponent(cookie.slice("lexaware_csrf=".length)); } catch { return undefined; }
}
function errorMessage(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map((entry) => typeof entry === "object" && entry !== null && "msg" in entry && typeof entry.msg === "string" ? entry.msg : "The request could not be completed.").join(" ");
  if (typeof value === "object" && value !== null && "message" in value && typeof value.message === "string") return value.message;
  return "The request could not be completed.";
}
export function normalizeError(status: number, payload: unknown, correlationId?: string): ApiError {
  if (typeof payload === "object" && payload !== null && "error" in payload) {
    const error = payload.error;
    if (typeof error === "object" && error !== null) {
      const record = error as Record<string, unknown>;
      return new ApiError(status, { message: errorMessage(record.message), code: typeof record.code === "string" ? record.code : undefined }, correlationId);
    }
  }
  if (typeof payload === "object" && payload !== null && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    return new ApiError(status, { message: errorMessage(detail), fields: Array.isArray(detail) ? detail : undefined }, correlationId);
  }
  return new ApiError(status, { message: errorMessage(payload) }, correlationId);
}

export type RequestOptions = Omit<RequestInit, "body"> & { body?: unknown; timeoutMs?: number };
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { timeoutMs = 15_000, body, headers: suppliedHeaders, ...init } = options;
  const method = (init.method ?? (body === undefined ? "GET" : "POST")).toUpperCase();
  const headers = new Headers(suppliedHeaders);
  if (body !== undefined && !(body instanceof FormData) && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (!safeMethods.has(method)) { const token = csrfToken(); if (token && !headers.has("X-CSRF-Token")) headers.set("X-CSRF-Token", token); }
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(new DOMException("Request timed out", "TimeoutError")), timeoutMs);
  try {
    const response = await fetch(`${baseUrl}${path.startsWith("/") ? path : `/${path}`}`, {
      ...init, method, headers, credentials: "include", signal: init.signal ? AbortSignal.any([controller.signal, init.signal]) : controller.signal,
      body: body === undefined ? undefined : body instanceof FormData || typeof body === "string" ? body : JSON.stringify(body),
    });
    const text = await response.text();
    let payload: unknown;
    try { payload = text ? JSON.parse(text) as unknown : undefined; } catch { payload = text; }
    if (!response.ok) {
      if (response.status === 401) unauthorizedHandler?.();
      throw normalizeError(response.status, payload, response.headers.get("X-Correlation-ID") ?? undefined);
    }
    return payload as T;
  } finally { window.clearTimeout(timeout); }
}
