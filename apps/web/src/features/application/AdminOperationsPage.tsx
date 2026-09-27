import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../../api/client";
import { operationsApi, type OperationsItem, type OperationsOverview } from "../../api/operations";
import { Button } from "../../shared/components/Button";

const categories: { key: keyof OperationsOverview; title: string; description: string }[] = [
  { key: "stale_content", title: "Stale content", description: "Published knowledge and complaint guidance past its review date." },
  { key: "failed_analyses", title: "Failed analyses", description: "Document analysis jobs that failed. File names and document content are not shown." },
  { key: "provider_errors", title: "Provider errors", description: "Recent assistant provider or retrieval failures." },
  { key: "user_reports", title: "User reports", description: "Assistant responses reported for review." },
  { key: "unresolved_feedback", title: "Unresolved feedback", description: "Assistant feedback that has not been marked reviewed." },
];

function Queue({ items, resolve }: { items: OperationsItem[]; resolve?: (id: string) => Promise<void> }) {
  if (!items.length) return <p className="admin-operations__empty">No items need attention.</p>;
  return <ul className="admin-operations__list">{items.map((item) => <li key={`${item.category}-${item.id}`}>
    <div><strong>{item.label || item.category.replaceAll("_", " ")}</strong><span>{item.status.replaceAll("_", " ")}</span><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time></div>
    {resolve && <Button variant="outline" onClick={() => void resolve(item.id)}>Mark reviewed</Button>}
  </li>)}</ul>;
}

export function AdminOperationsPage() {
  const [data, setData] = useState<OperationsOverview | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [actionError, setActionError] = useState(false);
  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true); setError(false);
    try { setData(await operationsApi.overview(signal)); }
    catch (cause) {
      if (signal?.aborted) return;
      setError(true);
      if (cause instanceof ApiError && cause.status === 401) setData(null);
    } finally { if (!signal?.aborted) setLoading(false); }
  }, []);
  useEffect(() => { const controller = new AbortController(); void load(controller.signal); return () => controller.abort(); }, [load, refresh]);
  async function resolve(id: string) {
    setActionError(false);
    try { await operationsApi.resolveFeedback(id); setRefresh((value) => value + 1); }
    catch { setActionError(true); }
  }

  return <div className="page-container admin-operations">
    <header className="admin-operations__header"><p className="eyebrow">Operations</p><h1>Admin overview</h1><p>Review content freshness, processing failures, provider issues, and student feedback.</p></header>
    {loading && <p role="status">Loading operations queues…</p>}
    {error && <section role="alert"><p>The operations overview could not be loaded. Your account may not have administrator access.</p><Button variant="outline" onClick={() => setRefresh((value) => value + 1)}>Try again</Button></section>}
    {actionError && <p role="alert">That feedback could not be marked reviewed. Refresh and try again.</p>}
    {!loading && !error && data && <div className="admin-operations__grid">{categories.map(({ key, title, description }) => <section className="admin-operations__card" key={key} aria-labelledby={`ops-${key}`}>
      <h2 id={`ops-${key}`}>{title} <span>{data[key].length}</span></h2><p>{description}</p><Queue items={data[key]} resolve={key === "unresolved_feedback" ? resolve : undefined} />
    </section>)}</div>}
  </div>;
}
