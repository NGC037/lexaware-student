import { useEffect, useRef, useState, type FormEvent } from "react";
import { governedHelpApi, type GovernedContentFilters, type GovernedHelpResource } from "../../api/student-content";
import { StatePanel } from "../../shared/components/StatePanel";

function safeHttpUrl(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : null;
  } catch { return null; }
}

function formatDate(value: string): string | null {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? null : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeZone: "UTC" }).format(date);
}

export function HelpDirectoryPage() {
  const [draft, setDraft] = useState({ category: "", jurisdiction: "", assistance_type: "" });
  const [filters, setFilters] = useState<GovernedContentFilters>({});
  const [resources, setResources] = useState<GovernedHelpResource[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [retry, setRetry] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreError, setMoreError] = useState(false);
  const moreController = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    moreController.current?.abort(); setLoadingMore(false); setMoreError(false); setHasMore(false);
    setState("loading");
    governedHelpApi.list({ ...filters, limit: 50 }, controller.signal)
      .then((result) => { setResources(result); setHasMore(result.length === 50); setState("ready"); })
      .catch(() => { if (!controller.signal.aborted) setState("error"); });
    return () => { controller.abort(); moreController.current?.abort(); };
  }, [filters, retry]);

  async function loadMore() {
    if (loadingMore || !hasMore) return;
    const controller = new AbortController(); moreController.current = controller;
    setLoadingMore(true); setMoreError(false);
    try {
      const result = await governedHelpApi.list({ ...filters, limit: 50, offset: resources.length }, controller.signal);
      if (!controller.signal.aborted) { setResources((current) => [...current, ...result]); setHasMore(result.length === 50); }
    } catch { if (!controller.signal.aborted) setMoreError(true); }
    finally { if (!controller.signal.aborted) setLoadingMore(false); }
  }

  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFilters({ category: draft.category.trim(), jurisdiction: draft.jurisdiction.trim(), assistance_type: draft.assistance_type.trim() });
  }

  function clear() {
    setDraft({ category: "", jurisdiction: "", assistance_type: "" });
    setFilters({});
  }

  return <div className="workspace-page governed-page">
    <header className="governed-hero page-container">
      <p className="eyebrow">Currently verified resources</p>
      <h1>Help directory</h1>
      <p>Browse current, source-backed services and contact information. Check the listed jurisdiction and source details to decide whether a resource is relevant to you.</p>
    </header>
    <section className="governed-filter page-container" aria-label="Filter help resources">
      <form onSubmit={apply}>
        <label>Category<input value={draft.category} onChange={(event) => setDraft((value) => ({ ...value, category: event.target.value }))} maxLength={80} /></label>
        <label>Jurisdiction code<input value={draft.jurisdiction} onChange={(event) => setDraft((value) => ({ ...value, jurisdiction: event.target.value }))} maxLength={32} /></label>
        <label>Assistance type<input value={draft.assistance_type} onChange={(event) => setDraft((value) => ({ ...value, assistance_type: event.target.value }))} maxLength={80} /></label>
        <div className="governed-filter__actions"><button className="button button--primary" type="submit">Apply filters</button><button className="button button--outline" type="button" onClick={clear}>Clear</button></div>
      </form>
    </section>
    <section className="governed-results page-container" aria-labelledby="help-results-title">
      <h2 id="help-results-title">Verified resources</h2>
      {state === "loading" && <StatePanel kind="info" title="Loading verified resources">Retrieving resources that are currently available.</StatePanel>}
      {state === "error" && <><StatePanel kind="error" title="The help directory is temporarily unavailable">Please check your connection and try again.</StatePanel><button className="workspace-retry" type="button" onClick={() => setRetry((value) => value + 1)}>Try again</button></>}
      {state === "ready" && resources.length === 0 && <StatePanel title="No verified resources found">Try changing or clearing the category, jurisdiction, or assistance type filters.</StatePanel>}
      {state === "ready" && resources.length > 0 && <><ul className="governed-list">{resources.map((resource) => {
        const contactUrl = safeHttpUrl(resource.contact_url);
        const sourceUrl = safeHttpUrl(resource.source_url);
        const phone = resource.phone?.replace(/[^\d+*#]/g, "");
        const email = resource.contact_email?.trim();
        return <li key={resource.id}><article className="governed-entry help-entry">
          <p className="governed-entry__meta">{resource.resource_type} <span aria-hidden="true">·</span> {resource.assistance_type}</p>
          <h3>{resource.name}</h3>
          <p className="help-entry__category">{resource.category} <span aria-hidden="true">·</span> {resource.jurisdiction.name}</p>
          {resource.description && <p>{resource.description}</p>}
          <dl className="help-entry__details"><dt>Contact method</dt><dd>{resource.contact_method.replaceAll("_", " ")}</dd><dt>Verification</dt><dd>Verified {formatDate(resource.verified_at) ?? "date unavailable"}</dd></dl>
          <div className="help-entry__links" aria-label={`Contact ${resource.name}`}>
            {phone && <a href={`tel:${phone}`}>Call {resource.phone}</a>}
            {email && <a href={`mailto:${encodeURIComponent(email)}`}>Email {email}</a>}
            {contactUrl && <a href={contactUrl} target="_blank" rel="noopener noreferrer">Visit resource website <span aria-hidden="true">↗</span></a>}
          </div>
          <footer className="governed-entry__source"><span>Source: {resource.source_title}{resource.source_publisher ? ` · ${resource.source_publisher}` : ""}{resource.source_citation ? ` · ${resource.source_citation}` : ""}</span><span>Retrieved {formatDate(resource.source_retrieved_at) ?? "date unavailable"}</span>{sourceUrl && <a href={sourceUrl} target="_blank" rel="noopener noreferrer">View source</a>}</footer>
        </article></li>;
      })}</ul>{moreError && <div className="rights-more-error" role="status">More resources could not be loaded. <button type="button" onClick={() => void loadMore()}>Try again</button></div>}{hasMore && <button className="button button--outline rights-load-more" type="button" disabled={loadingMore} onClick={() => void loadMore()}>{loadingMore ? "Loading..." : "Load more resources"}</button>}</>}
    </section>
  </div>;
}
