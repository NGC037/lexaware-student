import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { ApiError } from "../../api/client";
import {
  canRetryDocument,
  DOCUMENT_MAX_POLL_ATTEMPTS,
  DOCUMENT_POLL_INTERVAL_MS,
  documentsApi,
  isDocumentProcessing,
  type DocumentReport,
  type DocumentSummary,
} from "../../api/documents";
import { StatePanel } from "../../shared/components/StatePanel";
import { DocumentDeleteDialog } from "./DocumentDeleteDialog";
import { DocumentReportView } from "./DocumentReportView";
import { DocumentStatusBadge } from "./DocumentStatusBadge";

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "Date unavailable" : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeZone: "UTC" }).format(date);
}

function isReportAvailable(document: DocumentSummary): boolean {
  return ["completed", "ready", "unsupported"].includes(document.status);
}

function detailError(error: unknown): string {
  if (error instanceof ApiError && error.status === 401) return "Your session may have expired. Sign in again to continue.";
  if (error instanceof ApiError && error.status === 403) return "The secure session check could not be completed. Refresh and try again.";
  if (error instanceof ApiError && error.status >= 500) return "The document service is temporarily unavailable. Please try again.";
  return "Document information could not be loaded. Check your connection and try again.";
}

function actionError(error: unknown, action: "download" | "retry" | "delete"): string {
  if (error instanceof ApiError && error.status === 401) return "Your session may have expired. Sign in again to continue.";
  if (error instanceof ApiError && error.status === 404) return "This document is no longer available.";
  if (error instanceof ApiError && error.status === 409) return action === "retry" ? "This processing job cannot be retried right now." : "This action is not available for the document's current status.";
  if (error instanceof ApiError && error.status >= 500) return "The document service is temporarily unavailable. Please try again.";
  if (action === "download") return "The PDF could not be downloaded. Please try again.";
  if (action === "delete") return "The document could not be deleted. It remains in your vault.";
  return "Analysis could not be restarted. Please try again.";
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url; link.download = filename; link.rel = "noopener";
  document.body.append(link); link.click(); link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function DocumentDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [document, setDocument] = useState<DocumentSummary | null>(null);
  const [report, setReport] = useState<DocumentReport | null>(null);
  const [pageState, setPageState] = useState<"loading" | "ready" | "error" | "not-found">("loading");
  const [reportState, setReportState] = useState<"not-needed" | "loading" | "ready" | "pending" | "error">("not-needed");
  const [actionMessage, setActionMessage] = useState("");
  const [actionErrorMessage, setActionErrorMessage] = useState("");
  const [busyAction, setBusyAction] = useState("");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [pollRound, setPollRound] = useState(0);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (!id) { setPageState("not-found"); return; }
    const controller = new AbortController();
    let timer: number | undefined;
    if (pollRound === 0) { setPageState((current) => current === "ready" ? current : "loading"); setActionErrorMessage(""); }

    async function refresh() {
      try {
        const current = await documentsApi.get(id, controller.signal);
        if (controller.signal.aborted) return;
        setDocument(current); setPageState("ready");
        let reportPending = false;
        if (isReportAvailable(current)) {
          setReportState("loading");
          try {
            const currentReport = await documentsApi.report(id, controller.signal);
            if (!controller.signal.aborted) { setReport(currentReport); setReportState("ready"); }
          } catch (error) {
            if (controller.signal.aborted) return;
            if (error instanceof ApiError && error.status === 409) {
              setReport(null); setReportState("pending"); reportPending = true;
            } else if (error instanceof ApiError && error.status === 404) {
              setPageState("not-found"); setReportState("not-needed"); return;
            } else { setReport(null); setReportState("error"); }
          }
        } else { setReport(null); setReportState("not-needed"); }

        const keepPolling = isDocumentProcessing(current) || reportPending;
        if (keepPolling && pollRound < DOCUMENT_MAX_POLL_ATTEMPTS) {
          timer = window.setTimeout(() => setPollRound((round) => round + 1), DOCUMENT_POLL_INTERVAL_MS);
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          if (error instanceof ApiError && error.status === 404) setPageState("not-found");
          else { setPageState("error"); setActionErrorMessage(detailError(error)); }
        }
      }
    }
    void refresh();
    return () => { controller.abort(); if (timer !== undefined) window.clearTimeout(timer); };
  }, [id, pollRound, refreshKey]);

  async function download() {
    if (!document || busyAction) return;
    setBusyAction("download"); setActionErrorMessage(""); setActionMessage("");
    try { downloadBlob(await documentsApi.download(document.id), document.original_filename); }
    catch (error) { setActionErrorMessage(actionError(error, "download")); }
    finally { setBusyAction(""); }
  }

  async function retry() {
    if (!document || busyAction || !canRetryDocument(document)) return;
    setBusyAction("retry"); setActionErrorMessage(""); setActionMessage("");
    try {
      const updated = await documentsApi.retry(document.id);
      setDocument(updated); setReport(null); setReportState("not-needed"); setPollRound(0); setRefreshKey((value) => value + 1);
      setActionMessage("Processing was restarted. This page will check the status periodically.");
    } catch (error) { setActionErrorMessage(actionError(error, "retry")); }
    finally { setBusyAction(""); }
  }

  async function deleteDocument() {
    if (!document || busyAction) return;
    setBusyAction("delete"); setActionErrorMessage("");
    try { await documentsApi.delete(document.id); setDeleteOpen(false); navigate("/app/documents", { replace: true }); }
    catch (error) { setActionErrorMessage(actionError(error, "delete")); }
    finally { setBusyAction(""); }
  }

  const autoPolling = Boolean(document && (isDocumentProcessing(document) || reportState === "pending") && pollRound >= DOCUMENT_MAX_POLL_ATTEMPTS);

  return <div className="workspace-page documents-page documents-detail page-container">
    <Link className="documents-back" to="/app/documents">← My Documents</Link>
    {pageState === "loading" && <StatePanel kind="info" title="Loading document">Retrieving its current status from your account.</StatePanel>}
    {pageState === "error" && <><StatePanel kind="error" title="Document details are temporarily unavailable">No document contents are shown in this error state.</StatePanel><button className="button button--outline" type="button" onClick={() => { setPollRound(0); setRefreshKey((value) => value + 1); }}>Try again</button></>}
    {pageState === "not-found" && <StatePanel title="This document is not available">It may have been deleted or may belong to another account. Return to your private vault.</StatePanel>}

    {pageState === "ready" && document && <>
      <header className="document-detail-header">
        <p className="eyebrow">Private document</p><h1>{document.original_filename}</h1>
        <div className="document-detail-header__meta"><DocumentStatusBadge document={document}/><span>{document.document_type ? document.document_type.replaceAll("_", " ") : "Document type not identified"}</span><span>{document.page_count === null ? "Page count unavailable" : `${document.page_count} ${document.page_count === 1 ? "page" : "pages"}`}</span><span>Added {formatDate(document.created_at)}</span></div>
        <div className="document-detail-header__actions">
          {document.status !== "failed" && document.status !== "deleted" && document.malware_scan_state !== "infected" && <button className="button button--outline" type="button" disabled={Boolean(busyAction)} onClick={() => void download()}>{busyAction === "download" ? "Preparing download…" : "Download original PDF"}</button>}
          {canRetryDocument(document) && <button className="button button--outline" type="button" disabled={Boolean(busyAction)} onClick={() => void retry()}>{busyAction === "retry" ? "Restarting…" : "Retry analysis"}</button>}
          <button className="button button--quiet document-card__delete" type="button" disabled={Boolean(busyAction)} onClick={() => { setActionErrorMessage(""); setDeleteOpen(true); }}>Delete document</button>
          <button className="button button--quiet" type="button" disabled={Boolean(busyAction)} onClick={() => { setPollRound(0); setRefreshKey((value) => value + 1); }}>Refresh status</button>
        </div>
      </header>

      {actionMessage && <p className="document-action-message" role="status">{actionMessage}</p>}
      {actionErrorMessage && <p className="document-inline-error" role="alert">{actionErrorMessage}</p>}
      {autoPolling && <p className="document-poll-message" role="status">Automatic status checks have paused. Refresh this page to check again.</p>}

      {document.malware_scan_state === "infected" && <aside className="document-uncertainty document-uncertainty--prominent" role="alert"><h2>This file was blocked after a safety scan</h2><p>It was not analyzed. You can delete it from your vault. Do not retry this file.</p></aside>}
      {document.job_status === "blocked" && document.malware_scan_state !== "infected" && <aside className="document-uncertainty document-uncertainty--prominent" role="status"><h2>Safety scanning could not complete</h2><p>The file has not been analyzed. You can retry when the scanning service is available.</p></aside>}
      {document.needs_ocr && <aside className="document-uncertainty" role="note"><h2>Some text may not be machine-readable</h2><p>Scanned or image-only pages may not have been reviewed. OCR is not available. Consider a text-based copy or manual review.</p></aside>}
      {document.status === "unsupported" && !document.needs_ocr && <aside className="document-uncertainty" role="note"><h2>This document type was not supported for clause review</h2><p>The report may include extraction information, but no supported document review was performed.</p></aside>}
      {document.status === "failed" && document.malware_scan_state !== "infected" && <aside className="document-uncertainty" role="status"><h2>Document processing did not complete</h2><p>No complete review is available. Check the status again or retry if the action is available.</p></aside>}
      {isDocumentProcessing(document) && <StatePanel kind="info" title={document.job_status === "queued" ? "Waiting for document processing" : "Document processing in progress"}>Safety scanning and analysis run asynchronously. This page checks status at intervals; no progress percentage is estimated.</StatePanel>}

      {isReportAvailable(document) && reportState === "loading" && <StatePanel kind="info" title="Loading the review report">The report is retrieved from your account and is not stored in browser persistence.</StatePanel>}
      {isReportAvailable(document) && reportState === "pending" && <StatePanel kind="info" title="The report is not available yet">The document status has updated. Refresh shortly to check whether the report is ready.</StatePanel>}
      {isReportAvailable(document) && reportState === "error" && <><StatePanel kind="error" title="The report could not be loaded">The document remains in your vault. Try loading the report again.</StatePanel><button className="button button--outline" type="button" onClick={() => { setPollRound(0); setRefreshKey((value) => value + 1); }}>Retry report</button></>}
      {report && <DocumentReportView report={report}/>}
      {!isReportAvailable(document) && document.job_status !== "blocked" && document.status !== "failed" && <p className="document-report-note">A review report will appear here if the backend completes one.</p>}
    </>}
    {deleteOpen && document && <DocumentDeleteDialog filename={document.original_filename} busy={busyAction === "delete"} onCancel={() => { if (!busyAction) setDeleteOpen(false); }} onConfirm={() => void deleteDocument()} />}
  </div>;
}
