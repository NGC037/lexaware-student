import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { knowledgeApi, type KnowledgeCategory, type KnowledgeJurisdiction, type StudentArticle } from "../../api/student-content";
import { StatePanel } from "../../shared/components/StatePanel";

const PAGE_SIZE = 12;

function safeSource(value: string): string | null {
  try { const url = new URL(value); return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : null; }
  catch { return null; }
}

function formatDate(value: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? null : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeZone: "UTC" }).format(date);
}

export function RightsExplorerPage() {
  const [categories, setCategories] = useState<KnowledgeCategory[]>([]);
  const [jurisdictions, setJurisdictions] = useState<KnowledgeJurisdiction[]>([]);
  const [filtersState, setFiltersState] = useState<"loading" | "ready" | "error">("loading");
  const [draftQuery, setDraftQuery] = useState("");
  const [draftCategory, setDraftCategory] = useState("");
  const [draftJurisdiction, setDraftJurisdiction] = useState("");
  const [applied, setApplied] = useState({ q: "", category: "", jurisdiction: "" });
  const [articles, setArticles] = useState<StudentArticle[]>([]);
  const [listState, setListState] = useState<"loading" | "ready" | "error">("loading");
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreError, setMoreError] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [retry, setRetry] = useState(0);
  const moreController = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setFiltersState("loading");
    Promise.all([knowledgeApi.listCategories(undefined, controller.signal), knowledgeApi.listJurisdictions(controller.signal)])
      .then(([nextCategories, nextJurisdictions]) => { setCategories(nextCategories); setJurisdictions(nextJurisdictions); setFiltersState("ready"); })
      .catch(() => { if (!controller.signal.aborted) setFiltersState("error"); });
    return () => controller.abort();
  }, [retry]);

  useEffect(() => {
    const controller = new AbortController();
    moreController.current?.abort();
    setLoadingMore(false);
    setListState("loading"); setArticles([]); setHasMore(false); setMoreError(false);
    knowledgeApi.listArticles({ ...applied, limit: PAGE_SIZE, offset: 0 }, controller.signal)
      .then((result) => { setArticles(result); setHasMore(result.length === PAGE_SIZE); setListState("ready"); })
      .catch(() => { if (!controller.signal.aborted) setListState("error"); });
    return () => { controller.abort(); moreController.current?.abort(); };
  }, [applied, retry]);

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setApplied({ q: draftQuery.trim().slice(0, 200), category: draftCategory, jurisdiction: draftJurisdiction });
  }

  function clearFilters() {
    setDraftQuery(""); setDraftCategory(""); setDraftJurisdiction("");
    setApplied({ q: "", category: "", jurisdiction: "" });
  }

  async function loadMore() {
    if (loadingMore || !hasMore) return;
    const controller = new AbortController();
    moreController.current = controller;
    setLoadingMore(true); setMoreError(false);
    try {
      const next = await knowledgeApi.listArticles({ ...applied, limit: PAGE_SIZE, offset: articles.length }, controller.signal);
      if (!controller.signal.aborted) {
        setArticles((current) => [...current, ...next]); setHasMore(next.length === PAGE_SIZE);
      }
    } catch { if (!controller.signal.aborted) setMoreError(true); }
    finally { if (!controller.signal.aborted) setLoadingMore(false); }
  }

  return <div className="workspace-page rights-page">
    <section className="rights-hero page-container" aria-labelledby="rights-title">
      <p className="eyebrow">Reviewed legal information</p>
      <h1 id="rights-title">Know Your Rights</h1>
      <p>Explore published guidance for students and practical considerations. Applicability can depend on your circumstances and location; review each source and consider qualified help for your situation.</p>
    </section>
    <section className="rights-explorer page-container" aria-label="Search and filter guidance">
      <form className="rights-filters" onSubmit={applyFilters}>
        <label className="rights-search">Search guidance
          <input type="search" value={draftQuery} maxLength={200} onChange={(event) => setDraftQuery(event.target.value)} placeholder="Try a topic or phrase" />
        </label>
        <label>Category
          <select value={draftCategory} onChange={(event) => setDraftCategory(event.target.value)} disabled={filtersState !== "ready"}>
            <option value="">All categories</option>{categories.map((item) => <option key={item.category} value={item.category}>{item.category}</option>)}
          </select>
        </label>
        <label>Jurisdiction
          <select value={draftJurisdiction} onChange={(event) => setDraftJurisdiction(event.target.value)} disabled={filtersState !== "ready"}>
            <option value="">All jurisdictions</option>{jurisdictions.map((item) => <option key={item.code} value={item.code}>{item.name}</option>)}
          </select>
        </label>
        <div className="rights-filter-actions"><button className="button button--primary" type="submit">Apply filters</button><button className="button button--outline" type="button" onClick={clearFilters}>Clear</button></div>
      </form>
      {filtersState === "error" && <div className="rights-filter-error" role="status">Some filters could not be loaded. You can still browse published guidance. <button type="button" onClick={() => setRetry((value) => value + 1)}>Retry filters</button></div>}
    </section>
    <section className="rights-results page-container" aria-labelledby="rights-results-title">
      <div className="rights-results-heading"><div><p className="eyebrow">Student knowledge base</p><h2 id="rights-results-title">Published guidance</h2></div></div>
      {listState === "loading" && <StatePanel kind="info" title="Loading published guidance">Showing current guidance that applies to students.</StatePanel>}
      {listState === "error" && <div><StatePanel kind="error" title="Guidance is temporarily unavailable">Please check your connection and try again.</StatePanel><button className="workspace-retry" type="button" onClick={() => setRetry((value) => value + 1)}>Try again</button></div>}
      {listState === "ready" && articles.length === 0 && <StatePanel kind="empty" title="No guidance matched these filters">Try a broader search or clear one or more filters.</StatePanel>}
      {listState === "ready" && articles.length > 0 && <>
        <ul className="rights-article-list">{articles.map((article) => {
          const source = safeSource(article.source_url);
          return <li key={article.id} className="rights-article"><div className="rights-article__meta"><span>{article.category}</span>{article.topic && <span>{article.topic}</span>}<span>{article.jurisdiction.name}</span></div>
            <h3><Link to={"/app/rights/" + encodeURIComponent(article.slug)}>{article.title}</Link></h3>
            {article.summary && <p>{article.summary}</p>}
            {article.applicability_notes && <p className="rights-article__applicability"><strong>Applicability:</strong> {article.applicability_notes}</p>}
            <div className="rights-article__source"><span>{article.last_reviewed_at && <>Last reviewed {formatDate(article.last_reviewed_at)}</>}{article.effective_from && <>; Effective {formatDate(article.effective_from)}</>}</span><span>{article.source_title}{article.source_publisher ? " | " + article.source_publisher : ""}{article.source_citation ? " | " + article.source_citation : ""}</span></div>
            <div className="rights-article__actions"><Link className="text-link--strong" to={"/app/rights/" + encodeURIComponent(article.slug)}>Read guidance <span aria-hidden="true">&rarr;</span></Link>{source && <a href={source} target="_blank" rel="noopener noreferrer">View source <span aria-hidden="true">&nearr;</span></a>}</div>
          </li>;
        })}</ul>
        {moreError && <div role="status" className="rights-more-error">More guidance could not be loaded. <button type="button" onClick={() => void loadMore()}>Try again</button></div>}
        {hasMore && <button className="button button--outline rights-load-more" type="button" onClick={() => void loadMore()} disabled={loadingMore}>{loadingMore ? "Loading..." : "Load more guidance"}</button>}
      </>}
    </section>
  </div>;
}
