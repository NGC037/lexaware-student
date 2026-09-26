import { request } from "./client";

export type StudentArticle = {
  id: string;
  slug: string;
  title: string;
  category: string;
  topic: string | null;
  audience: string;
  summary: string | null;
  applicability_notes: string | null;
  escalation_guidance: string | null;
  jurisdiction: { id: string; code: string; name: string; parent_id: string | null };
  effective_from: string | null;
  last_reviewed_at: string | null;
  source_title: string | null;
  source_publisher: string | null;
  source_url: string;
  source_citation: string | null;
};

export type HelpResource = {
  id: string;
  name: string;
  category: string;
  resource_type: string;
  assistance_type: string;
  contact_method: "phone" | "website" | "email" | "in_person" | "multiple";
  description: string | null;
  contact_url: string | null;
  phone: string | null;
  contact_email: string | null;
  jurisdiction: { code: string; name: string };
  source_title: string;
  source_publisher: string | null;
  source_url: string;
  source_citation: string | null;
  source_retrieved_at: string;
  verified_at: string;
  status: "verified_current";
};

export const knowledgeApi = {
  searchArticles(query: string, signal?: AbortSignal) {
    const params = new URLSearchParams({ q: query, audience: "students", limit: "4" });
    return request<StudentArticle[]>(`/knowledge/articles?${params.toString()}`, { signal });
  },
};

export const helpApi = {
  list(signal?: AbortSignal) {
    return request<HelpResource[]>("/help?limit=3", { signal });
  },
};
