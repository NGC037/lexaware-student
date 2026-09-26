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

export type KnowledgeCategory = { category: string; article_count: number };
export type KnowledgeJurisdiction = { id: string; code: string; name: string; parent_id: string | null };
export type StudentArticleFilters = {
  q?: string;
  category?: string;
  jurisdiction?: string;
  limit?: number;
  offset?: number;
};
export type StudentArticleDetail = Omit<StudentArticle, "source_title" | "source_publisher" | "source_url" | "source_citation"> & {
  version_number: number;
  content: string;
  source: {
    id: string;
    jurisdiction_id: string;
    title: string;
    publisher: string | null;
    source_url: string;
    citation: string | null;
    retrieved_at: string;
    effective_from: string | null;
    effective_until: string | null;
    is_active: boolean;
  };
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

export type ComplaintGuide = {
  id: string;
  slug: string;
  version_number: number;
  title: string;
  category: string;
  audience: string;
  short_description: string;
  jurisdiction: { id: string; code: string; name: string };
  guidance_steps: { position: number; section: string; title: string; instruction: string }[];
  reviewed_at: string;
};

export type GovernedHelpResource = HelpResource;

export type GovernedContentFilters = { category?: string; jurisdiction?: string; assistance_type?: string; limit?: number; offset?: number };

function queryString(filters: GovernedContentFilters = {}) {
  const params = new URLSearchParams();
  for (const key of ["category", "jurisdiction", "assistance_type"] as const) {
    const value = filters[key]?.trim();
    if (value) params.set(key, value);
  }
  params.set("limit", String(filters.limit ?? 50));
  params.set("offset", String(filters.offset ?? 0));
  return params.toString();
}

export const complaintApi = {
  list(filters: GovernedContentFilters = {}, signal?: AbortSignal) {
    const params = new URLSearchParams(queryString(filters));
    params.set("audience", "students");
    return request<ComplaintGuide[]>(`/complaints/guides?${params.toString()}`, { signal });
  },
  get(slug: string, signal?: AbortSignal) {
    return request<ComplaintGuide>(`/complaints/guides/${encodeURIComponent(slug)}`, { signal });
  },
};

export const governedHelpApi = {
  list(filters: GovernedContentFilters = {}, signal?: AbortSignal) {
    return request<GovernedHelpResource[]>(`/help?${queryString(filters)}`, { signal });
  },
};

export const knowledgeApi = {
  listArticles(filters: StudentArticleFilters = {}, signal?: AbortSignal) {
    const params = new URLSearchParams({ audience: "students", limit: String(filters.limit ?? 12), offset: String(filters.offset ?? 0) });
    const query = filters.q?.trim();
    if (query) params.set("q", query);
    if (filters.category) params.set("category", filters.category);
    if (filters.jurisdiction) params.set("jurisdiction", filters.jurisdiction);
    return request<StudentArticle[]>(`/knowledge/articles?${params.toString()}`, { signal });
  },
  searchArticles(query: string, signal?: AbortSignal) {
    return this.listArticles({ q: query, limit: 4 }, signal);
  },
  listCategories(jurisdiction?: string, signal?: AbortSignal) {
    const params = new URLSearchParams();
    if (jurisdiction) params.set("jurisdiction", jurisdiction);
    return request<KnowledgeCategory[]>(`/knowledge/categories${params.size ? `?${params.toString()}` : ""}`, { signal });
  },
  listJurisdictions(signal?: AbortSignal) {
    return request<KnowledgeJurisdiction[]>("/knowledge/jurisdictions", { signal });
  },
  getArticle(slug: string, signal?: AbortSignal) {
    return request<StudentArticleDetail>(`/knowledge/articles/${encodeURIComponent(slug)}`, { signal });
  },
};

export const helpApi = {
  list(signal?: AbortSignal) {
    return request<HelpResource[]>("/help?limit=3", { signal });
  },
};
