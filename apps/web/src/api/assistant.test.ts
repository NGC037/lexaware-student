import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./client";
import { assistantApi, type AssistantResponse } from "./assistant";

describe("assistant API client", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockImplementation(() => Promise.resolve(new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } })));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    document.cookie = "lexaware_csrf=; Max-Age=0; path=/";
  });

  it("posts only the typed assistant request through the shared cookie and CSRF client", async () => {
    document.cookie = "lexaware_csrf=csrf-test-token; path=/";
    await assistantApi.send({ message: "What does this clause mean?", jurisdiction: "IN", topic: "contract" });
    const [input, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new URL(input).pathname).toBe("/api/v1/assistant/messages");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("include");
    expect(new Headers(init.headers).get("X-CSRF-Token")).toBe("csrf-test-token");
    expect(JSON.parse(String(init.body))).toEqual({ message: "What does this clause mean?", jurisdiction: "IN", topic: "contract" });
  });

  it("preserves the structured response contract", async () => {
    const response: AssistantResponse = {
      status: "answer", classification: {
        intent: "legal_awareness", urgency: "routine", risk_level: "low", category: "none",
        jurisdiction_state: "provided", escalation_required: false, clarification_required: false, deterministic: true,
      }, what_this_may_mean: "Governed guidance may apply.", relevant_facts_or_dependencies: [], next_steps: [], urgent_help: "", urgent_resources: [],
      sources: [], limitations: ["General awareness only."], uncertainty: "The facts matter.", escalation: "", error_code: null,
      trace: {
        correlation_id: "trace-id", route: "answer", risk_level: "low", risk_category: "none", prompt_id: "prompt",
        prompt_version: "2.0.0", response_schema_version: "assistant-response-v2", retrieval_version: "retrieval-v2",
        embedding_model: null, retrieval_state: "grounded", provider_name: "gemini", model_identifier: "model", knowledge_references: [],
        validation_outcomes: {}, failure_category: null, provider_status: "complete", provider_latency_ms: 1,
        started_at: "2026-01-01T00:00:00Z", completed_at: "2026-01-01T00:00:01Z",
      },
    };
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(response), { status: 200, headers: { "Content-Type": "application/json" } }));
    const result = await assistantApi.send({ message: "question" });
    expect(result).toEqual(response);
    expect(result.status).toBe("answer");
  });

  it("normalizes validation envelopes without requiring vendor-specific errors", async () => {
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: "ASSISTANT_INVALID_REQUEST", message: "The assistant request is invalid." } }), {
      status: 422, headers: { "Content-Type": "application/json", "X-Correlation-ID": "correlation-id" },
    }));
    await expect(assistantApi.send({ message: "question" })).rejects.toMatchObject({
      name: "ApiError", status: 422, message: "The assistant request is invalid.", correlationId: "correlation-id",
    } satisfies Partial<ApiError>);
  });
});
