import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { ApiError } from "../../api/client";
import { knowledgeApi, type StudentArticleDetail } from "../../api/student-content";
import { StatePanel } from "../../shared/components/StatePanel";

function safeSource(value: string): string | null {
  try { const url = new URL(value); return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : null; }
  catch { return null; }
}

function dateLabel(value: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? null : new Intl.DateTimeFormat(undefined, { dateStyle: "long", timeZone: "UTC" }).format(date);
}

export function StudentArticlePage() {
  const { slug = "" } = useParams();
  const [article, setArticle] = useState<StudentArticleDetail | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "missing" | "error">("loading");
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState("loading"); setArticle(null);
    knowledgeApi.getArticle(slug, controller.signal).then((result) => { setArticle(result); setState("ready"); })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState(error instanceof ApiError && error.status === 404 ? "missing" : "error");
      });
    return () => controller.abort();
  }, [slug, retry]);

  if (state === "loading") return <div className="rights-detail page-container"><StatePanel kind="info" title="Loading guidance">Retrieving the currently available published article.</StatePanel></div>;
  if (state === "missing") return <div className="rights-detail page-container"><Link className="rights-back" to="/app/rights">&larr; All guidance</Link><StatePanel kind="empty" title="This guidance is not currently available">It may have changed or may no longer be published. Return to the current guidance library.</StatePanel></div>;
  if (state === "error" || !article) return <div className="rights-detail page-container"><Link className="rights-back" to="/app/rights">&larr; All guidance</Link><StatePanel kind="error" title="Guidance is temporarily unavailable">Please check your connection and try again.</StatePanel><button className="workspace-retry" type="button" onClick={() => setRetry((value) => value + 1)}>Try again</button></div>;

  const sourceLink = safeSource(article.source.source_url);
  const effectiveDate = dateLabel(article.effective_from);
  const reviewedDate = dateLabel(article.last_reviewed_at);
  const sourceRetrieved = dateLabel(article.source.retrieved_at);
  const sourceStart = dateLabel(article.source.effective_from);
  const sourceEnd = dateLabel(article.source.effective_until);

  return <article className="rights-detail page-container">
    <Link className="rights-back" to="/app/rights">&larr; All guidance</Link>
    <header className="rights-detail__header"><div className="rights-article__meta"><span>{article.category}</span>{article.topic && <span>{article.topic}</span>}<span>{article.jurisdiction.name}</span></div><h1>{article.title}</h1><p className="rights-detail__dek">Published student guidance | Version {article.version_number}</p>
      <div className="rights-detail__dates">{effectiveDate && <span>Effective {effectiveDate}</span>}{reviewedDate && <span>Last reviewed {reviewedDate}</span>}</div>
    </header>
    <div className="rights-detail__layout">
      <div className="rights-detail__body">
        {article.summary && <section aria-labelledby="rights-summary"><h2 id="rights-summary">What this guidance covers</h2><p>{article.summary}</p></section>}
        <section aria-labelledby="rights-content"><h2 id="rights-content">Guidance</h2><div className="rights-detail__content">{article.content}</div></section>
        {article.applicability_notes && <section aria-labelledby="rights-applicability"><h2 id="rights-applicability">Applicability</h2><p>{article.applicability_notes}</p></section>}
        {article.escalation_guidance && <section aria-labelledby="rights-next-steps"><h2 id="rights-next-steps">Practical next steps</h2><div className="rights-detail__content">{article.escalation_guidance}</div></section>}
      </div>
      <aside className="rights-detail__source" aria-labelledby="rights-source-title"><p className="eyebrow">Source and review</p><h2 id="rights-source-title">{article.source.title}</h2>{article.source.publisher && <p>{article.source.publisher}</p>}{article.source.citation && <p>{article.source.citation}</p>}
        <dl>{sourceRetrieved && <><dt>Source retrieved</dt><dd>{sourceRetrieved}</dd></>}{sourceStart && <><dt>Source effective from</dt><dd>{sourceStart}</dd></>}{sourceEnd && <><dt>Source effective until</dt><dd>{sourceEnd}</dd></>}</dl>
        {sourceLink && <a href={sourceLink} target="_blank" rel="noopener noreferrer">Open original source <span aria-hidden="true">&nearr;</span></a>}
      </aside>
    </div>
    <p className="rights-detail__boundary">This is educational legal-awareness information, not a determination of how the law applies to a particular situation. Review the cited source and seek qualified assistance where needed.</p>
  </article>;
}
