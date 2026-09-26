import { request } from "./client";

export type AssistantRequest = {
  message: string;
  jurisdiction?: string;
  topic?: string;
};

export type AssistantStatus =
  | "answer"
  | "clarify"
  | "refuse"
  | "escalate"
  | "out_of_scope"
  | "provider_unavailable"
  | "retrieval_unavailable";

export type AssistantErrorCode =
  | "ASSISTANT_INVALID_REQUEST"
  | "ASSISTANT_UNSAFE_REQUEST"
  | "ASSISTANT_OUT_OF_SCOPE"
  | "ASSISTANT_PROVIDER_UNAVAILABLE"
  | "ASSISTANT_GROUNDING_FAILED"
  | "ASSISTANT_RESPONSE_INVALID"
  | "ASSISTANT_RETRIEVAL_UNAVAILABLE";

export type AssistantClassification = {
  intent: "legal_awareness" | "definitive_verdict" | "evidence_concealment" | "out_of_scope";
  urgency: "routine" | "soon" | "immediate";
  risk_level: "low" | "elevated" | "high" | "critical";
  category:
    | "none"
    | "immediate_danger"
    | "threats"
    | "violence"
    | "sexual_violence"
    | "self_harm"
    | "child_safety"
    | "extortion"
    | "active_financial_fraud"
    | "imminent_deadline"
    | "evidence_concealment"
    | "definitive_verdict"
    | "unsupported_topic"
    | "jurisdiction_required"
    | "jurisdiction_mismatch";
  jurisdiction_state: "not_provided" | "provided" | "required" | "mismatch";
  escalation_required: boolean;
  clarification_required: boolean;
  deterministic: true;
};

export type AssistantSource = {
  title: string;
  url: string;
  citation: string | null;
  jurisdiction: string;
  effective_from: string | null;
  last_reviewed_at: string | null;
  review_due_at: string | null;
  knowledge_reference: string;
};

export type AssistantUrgentResource = {
  name: string;
  category: string;
  assistance_type: string;
  contact_method: string;
  contact_url: string | null;
  phone: string | null;
  email: string | null;
  jurisdiction: string;
  source_title: string;
  source_url: string;
  verified_at: string;
};

export type AssistantTrace = {
  correlation_id: string;
  route: AssistantStatus;
  risk_level: AssistantClassification["risk_level"];
  risk_category: AssistantClassification["category"];
  prompt_id: string;
  prompt_version: string;
  response_schema_version: string;
  retrieval_version: string;
  embedding_model: string | null;
  retrieval_state: string;
  provider_name: string | null;
  model_identifier: string | null;
  knowledge_references: string[];
  validation_outcomes: Record<string, boolean>;
  failure_category: AssistantErrorCode | null;
  provider_status: string | null;
  provider_latency_ms: number | null;
  started_at: string;
  completed_at: string;
};

type AssistantResponseFields = {
  classification: AssistantClassification;
  what_this_may_mean: string;
  relevant_facts_or_dependencies: string[];
  next_steps: { text: string }[];
  urgent_help: string;
  urgent_resources: AssistantUrgentResource[];
  sources: AssistantSource[];
  limitations: string[];
  uncertainty: string;
  escalation: string;
  error_code?: AssistantErrorCode | null;
  trace: AssistantTrace;
};

export type AssistantResponse = AssistantResponseFields & (
  | { status: "answer" }
  | { status: "clarify" }
  | { status: "refuse" }
  | { status: "escalate" }
  | { status: "out_of_scope" }
  | { status: "provider_unavailable" }
  | { status: "retrieval_unavailable" }
);

export const assistantApi = {
  send(payload: AssistantRequest, signal?: AbortSignal) {
    return request<AssistantResponse>("/assistant/messages", {
      method: "POST",
      body: payload,
      signal,
    });
  },
};
