import { request } from "./client";

export type OperationsItem = { id: string; category: string; status: string; created_at: string; label?: string | null };
export type OperationsOverview = {
  stale_content: OperationsItem[];
  failed_analyses: OperationsItem[];
  provider_errors: OperationsItem[];
  user_reports: OperationsItem[];
  unresolved_feedback: OperationsItem[];
};

export const operationsApi = {
  overview(signal?: AbortSignal) {
    return request<OperationsOverview>("/admin/operations", { signal });
  },
  resolveFeedback(id: string) {
    return request<void>(`/admin/operations/feedback/${encodeURIComponent(id)}/resolve`, { method: "POST", body: {} });
  },
};
