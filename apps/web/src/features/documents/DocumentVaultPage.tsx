import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { ApiError } from "../../api/client";
import {
  canRetryDocument,
  DOCUMENT_MAX_POLL_ATTEMPTS,
  DOCUMENT_MAX_UPLOAD_BYTES,
  DOCUMENT_POLL_INTERVAL_MS,
  documentsApi,
  isDocumentProcessing,
  type DocumentSummary,
} from "../../api/documents";
import { StatePanel } from "../../shared/components/StatePanel";
import { DocumentDeleteDialog } from "./DocumentDeleteDialog";
import { DocumentStatusBadge } from "./DocumentStatusBadge";

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "Date unavailable" : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeZone: "UTC" }).format(date);
}

function safeError(error: unknown, operation: "upload" | "refresh" | "download" | "retry" | "delete"): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your session may have expired. Sign in again to continue.";
    if (error.status === 403) return "The secure session check could not be completed. Refresh and try again.";
    if (error.status === 404) return "This document is no longer available in your vault.";
    if (error.status === 409) {
      if (operation === "download") return "This document is not currently available to download.";
      if (operation === "retry") return "This processing job cannot be retried right now.";
      return "This action is not available for the document's current status.";
    }
    if (operation === "upload" && (error.status === 413 || error.status === 422)) return "This PDF was not accepted. Check that it is a readable, unprotected PDF within the size and page limits.";
    if (error.status >= 500) return "The document service is temporarily unavailable. Please try again.";
  }
  if (operation === "upload") return "The PDF could not be uploaded. Check your connection and try again.";
  if (operation === "download") return "The document could not be downloaded. Please try again.";
  if (operation === "delete") return "The document could not be deleted. It remains in your vault.";
  if (operation === "retry") return "Analysis could not be restarted. Please try again.";
  return "Your documents could not be loaded. Check your connection and try again.";
}

function upsertDocument(current: DocumentSummary[], incoming: DocumentSummary): DocumentSummary[] {
  return [incoming, ...current.filter((document) => document.id !== incoming.id)];
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function DocumentVaultPage() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [pageState, setPageState] = useState<"loading" | "ready" | "error">("loading");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [validationError, setValidationError] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [busyAction, setBusyAction] = useState("");
  const [uploading, setUploading] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<DocumentSummary | null>(null);
  const [deleteError, setDeleteError] = useState("");
  const [pollAttempt, setPollAttempt] = useState(0);
  const [pollError, setPollError] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const fileInput = useRef<HTMLInputElement>(null);
  const deleteTrigger = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setPageState("loading");
    documentsApi.list(controller.signal)
      .then((result) => { if (!controller.signal.aborted) { setDocuments(result); setPageState("ready"); setPollError(false); } })
      .catch(() => { if (!controller.signal.aborted) setPageState("error"); });
    return () => controller.abort();
  }, [refreshKey]);

  useEffect(() => {
    if (pageState !== "ready" || !documents.some(isDocumentProcessing) || pollAttempt >= DOCUMENT_MAX_POLL_ATTEMPTS) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      documentsApi.list(controller.signal)
        .then((result) => {
          if (!controller.signal.aborted) {
            setDocuments(result); setPollError(false); setPollAttempt((attempt) => attempt + 1);
          }
        })
        .catch(() => { if (!controller.signal.aborted) setPollError(true); });
    }, DOCUMENT_POLL_INTERVAL_MS);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [documents, pageState, pollAttempt]);

  function chooseFile(file: File | null) {
    setSelectedFile(file); setValidationError(""); setUploadError(""); setActionMessage("");
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf") || (file.type && file.type.toLowerCase() !== "application/pdf")) {
      setValidationError("Choose a PDF file. Other file types are not supported."); return;
    }
    if (file.size === 0) { setValidationError("This file is empty. Choose a readable PDF."); return; }
    if (file.size > DOCUMENT_MAX_UPLOAD_BYTES) { setValidationError("This PDF is larger than the 10 MiB upload limit."); return; }
  }

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (uploading || !selectedFile) {
      if (!selectedFile) setValidationError("Choose a PDF file before uploading.");
      return;
    }
    if (validationError) return;
    setUploading(true); setUploadError(""); setActionMessage("");
    try {
      const result = await documentsApi.upload(selectedFile);
      setDocuments((current) => upsertDocument(current, result.document));
      setPageState("ready"); setSelectedFile(null); setPollAttempt(0);
      if (fileInput.current) fileInput.current.value = "";
      setActionMessage(result.duplicate ? "This PDF is already in your vault. Its existing processing job was retained." : "Upload accepted. Safety scanning and processing will continue.");
    } catch (error) { setUploadError(safeError(error, "upload")); }
    finally { setUploading(false); }
  }

  async function download(document: DocumentSummary) {
    if (busyAction) return;
    setBusyAction(`download:${document.id}`); setActionMessage(""); setUploadError("");
    try { downloadBlob(await documentsApi.download(document.id), document.original_filename); }
    catch (error) { setUploadError(safeError(error, "download")); }
    finally { setBusyAction(""); }
  }

  async function retry(document: DocumentSummary) {
    if (busyAction || !canRetryDocument(document)) return;
    setBusyAction(`retry:${document.id}`); setActionMessage(""); setUploadError("");
    try {
      const updated = await documentsApi.retry(document.id);
      setDocuments((current) => upsertDocument(current, updated)); setPollAttempt(0);
      setActionMessage(`Processing restarted for ${document.original_filename}.`);
    } catch (error) { setUploadError(safeError(error, "retry")); }
    finally { setBusyAction(""); }
  }

  async function deleteDocument() {
    if (!deleteTarget || busyAction) return;
    const target = deleteTarget;
    setBusyAction(`delete:${target.id}`); setDeleteError("");
    try {
      await documentsApi.delete(target.id);
      setDocuments((current) => current.filter((document) => document.id !== target.id));
      setDeleteTarget(null); setActionMessage("The document and its report were deleted from your account.");
      window.setTimeout(() => deleteTrigger.current?.focus(), 0);
    } catch (error) { setDeleteError(safeError(error, "delete")); }
    finally { setBusyAction(""); }
  }

  return <div className="workspace-page documents-page">
    <header className="documents-hero page-container">
      <div><p className="eyebrow">Your private document workspace</p><h1>My Documents</h1><p>Review PDFs from your account and see the processing status, evidence, and limitations returned by the analyzer.</p></div>
      <a className="button button--primary documents-hero__action" href="#document-upload">Upload document</a>
    </header>

    <div className="documents-privacy page-container" role="note"><strong>Your documents are private to your account.</strong><span>Analysis provides informational review signals, not a legal opinion or conclusion. Do not upload a document unless you are comfortable processing it here.</span></div>

    <section id="document-upload" className="document-upload page-container" aria-labelledby="document-upload-title">
      <div className="document-upload__heading"><div><p className="eyebrow">Private PDF upload</p><h2 id="document-upload-title">Add a document</h2></div><span className="badge badge--neutral">PDF only</span></div>
      <p id="document-upload-help">PDFs up to 10 MiB and 250 pages can be uploaded. Password-protected PDFs, photos, and other formats are not supported. Scanned PDFs may not be reviewable; OCR is not provided.</p>
      <form onSubmit={(event) => void upload(event)} aria-busy={uploading} noValidate>
        <label className="document-file-label" htmlFor="document-file">Choose a PDF from this device</label>
        <input ref={fileInput} id="document-file" name="file" type="file" accept=".pdf,application/pdf" aria-describedby={`document-upload-help${validationError ? " document-upload-error" : ""}`} aria-invalid={Boolean(validationError)} disabled={uploading} onChange={(event) => chooseFile(event.target.files?.[0] ?? null)} />
        {selectedFile && !validationError && <p className="document-file-selected">Selected: <strong>{selectedFile.name}</strong> · {(selectedFile.size / 1024 / 1024).toFixed(2)} MiB</p>}
        {validationError && <p id="document-upload-error" className="document-inline-error" role="alert">{validationError}</p>}
        {uploadError && <p className="document-inline-error" role="alert">{uploadError}</p>}
        <div className="document-upload__actions"><button className="button button--primary" type="submit" disabled={uploading || !selectedFile || Boolean(validationError)}>{uploading ? "Uploading PDF…" : "Upload document"}</button><p>Upload status is shown without estimated percentages.</p></div>
        {uploading && <p className="document-upload__progress" role="status">Uploading your PDF to the private document service…</p>}
      </form>
    </section>

    <section className="document-vault page-container" aria-labelledby="document-vault-title" aria-busy={pageState === "loading"}>
      <div className="document-section-heading"><div><p className="eyebrow">Account-owned files</p><h2 id="document-vault-title">Your vault</h2></div><button className="button button--outline" type="button" disabled={pageState === "loading"} onClick={() => { setPollAttempt(0); setPollError(false); setRefreshKey((value) => value + 1); }}>Refresh list</button></div>
      {pageState === "loading" && <StatePanel kind="info" title="Loading your vault">Retrieving documents linked to your account.</StatePanel>}
      {pageState === "error" && <div><StatePanel kind="error" title="Your vault is temporarily unavailable">Your files were not changed. Check your connection and try again.</StatePanel><button className="button button--outline" type="button" onClick={() => setRefreshKey((value) => value + 1)}>Try again</button></div>}
      {pageState === "ready" && documents.length === 0 && <StatePanel title="Your vault is empty">Upload a supported PDF to see its processing status and any available review report.</StatePanel>}
      {pollError && <p className="document-poll-message" role="status">Processing status could not be refreshed. <button type="button" onClick={() => { setPollError(false); setPollAttempt(0); setRefreshKey((value) => value + 1); }}>Refresh now</button></p>}
      {pageState === "ready" && documents.some(isDocumentProcessing) && pollAttempt >= DOCUMENT_MAX_POLL_ATTEMPTS && <p className="document-poll-message" role="status">Processing is still underway. Automatic refresh has paused; use Refresh list to check again.</p>}
      {actionMessage && <p className="document-action-message" role="status">{actionMessage}</p>}
      {pageState === "ready" && documents.length > 0 && <ul className="document-list">{documents.map((document) => {
        const downloadBusy = busyAction === `download:${document.id}`;
        const retryBusy = busyAction === `retry:${document.id}`;
        return <li key={document.id}><article className="document-card">
          <div className="document-card__main"><p className="eyebrow">{document.document_type ? document.document_type.replaceAll("_", " ") : "PDF document"}</p><h3><Link to={`/app/documents/${encodeURIComponent(document.id)}`}>{document.original_filename}</Link></h3><p>{document.page_count === null ? "Page count pending" : `${document.page_count} ${document.page_count === 1 ? "page" : "pages"}`} · Added {formatDate(document.created_at)}</p></div>
          <div className="document-card__status"><DocumentStatusBadge document={document}/><span>{document.job_status === "processing" ? "Safety check and review in progress" : document.job_status === "queued" ? "Waiting for processing" : document.malware_scan_state === "unavailable" ? "File was not analyzed" : `${(document.size_bytes / 1024 / 1024).toFixed(2)} MiB`}</span></div>
          <div className="document-card__actions"><Link className="button button--outline" to={`/app/documents/${encodeURIComponent(document.id)}`}>View status and report</Link>
            {document.status !== "failed" && document.status !== "deleted" && document.malware_scan_state !== "infected" && <button className="button button--quiet" type="button" disabled={Boolean(busyAction)} onClick={() => void download(document)}>{downloadBusy ? "Preparing…" : "Download PDF"}</button>}
            {canRetryDocument(document) && <button className="button button--quiet" type="button" disabled={Boolean(busyAction)} onClick={() => void retry(document)}>{retryBusy ? "Restarting…" : "Retry analysis"}</button>}
            <button className="button button--quiet document-card__delete" type="button" disabled={Boolean(busyAction)} onClick={(event) => { deleteTrigger.current = event.currentTarget; setDeleteError(""); setDeleteTarget(document); }}>Delete</button>
          </div>
        </article></li>;
      })}</ul>}
      {deleteError && <p className="document-inline-error" role="alert">{deleteError}</p>}
    </section>
    {deleteTarget && <DocumentDeleteDialog filename={deleteTarget.original_filename} busy={busyAction === `delete:${deleteTarget.id}`} onCancel={() => { if (!busyAction) { setDeleteTarget(null); window.setTimeout(() => deleteTrigger.current?.focus(), 0); } }} onConfirm={() => void deleteDocument()} />}
  </div>;
}
