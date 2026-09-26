import { request } from "./client";
export type HealthResponse = { status: string; service: string; version: string };
/** Liveness only. Readiness dependencies belong to operational tooling. */
export function getHealth(signal?: AbortSignal) { return request<HealthResponse>("/health", { signal }); }
