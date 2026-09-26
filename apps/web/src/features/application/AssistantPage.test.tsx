import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import { assistantApi, type AssistantResponse } from "../../api/assistant";
import { AssistantPage } from "./AssistantPage";

vi.mock("../../api/assistant", () => ({ assistantApi: { send: vi.fn() } }));

function makeResponse(status: AssistantResponse["status"]): AssistantResponse {
  return {
    status,
    classification: {
      intent: "legal_awareness", urgency: "routine", risk_level: "low", category: "none",
      jurisdiction_state: "provided", escalation_required: false, clarification_required: false, deterministic: true,
    },
    what_this_may_mean: `Backend guidance for ${status}.`,
    relevant_facts_or_dependencies: [], next_steps: [], urgent_help: "", urgent_resources: [], sources: [],
    limitations: [], uncertainty: "", escalation: "", error_code: null,
    trace: {
      correlation_id: "trace-private", route: status, risk_level: "low", risk_category: "none", prompt_id: "private-prompt",
      prompt_version: "2.0.0", response_schema_version: "assistant-response-v2", retrieval_version: "private-retrieval",
      embedding_model: null, retrieval_state: "grounded", provider_name: "private-provider", model_identifier: "private-model",
      knowledge_references: [], validation_outcomes: {}, failure_category: null, provider_status: null, provider_latency_ms: null,
      started_at: "2026-09-01T00:00:00Z", completed_at: "2026-09-01T00:00:01Z",
    },
  };
}

describe("guided legal awareness assistant", () => {
  beforeEach(() => vi.mocked(assistantApi.send).mockReset());
  afterEach(cleanup);

  it.each([
    ["answer", "Guidance response"],
    ["clarify", "A little more information may help"],
    ["refuse", "The assistant can’t support that request"],
    ["escalate", "Guidance for your next step"],
    ["out_of_scope", "Outside the supported guidance scope"],
    ["provider_unavailable", "The assistant is temporarily unavailable"],
    ["retrieval_unavailable", "Current guidance could not be retrieved"],
  ] as const)("renders the %s response state", async (status, heading) => {
    vi.mocked(assistantApi.send).mockResolvedValue(makeResponse(status));
    const user = userEvent.setup();
    render(<AssistantPage />);
    await user.type(screen.getByRole("textbox", { name: "What would you like help understanding?" }), "What should I understand?");
    await user.click(screen.getByRole("button", { name: "Get guidance" }));
    expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
    expect(screen.getByText(`Backend guidance for ${status}.`)).toBeInTheDocument();
    expect(screen.queryByText(/private-prompt|private-retrieval|private-provider|private-model|trace-private/)).not.toBeInTheDocument();
  });

  it("validates blank input, shows a character count, and trims optional request fields", async () => {
    vi.mocked(assistantApi.send).mockResolvedValue(makeResponse("clarify"));
    const user = userEvent.setup();
    render(<AssistantPage />);
    const message = screen.getByRole("textbox", { name: "What would you like help understanding?" });
    expect(message).toHaveAttribute("maxLength", "4000");
    await user.type(message, "   ");
    await user.click(screen.getByRole("button", { name: "Get guidance" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Enter a question");
    expect(assistantApi.send).not.toHaveBeenCalled();

    await user.clear(message);
    await user.type(message, "  What does this clause mean?  ");
    await user.type(screen.getByRole("textbox", { name: /Jurisdiction code/ }), " IN ");
    await user.type(screen.getByRole("textbox", { name: /Topic/ }), " contract ");
    expect(screen.getByText("31 / 4000 characters")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Get guidance" }));
    await screen.findByRole("heading", { name: "A little more information may help" });
    expect(assistantApi.send).toHaveBeenCalledWith({ message: "What does this clause mean?", jurisdiction: "IN", topic: "contract" }, expect.any(AbortSignal));
  });

  it("allows exactly 4000 characters and prevents entry beyond the backend limit", async () => {
    vi.mocked(assistantApi.send).mockResolvedValue(makeResponse("answer"));
    render(<AssistantPage />);
    const message = screen.getByRole("textbox", { name: "What would you like help understanding?" });
    fireEvent.change(message, { target: { value: "x".repeat(4000) } });
    expect(message).toHaveValue("x".repeat(4000));
    expect(screen.getByText("4000 / 4000 characters")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Get guidance" }));
    await screen.findByRole("heading", { name: "Guidance response" });
    expect(assistantApi.send).toHaveBeenCalledWith({ message: "x".repeat(4000) }, expect.any(AbortSignal));
    expect(message).toHaveAttribute("maxLength", "4000");
  });

  it("checks optional-field constraints without sending invalid data", async () => {
    const user = userEvent.setup();
    render(<AssistantPage />);
    await user.type(screen.getByRole("textbox", { name: "What would you like help understanding?" }), "A legal question");
    await user.type(screen.getByRole("textbox", { name: /Jurisdiction code/ }), "I");
    await user.click(screen.getByRole("button", { name: "Get guidance" }));
    expect(screen.getByRole("alert")).toHaveTextContent("between 2 and 32 characters");
    expect(assistantApi.send).not.toHaveBeenCalled();
  });

  it("announces loading and prevents duplicate submissions while pending", async () => {
    let resolveRequest: (value: AssistantResponse) => void = () => undefined;
    vi.mocked(assistantApi.send).mockReturnValue(new Promise((resolve) => { resolveRequest = resolve; }));
    const user = userEvent.setup();
    render(<AssistantPage />);
    await user.type(screen.getByRole("textbox", { name: "What would you like help understanding?" }), "Question one");
    await user.click(screen.getByRole("button", { name: "Get guidance" }));
    const submit = screen.getByRole("button", { name: "Getting guidance…" });
    expect(submit).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("The request is being checked against current reviewed sources.");
    await user.click(submit);
    expect(assistantApi.send).toHaveBeenCalledTimes(1);
    resolveRequest(makeResponse("answer"));
    expect(await screen.findByRole("heading", { name: "Guidance response" })).toBeInTheDocument();
  });

  it("renders governed sources, limitations, uncertainty, and returned resources safely", async () => {
    const result = makeResponse("escalate");
    result.urgent_help = "Move to a safer place if possible.";
    result.escalation = result.urgent_help;
    result.urgent_resources = [{
      name: "Verified support service", category: "support", assistance_type: "student support", contact_method: "multiple",
      contact_url: "https://support.example.test", phone: "+91 123 456", email: "help@example.test", jurisdiction: "India",
      source_title: "Official directory", source_url: "https://source.example.test", verified_at: "2026-08-01T00:00:00Z",
    }];
    result.sources = [
      { title: "Current source", url: "https://law.example.test/source", citation: "Section 4", jurisdiction: "India", effective_from: null, last_reviewed_at: "2026-08-01T00:00:00Z", review_due_at: null, knowledge_reference: "guide:v1" },
      { title: "Unsafe source", url: "javascript:alert(1)", citation: null, jurisdiction: "India", effective_from: null, last_reviewed_at: null, review_due_at: null, knowledge_reference: "unsafe:v1" },
    ];
    result.limitations = ["General awareness only."];
    result.uncertainty = "A professional can assess your circumstances.";
    vi.mocked(assistantApi.send).mockResolvedValue(result);
    const user = userEvent.setup();
    render(<AssistantPage />);
    await user.type(screen.getByRole("textbox", { name: "What would you like help understanding?" }), "I need guidance");
    await user.click(screen.getByRole("button", { name: "Get guidance" }));
    expect(await screen.findByRole("heading", { name: "Guidance for your next step" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Sources" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^View source$/ })).toHaveAttribute("href", "https://law.example.test/source");
    expect(screen.queryByRole("link", { name: /Unsafe source/ })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Limitations" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Uncertainty" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Call \+91 123 456/ })).toHaveAttribute("href", "tel:+91123456");
    expect(screen.getByRole("link", { name: /Visit resource website/ })).toHaveAttribute("href", "https://support.example.test/");
  });

  it("replaces the prior result with a new independent request and persists neither request nor response", async () => {
    vi.mocked(assistantApi.send).mockResolvedValueOnce(makeResponse("answer")).mockResolvedValueOnce(makeResponse("clarify"));
    const user = userEvent.setup();
    const view = render(<AssistantPage />);
    const message = screen.getByRole("textbox", { name: "What would you like help understanding?" });
    await user.type(message, "First question");
    await user.click(screen.getByRole("button", { name: "Get guidance" }));
    expect(await screen.findByRole("heading", { name: "Guidance response" })).toBeInTheDocument();
    await user.clear(message); await user.type(message, "Second question");
    await user.click(screen.getByRole("button", { name: "Get guidance" }));
    expect(await screen.findByRole("heading", { name: "A little more information may help" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Guidance response" })).not.toBeInTheDocument();
    expect(assistantApi.send).toHaveBeenNthCalledWith(1, { message: "First question" }, expect.any(AbortSignal));
    expect(assistantApi.send).toHaveBeenNthCalledWith(2, { message: "Second question" }, expect.any(AbortSignal));
    expect(window.location.search).toBe("");
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
    view.unmount();
    render(<AssistantPage />);
    expect(screen.getByRole("textbox", { name: "What would you like help understanding?" })).toHaveValue("");
    expect(screen.queryByRole("heading", { name: "A little more information may help" })).not.toBeInTheDocument();
  });

  it("uses a safe service error message without exposing server details", async () => {
    vi.mocked(assistantApi.send).mockImplementationOnce(async () => { throw new ApiError(503, { message: "Gemini API key secret diagnostic" }); });
    const user = userEvent.setup();
    render(<AssistantPage />);
    await user.type(screen.getByRole("textbox", { name: "What would you like help understanding?" }), "A supported question");
    await user.click(screen.getByRole("button", { name: "Get guidance" }));
    expect(await screen.findByRole("heading", { name: "Guidance could not be provided" })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("The service could not complete this request");
    expect(screen.queryByText(/Gemini API key secret diagnostic/)).not.toBeInTheDocument();
  });
});
