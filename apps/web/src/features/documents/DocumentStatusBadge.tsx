import type { DocumentSummary } from "../../api/documents";

const statusText: Record<DocumentSummary["status"], string> = {
  uploaded: "Uploaded", validating: "Checking PDF", validated: "Ready for safety scan", processing: "Processing",
  extracted: "Text extracted", analyzing: "Preparing review", completed: "Review ready", ready: "Review ready",
  failed: "Could not be reviewed", unsupported: "Manual review may be needed", deleted: "Deleted",
};

function documentStatusText(document: DocumentSummary): string {
  if (document.malware_scan_state === "infected") return "Blocked after safety scan";
  if (document.job_status === "blocked") return "Safety scan unavailable";
  return statusText[document.status];
}

export function DocumentStatusBadge({ document }: { document: DocumentSummary }) {
  const kind = document.malware_scan_state === "infected" || document.status === "failed"
    ? "danger"
    : document.job_status === "blocked" || document.status === "unsupported"
      ? "warning"
      : document.status === "completed" || document.status === "ready"
        ? "success"
        : isActive(document) ? "info" : "neutral";
  return <span className={`badge badge--${kind}`} aria-label={`Document status: ${documentStatusText(document)}`}>{documentStatusText(document)}</span>;
}

function isActive(document: DocumentSummary): boolean {
  return document.job_status === "queued" || document.job_status === "processing"
    || ["uploaded", "validating", "validated", "processing", "extracted", "analyzing"].includes(document.status);
}
