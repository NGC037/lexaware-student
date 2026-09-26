import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router";
import { complaintApi, type ComplaintGuide, type GovernedContentFilters } from "../../api/student-content";
import { ApiError } from "../../api/client";
import { StatePanel } from "../../shared/components/StatePanel";

function formatDate(value: string): string | null {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? null : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeZone: "UTC" }).format(date);
}

export function ComplaintGuidesPage() {
  const [draft, setDraft] = useState({ category: "", jurisdiction: "" });
  const [filters, setFilters] = useState<GovernedContentFilters>({});
  const [guides, setGuides] = useState<ComplaintGuide[]>([]);
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
    complaintApi.list({ ...filters, limit: 50 }, controller.signal)
      .then((result) => { setGuides(result); setHasMore(result.length === 50); setState("ready"); })
      .catch(() => { if (!controller.signal.aborted) setState("error"); });
    return () => { controller.abort(); moreController.current?.abort(); };
  }, [filters, retry]);

  async function loadMore() {
    if (loadingMore || !hasMore) return;
    const controller = new AbortController(); moreController.current = controller;
    setLoadingMore(true); setMoreError(false);
    try {
      const result = await complaintApi.list({ ...filters, limit: 50, offset: guides.length }, controller.signal);
      if (!controller.signal.aborted) { setGuides((current) => [...current, ...result]); setHasMore(result.length === 50); }
    } catch { if (!controller.signal.aborted) setMoreError(true); }
    finally { if (!controller.signal.aborted) setLoadingMore(false); }
  }

  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFilters({ category: draft.category.trim(), jurisdiction: draft.jurisdiction.trim() });
  }

  function clear() {
    setDraft({ category: "", jurisdiction: "" });
    setFilters({});
  }

  return <div className="workspace-page governed-page">
    <header className="governed-hero page-container">
      <p className="eyebrow">Published and reviewed information</p>
      <h1>Complaint guidance</h1>
      <p>Explore current guidance for students. These guides provide general information and do not file a complaint or replace advice from an appropriate professional or institution.</p>
    </header>
    <section className="governed-filter page-container" aria-label="Filter complaint guidance">
      <form onSubmit={apply}>
        <label>Category<input value={draft.category} onChange={(event) => setDraft((value) => ({ ...value, category: event.target.value }))} maxLength={80} /></label>
        <label>Jurisdiction code<input value={draft.jurisdiction} onChange={(event) => setDraft((value) => ({ ...value, jurisdiction: event.target.value }))} maxLength={32} /></label>
        <div className="governed-filter__actions"><button className="button button--primary" type="submit">Apply filters</button><button className="button button--outline" type="button" onClick={clear}>Clear</button></div>
      </form>
    </section>
    <section className="governed-results page-container" aria-labelledby="complaint-results-title">
      <h2 id="complaint-results-title">Available guides</h2>
      {state === "loading" && <StatePanel kind="info" title="Loading published guides">Retrieving current student guidance.</StatePanel>}
      {state === "error" && <><StatePanel kind="error" title="Complaint guidance is temporarily unavailable">Please check your connection and try again.</StatePanel><button className="workspace-retry" type="button" onClick={() => setRetry((value) => value + 1)}>Try again</button></>}
      {state === "ready" && guides.length === 0 && <StatePanel title="No published guides found">Try changing or clearing the category or jurisdiction filters.</StatePanel>}
      {state === "ready" && guides.length > 0 && <><ul className="governed-list">{guides.map((guide) => <li key={guide.id}>
        <article className="governed-entry"><p className="governed-entry__meta">{guide.category} <span aria-hidden="true">·</span> {guide.jurisdiction.name}</p><h3><Link to={`/app/complaints/${encodeURIComponent(guide.slug)}`}>{guide.title}</Link></h3><p>{guide.short_description}</p><p className="governed-entry__source">Reviewed {formatDate(guide.reviewed_at) ?? "date unavailable"}</p></article>
      </li>)}</ul>{moreError && <div className="rights-more-error" role="status">More guides could not be loaded. <button type="button" onClick={() => void loadMore()}>Try again</button></div>}{hasMore && <button className="button button--outline rights-load-more" type="button" disabled={loadingMore} onClick={() => void loadMore()}>{loadingMore ? "Loading..." : "Load more guides"}</button>}</>}
    </section>
  </div>;
}

export function ComplaintGuidePage() {
  const { slug = "" } = useParams();
  const [guide, setGuide] = useState<ComplaintGuide | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error" | "not-found">("loading");
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState("loading"); setGuide(null);
    complaintApi.get(slug, controller.signal).then((result) => { setGuide(result); setState("ready"); })
      .catch((error: unknown) => { if (!controller.signal.aborted) setState(error instanceof ApiError && error.status === 404 ? "not-found" : "error"); });
    return () => controller.abort();
  }, [slug, retry]);

  return <div className="workspace-page governed-page governed-detail page-container">
    <Link className="governed-back" to="/app/complaints">&larr; All complaint guides</Link>
    {state === "loading" && <StatePanel kind="info" title="Loading guide">Retrieving published student guidance.</StatePanel>}
    {state === "error" && <><StatePanel kind="error" title="This guide is temporarily unavailable">Please check your connection and try again.</StatePanel><button className="workspace-retry" type="button" onClick={() => setRetry((value) => value + 1)}>Try again</button></>}
    {state === "not-found" && <StatePanel title="This guide is not currently available">It may have changed or may no longer be published. Return to the current guide list.</StatePanel>}
    {state === "ready" && guide && <article className="complaint-guide" aria-labelledby="complaint-guide-title">
      <header><p className="eyebrow">{guide.category} · {guide.jurisdiction.name}</p><h1 id="complaint-guide-title">{guide.title}</h1><p className="complaint-guide__summary">{guide.short_description}</p><p className="governed-entry__source">For {guide.audience} · Reviewed {formatDate(guide.reviewed_at) ?? "date unavailable"}</p></header>
      {guide.guidance_steps.length > 0 && <section aria-labelledby="guidance-steps-title"><h2 id="guidance-steps-title">Guidance</h2><ol className="guidance-steps">{[...guide.guidance_steps].sort((a, b) => a.position - b.position).map((step) => <li key={step.position}><span className="guidance-steps__number" aria-hidden="true">{step.position}</span><div><p className="guidance-steps__section">{step.section.replaceAll("_", " ")}</p><h3>{step.title}</h3><p>{step.instruction}</p></div></li>)}</ol></section>}
    </article>}
  </div>;
}
