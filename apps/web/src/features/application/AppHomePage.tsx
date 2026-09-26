import { useCallback, useEffect, useRef, useState, type FormEvent, type PointerEvent } from "react";
import { ArrowRight, BookOpen, Check, FileText, HeartHandshake, LifeBuoy, Search, ShieldCheck, Sparkles } from "lucide-react";
import { Link } from "react-router";
import { useAuth } from "../../app/auth/auth-context";
import { helpApi, knowledgeApi, type HelpResource, type StudentArticle } from "../../api/student-content";
import { StatePanel } from "../../shared/components/StatePanel";

type LoadState<T> = { kind: "loading" } | { kind: "error" } | { kind: "success"; items: T[] };

function safeExternalUrl(value: string): string | undefined {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : undefined;
  } catch { return undefined; }
}

function LexAwareMark() {
  const ref = useRef<HTMLDivElement>(null);
  function move(event: PointerEvent<HTMLDivElement>) {
    const box = event.currentTarget.getBoundingClientRect();
    if (!box.width || !box.height) return;
    const x = (event.clientX - box.left) / box.width - 0.5;
    const y = (event.clientY - box.top) / box.height - 0.5;
    ref.current?.style.setProperty("--mark-rx", `${-y * 8}deg`);
    ref.current?.style.setProperty("--mark-ry", `${x * 10}deg`);
  }
  function reset() {
    ref.current?.style.setProperty("--mark-rx", "0deg");
    ref.current?.style.setProperty("--mark-ry", "0deg");
  }
  return <div ref={ref} className="workspace-art" onPointerMove={move} onPointerLeave={reset}>
    <div className="workspace-art__orbit workspace-art__orbit--outer" aria-hidden="true" />
    <div className="workspace-art__orbit workspace-art__orbit--inner" aria-hidden="true" />
    <svg className="workspace-art__mark" viewBox="0 0 300 300" role="img" aria-labelledby="workspace-mark-title workspace-mark-description">
      <title id="workspace-mark-title">Protection, understanding, and a next step</title>
      <desc id="workspace-mark-description">A layered shield opens into a book, with a path leading forward.</desc>
      <path className="workspace-art__shadow" d="M150 35 235 65v77c0 51-35 91-85 112-50-21-85-61-85-112V65l85-30Z" />
      <path className="workspace-art__shield" d="M150 27 235 57v77c0 51-35 91-85 112-50-21-85-61-85-112V57l85-30Z" />
      <path className="workspace-art__page" d="M92 93c21-5 41 0 58 14v81c-18-13-38-18-58-13V93Zm116 0c-21-5-41 0-58 14v81c18-13 38-18 58-13V93Z" />
      <path className="workspace-art__page-lines" d="M105 112v44m90-44v44" />
      <path className="workspace-art__path" d="M160 158h28l-12-12m12 12-12 12" />
      <circle className="workspace-art__accent" cx="211" cy="88" r="7" />
    </svg>
    <div className="workspace-art__caption"><span><ShieldCheck size={16} aria-hidden="true" /> A clearer way forward</span></div>
  </div>;
}

function greeting() {
  const hour = new Date().getHours();
  return hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
}

export function AppHomePage() {
  const { session } = useAuth();
  const [query, setQuery] = useState("");
  const [searchState, setSearchState] = useState<LoadState<StudentArticle> | null>(null);
  const [helpState, setHelpState] = useState<LoadState<HelpResource>>({ kind: "loading" });
  const searchController = useRef<AbortController | null>(null);
  const user = session.status === "authenticated" ? session.user : null;

  const loadHelp = useCallback(async (signal?: AbortSignal) => {
    setHelpState({ kind: "loading" });
    try { setHelpState({ kind: "success", items: await helpApi.list(signal) }); }
    catch { if (!signal?.aborted) setHelpState({ kind: "error" }); }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    void loadHelp(controller.signal);
    return () => { controller.abort(); searchController.current?.abort(); };
  }, [loadHelp]);

  async function runSearch() {
    const term = query.trim();
    if (!term) return;
    searchController.current?.abort();
    const controller = new AbortController();
    searchController.current = controller;
    setSearchState({ kind: "loading" });
    try { setSearchState({ kind: "success", items: await knowledgeApi.searchArticles(term, controller.signal) }); }
    catch { if (!controller.signal.aborted) setSearchState({ kind: "error" }); }
  }

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runSearch();
  }

  if (!user) return null;
  return <div className="workspace-page">
    <section aria-labelledby="app-welcome-title" className="workspace-hero page-container">
      <div className="workspace-hero__copy">
        <p className="eyebrow"><span className="eyebrow__dot" /> YOUR LEXAWARE SPACE</p>
        <h1 id="app-welcome-title">{greeting()}{user.display_name ? `, ${user.display_name}` : ""}.</h1>
        <p className="workspace-hero__lead">What would you like to understand today?</p>
        <form className="command-search" onSubmit={(event) => void search(event)} role="search">
          <label className="visually-hidden" htmlFor="guidance-query">Search reviewed student guidance</label>
          <Search aria-hidden="true" size={19} />
          <input id="guidance-query" maxLength={200} onChange={(event) => setQuery(event.target.value)} placeholder="Search a topic or situation" value={query} />
          <button aria-label="Search published guidance" type="submit" disabled={!query.trim() || searchState?.kind === "loading"}><ArrowRight size={19} aria-hidden="true" /></button>
        </form>
        <p className="workspace-hero__note">Searches reviewed, currently published guidance. Your search is not saved.</p>
        <div className="workspace-principles" aria-label="Protection, understanding, next step"><span><ShieldCheck size={16} aria-hidden="true" /> Protection</span><i aria-hidden="true" /><span><BookOpen size={16} aria-hidden="true" /> Understanding</span><i aria-hidden="true" /><span><ArrowRight size={16} aria-hidden="true" /> Next step</span></div>
      </div>
      <LexAwareMark />
    </section>

    {searchState && <section aria-label="Guidance search results" aria-live="polite" className="workspace-results page-container">
      {searchState.kind === "loading" && <StatePanel kind="info" title="Searching reviewed guidance">Looking for currently published articles.</StatePanel>}
      {searchState.kind === "error" && <div><StatePanel kind="error" title="Search is temporarily unavailable">Your search was not saved. Please try again.</StatePanel><button className="workspace-retry" onClick={() => void runSearch()} type="button">Try again</button></div>}
      {searchState.kind === "success" && (searchState.items.length ? <>
        <div className="workspace-results__heading"><h2>Published guidance</h2><span>{Math.min(searchState.items.length, 4)} {searchState.items.length === 1 ? "result" : "results"}</span></div>
        <ul className="guidance-results">{searchState.items.slice(0, 4).map((article) => <li key={article.id}>
          <span className="guidance-results__category">{article.category}</span><h3>{article.title}</h3>{article.summary && <p>{article.summary}</p>}
          <p className="guidance-results__source">{article.jurisdiction.name}{article.last_reviewed_at ? ` · Reviewed ${new Date(article.last_reviewed_at).toLocaleDateString()}` : ""}</p>
          {safeExternalUrl(article.source_url) && <a href={safeExternalUrl(article.source_url)} rel="noreferrer noopener" target="_blank">View source{article.source_title ? `: ${article.source_title}` : ""}<ArrowRight size={15} aria-hidden="true" /></a>}
        </li>)}</ul>
      </> : <StatePanel kind="empty" title="No published guidance matched">Try a broader search term, or explore another topic later.</StatePanel>)}
    </section>}

    <section aria-labelledby="quick-actions-title" className="workspace-actions page-container">
      <div className="workspace-section-heading"><div><p className="eyebrow">START WITH WHAT YOU NEED</p><h2 id="quick-actions-title">A useful next step</h2></div><p>Choose a starting point. You can return here at any time.</p></div>
      <div className="workspace-action-list">
        <Link className="workspace-action workspace-action--primary" to="/app/rights"><span className="workspace-action__icon"><BookOpen size={22} aria-hidden="true" /></span><span><strong>Know your rights</strong><small>Search reviewed, source-backed student guidance.</small></span><ArrowRight className="workspace-action__arrow" size={19} aria-hidden="true" /></Link>
        <Link className="workspace-action workspace-action--support" to="/app/assistant"><span className="workspace-action__icon"><Sparkles size={22} aria-hidden="true" /></span><span><strong>Guided legal awareness</strong><small>Explore a question using current, reviewed sources.</small></span><ArrowRight className="workspace-action__arrow" size={19} aria-hidden="true" /></Link>
        <Link className="workspace-action workspace-action--support" to="/app/documents"><span className="workspace-action__icon"><FileText size={22} aria-hidden="true" /></span><span><strong>My Documents</strong><small>Review private PDFs, processing status, and available reports.</small></span><ArrowRight className="workspace-action__arrow" size={19} aria-hidden="true" /></Link>
        <a className="workspace-action workspace-action--support" href="#dashboard-support"><span className="workspace-action__icon"><HeartHandshake size={22} aria-hidden="true" /></span><span><strong>Find reviewed help</strong><small>See current, verified support contacts.</small></span><ArrowRight className="workspace-action__arrow" size={19} aria-hidden="true" /></a>
        <Link className="workspace-action workspace-action--support" to="/app/complaints"><span className="workspace-action__icon"><LifeBuoy size={22} aria-hidden="true" /></span><span><strong>Complaint guidance</strong><small>Explore published, reviewed guidance.</small></span><ArrowRight className="workspace-action__arrow" size={19} aria-hidden="true" /></Link>
      </div>
    </section>

    <div className="workspace-lower page-container">
      <section aria-labelledby="activity-title" className="workspace-activity"><p className="eyebrow">YOUR SPACE</p><h2 id="activity-title">Recent activity</h2><p>Your activity will appear here when account activity is available.</p><p className="workspace-muted">Saved items and announcements are not available yet.</p></section>
      <section aria-labelledby="dashboard-support-title" className="workspace-support" id="dashboard-support">
        <p className="eyebrow"><LifeBuoy size={15} aria-hidden="true" /> REVIEWED SUPPORT</p><h2 id="dashboard-support-title">Need help finding a next step?</h2><p className="workspace-support__intro">These contacts come from the currently verified support directory.</p><Link className="text-link--strong" to="/app/help">Browse the full help directory<ArrowRight size={15} aria-hidden="true" /></Link>
        {helpState.kind === "loading" && <div aria-label="Loading verified support contacts" className="workspace-skeleton" role="status"><span /><span /><span /></div>}
        {helpState.kind === "error" && <div className="workspace-support__state"><StatePanel kind="error" title="Support contacts are temporarily unavailable">Please try again. If you are in immediate danger, contact your local emergency service.</StatePanel><button className="workspace-retry" onClick={() => void loadHelp()} type="button">Try again</button></div>}
        {helpState.kind === "success" && (helpState.items.length ? <ul className="support-list">{helpState.items.slice(0, 3).map((resource) => <li key={resource.id}>
          <span className="support-list__verified"><Check size={13} aria-hidden="true" /> Verified</span><h3>{resource.name}</h3><p>{resource.description || resource.assistance_type}</p><p className="support-list__source">Source: {safeExternalUrl(resource.source_url) ? <a href={safeExternalUrl(resource.source_url)} rel="noreferrer noopener" target="_blank">{resource.source_title}</a> : resource.source_title} · {resource.jurisdiction.name} · Verified {new Date(resource.verified_at).toLocaleDateString()}</p>
          <div>{resource.phone && <a href={`tel:${resource.phone.replace(/[^\d+*#]/g, "")}`}>Call {resource.phone}</a>}{resource.contact_email && <a href={`mailto:${resource.contact_email}`}>Email</a>}{resource.contact_url && safeExternalUrl(resource.contact_url) && <a href={safeExternalUrl(resource.contact_url)} rel="noreferrer noopener" target="_blank">Visit website</a>}</div>
        </li>)}</ul> : <StatePanel kind="empty" title="No current contacts are listed">Verified support contacts will appear here when available. For immediate danger, contact your local emergency service.</StatePanel>)}
        <p className="workspace-support__footnote">Availability depends on the listed jurisdiction. Review source information before sharing personal details.</p>
      </section>
    </div>
    <div className="workspace-end page-container"><span><Check size={15} aria-hidden="true" /> A calm place to understand your options</span><Link to="/onboarding">Review how LexAware works<ArrowRight size={15} aria-hidden="true" /></Link></div>
  </div>;
}
