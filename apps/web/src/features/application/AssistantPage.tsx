import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError } from "../../api/client";
import {
  assistantApi,
  type AssistantRequest,
  type AssistantResponse,
  type AssistantSource,
  type AssistantUrgentResource,
} from "../../api/assistant";
import { StatePanel } from "../../shared/components/StatePanel";

const MESSAGE_LIMIT = 4000;
const TOPIC_LIMIT = 120;

const statusHeadings: Record<AssistantResponse["status"], string> = {
  answer: "Guidance response",
  clarify: "A little more information may help",
  refuse: "The assistant can’t support that request",
  escalate: "Guidance for your next step",
  out_of_scope: "Outside the supported guidance scope",
  provider_unavailable: "The assistant is temporarily unavailable",
  retrieval_unavailable: "Current guidance could not be retrieved",
};

function safeHttpUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : null;
  } catch { return null; }
}

function formatDate(value: string | null | undefined): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? null : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeZone: "UTC" }).format(date);
}

function requestErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 400 || error.status === 422) return "Please check the question and optional details, then try again.";
    if (error.status === 401) return "Your session may have expired. Sign in again to continue.";
    if (error.status === 403) return "The secure session check could not be completed. Refresh and try again.";
    if (error.status === 404) return "The guidance service could not be reached. Please try again later.";
    if (error.status >= 500) return "The service could not complete this request. Please try again later.";
  }
  return "We could not connect to the guidance service. Check your connection and try again.";
}

function SourceEntry({ source }: { source: AssistantSource }) {
  const href = safeHttpUrl(source.url);
  return <li className="assistant-source">
    <h3>{source.title}</h3>
    {source.citation && <p>{source.citation}</p>}
    <p>{source.jurisdiction}{source.effective_from && <> · Effective {formatDate(source.effective_from)}</>}{source.last_reviewed_at && <> · Reviewed {formatDate(source.last_reviewed_at)}</>}{source.review_due_at && <> · Review due {formatDate(source.review_due_at)}</>}</p>
    {href && <a href={href} target="_blank" rel="noopener noreferrer">View source <span aria-hidden="true">↗</span></a>}
  </li>;
}

function UrgentResourceEntry({ resource }: { resource: AssistantUrgentResource }) {
  const contactUrl = safeHttpUrl(resource.contact_url);
  const sourceUrl = safeHttpUrl(resource.source_url);
  const phone = resource.phone?.replace(/[^\d+*#]/g, "");
  const email = resource.email?.trim();
  return <li className="assistant-resource">
    <h3>{resource.name}</h3>
    <p>{resource.category} · {resource.assistance_type} · {resource.jurisdiction}</p>
    <p>Contact method: {resource.contact_method.replaceAll("_", " ")} · Verified {formatDate(resource.verified_at) ?? "date unavailable"}</p>
    <div className="assistant-resource__links">
      {phone && <a href={`tel:${phone}`}>Call {resource.phone}</a>}
      {email && <a href={`mailto:${encodeURIComponent(email)}`}>Email {email}</a>}
      {contactUrl && <a href={contactUrl} target="_blank" rel="noopener noreferrer">Visit resource website</a>}
      {sourceUrl && <a href={sourceUrl} target="_blank" rel="noopener noreferrer">View source: {resource.source_title}</a>}
    </div>
  </li>;
}

function AssistantResult({ response }: { response: AssistantResponse }) {
  const urgentText = response.urgent_help && response.urgent_help !== response.escalation
    ? response.urgent_help
    : response.escalation;
  const hasSources = response.sources.length > 0;
  const hasLimitations = response.limitations.length > 0;

  return <div className={`assistant-result assistant-result--${response.status}`}>
    <header className="assistant-result__header">
      <p className="eyebrow">Response status</p>
      <h2>{statusHeadings[response.status]}</h2>
    </header>
    <div className="assistant-result__layout">
      <div className="assistant-result__main">
        {response.what_this_may_mean && <section className="assistant-answer-section"><h3>What this may mean</h3><p>{response.what_this_may_mean}</p></section>}
        {response.relevant_facts_or_dependencies.length > 0 && <section className="assistant-answer-section"><h3>Relevant facts or dependencies</h3><ul>{response.relevant_facts_or_dependencies.map((fact, index) => <li key={`${index}-${fact}`}>{fact}</li>)}</ul></section>}
        {response.next_steps.length > 0 && <section className="assistant-answer-section"><h3>What you can consider next</h3><ol>{response.next_steps.map((step, index) => <li key={`${index}-${step.text}`}>{step.text}</li>)}</ol></section>}
        {urgentText && <section className="assistant-answer-section"><h3>{response.status === "escalate" ? "Guidance for now" : "Additional guidance"}</h3><p>{urgentText}</p></section>}
        {response.urgent_resources.length > 0 && <section className="assistant-answer-section assistant-resources" aria-labelledby="assistant-resources-title"><h3 id="assistant-resources-title">Verified resources</h3><ul>{response.urgent_resources.map((resource, index) => <UrgentResourceEntry key={`${resource.name}-${index}`} resource={resource} />)}</ul></section>}
      </div>
      <aside className="assistant-result__support">
        {hasSources && <section className="assistant-source-section" aria-labelledby="assistant-sources-title"><h3 id="assistant-sources-title">Sources</h3><ul>{response.sources.map((source, index) => <SourceEntry key={`${source.knowledge_reference}-${index}`} source={source} />)}</ul></section>}
        {hasLimitations && <section className="assistant-support-section"><h3>Limitations</h3><ul>{response.limitations.map((limitation, index) => <li key={`${index}-${limitation}`}>{limitation}</li>)}</ul></section>}
        {response.uncertainty && <section className="assistant-support-section"><h3>Uncertainty</h3><p>{response.uncertainty}</p></section>}
      </aside>
    </div>
  </div>;
}

export function AssistantPage() {
  const [message, setMessage] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [topic, setTopic] = useState("");
  const [response, setResponse] = useState<AssistantResponse | null>(null);
  const [validationError, setValidationError] = useState("");
  const [requestError, setRequestError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [retry, setRetry] = useState(0);
  const activeRequest = useRef<AbortController | null>(null);

  useEffect(() => () => activeRequest.current?.abort(), []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    const trimmedMessage = message.trim();
    const trimmedJurisdiction = jurisdiction.trim();
    const trimmedTopic = topic.trim();
    if (!trimmedMessage) { setValidationError("Enter a question before requesting guidance."); return; }
    if (trimmedMessage.length > MESSAGE_LIMIT) { setValidationError(`Keep the question to ${MESSAGE_LIMIT} characters or fewer.`); return; }
    if (trimmedJurisdiction && (trimmedJurisdiction.length < 2 || trimmedJurisdiction.length > 32)) {
      setValidationError("A jurisdiction code must be between 2 and 32 characters."); return;
    }
    if (trimmedTopic.length > TOPIC_LIMIT) { setValidationError(`Keep the topic to ${TOPIC_LIMIT} characters or fewer.`); return; }

    const payload: AssistantRequest = {
      message: trimmedMessage,
      ...(trimmedJurisdiction ? { jurisdiction: trimmedJurisdiction } : {}),
      ...(trimmedTopic ? { topic: trimmedTopic } : {}),
    };
    const controller = new AbortController();
    activeRequest.current = controller;
    setValidationError(""); setRequestError(""); setResponse(null); setSubmitting(true); setRetry((value) => value + 1);
    try {
      const result = await assistantApi.send(payload, controller.signal);
      if (!controller.signal.aborted) setResponse(result);
    } catch (error) {
      if (!controller.signal.aborted) setRequestError(requestErrorMessage(error));
    } finally {
      if (!controller.signal.aborted) setSubmitting(false);
    }
  }

  return <div className="workspace-page assistant-page">
    <header className="assistant-hero page-container">
      <p className="eyebrow">Guided legal awareness</p>
      <h1>Understand a question or situation</h1>
      <p>This assistant offers general awareness guidance based on reviewed sources. It is not a lawyer or legal representative and cannot provide a binding legal conclusion.</p>
    </header>
    <section className="assistant-workspace page-container" aria-label="Ask for guided legal awareness">
      <form className="assistant-form" onSubmit={(event) => void submit(event)} noValidate>
        <label htmlFor="assistant-message">What would you like help understanding?</label>
        <p id="assistant-message-help" className="assistant-form__help">Each question is handled independently and is not saved as conversation history.</p>
        <textarea id="assistant-message" name="message" value={message} onChange={(event) => { setMessage(event.target.value); setValidationError(""); }} maxLength={MESSAGE_LIMIT} rows={7} aria-describedby={`assistant-message-help assistant-character-count${validationError ? " assistant-validation-error" : ""}`} aria-invalid={Boolean(validationError)} />
        <div className="assistant-form__meta"><span id="assistant-character-count">{message.length} / {MESSAGE_LIMIT} characters</span></div>
        <div className="assistant-form__optional">
          <label htmlFor="assistant-jurisdiction">Jurisdiction code <span>(optional)</span>
            <input id="assistant-jurisdiction" name="jurisdiction" value={jurisdiction} onChange={(event) => { setJurisdiction(event.target.value); setValidationError(""); }} maxLength={32} minLength={2} aria-describedby="assistant-jurisdiction-help" />
          </label>
          <p id="assistant-jurisdiction-help">A supported jurisdiction may help find applicable guidance. Leave blank if unsure.</p>
          <label htmlFor="assistant-topic">Topic <span>(optional)</span>
            <input id="assistant-topic" name="topic" value={topic} onChange={(event) => { setTopic(event.target.value); setValidationError(""); }} maxLength={TOPIC_LIMIT} aria-describedby="assistant-topic-help" />
          </label>
          <p id="assistant-topic-help">Add a brief context label if useful. Do not include information you do not want processed for this request.</p>
        </div>
        {validationError && <p id="assistant-validation-error" className="assistant-form__error" role="alert">{validationError}</p>}
        <div className="assistant-form__actions"><button className="button button--primary" type="submit" disabled={submitting}>{submitting ? "Getting guidance…" : "Get guidance"}</button><p>Questions are not stored in browser storage.</p></div>
      </form>
      <div className="assistant-response" aria-busy={submitting}>
        {submitting && <StatePanel kind="info" title="Getting guidance">The request is being checked against current reviewed sources.</StatePanel>}
        {requestError && <StatePanel kind="error" title="Guidance could not be provided">{requestError}</StatePanel>}
        {!submitting && !requestError && response && <><p className="visually-hidden" role="status" aria-live="polite">Guidance response received.</p><AssistantResult key={retry} response={response} /></>}
      </div>
    </section>
  </div>;
}
