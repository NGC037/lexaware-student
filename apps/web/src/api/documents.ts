import { request, requestBlob } from "./client";

export type DocumentStatus =
  | "uploaded" | "validating" | "validated" | "processing" | "extracted" | "analyzing"
  | "completed" | "ready" | "failed" | "unsupported" | "deleted";
export type DocumentJobStatus = "queued" | "processing" | "completed" | "failed" | "blocked";
export type MalwareScanState = "not_configured" | "clean" | "infected" | "unavailable" | "error";
export type ExtractionQuality = "high" | "medium" | "low" | "unavailable";

export type DocumentSummary = {
  id: string;
  original_filename: string;
  media_type: string;
  size_bytes: number;
  status: DocumentStatus;
  malware_scan_state: MalwareScanState;
  page_count: number | null;
  document_type: string | null;
  classification_confidence: number | null;
  needs_ocr: boolean;
  job_status: DocumentJobStatus | null;
  attempts: number;
  created_at: string;
  updated_at: string;
};

export type UploadAccepted = {
  document: DocumentSummary;
  duplicate: boolean;
  detail: string;
};

export type DocumentEvidence = {
  page_number: number;
  excerpt: string;
  document_version: number;
  extraction_quality: ExtractionQuality;
};

export type DocumentFinding = {
  category: string;
  title: string;
  explanation: string;
  importance: "informational" | "attention" | "urgent_review";
  evidence: DocumentEvidence;
  uncertainty: string;
  limitation: string;
  recommended_next_step: string;
};

export type DocumentReport = {
  id: string;
  document_id: string;
  report_version: number;
  document_type: string;
  classification_confidence: number | null;
  extraction_quality: ExtractionQuality;
  page_count: number | null;
  needs_ocr: boolean;
  findings: DocumentFinding[];
  limitations: string[];
  next_steps: string[];
  review_recommendation: string;
  disclaimer: string;
  generated_at: string;
  manifest_sha256: string;
};

export const DOCUMENT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
export const DOCUMENT_POLL_INTERVAL_MS = 3_000;
export const DOCUMENT_MAX_POLL_ATTEMPTS = 20;

export const documentsApi = {
  list(signal?: AbortSignal) {
    return request<DocumentSummary[]>("/documents", { signal });
  },
  upload(file: File, signal?: AbortSignal) {
    const body = new FormData();
    body.append("file", file, file.name);
    return request<UploadAccepted>("/documents", { method: "POST", body, signal, timeoutMs: 60_000 });
  },
  get(documentId: string, signal?: AbortSignal) {
    return request<DocumentSummary>(`/documents/${encodeURIComponent(documentId)}`, { signal });
  },
  report(documentId: string, signal?: AbortSignal) {
    return request<DocumentReport>(`/documents/${encodeURIComponent(documentId)}/report`, { signal });
  },
  download(documentId: string, signal?: AbortSignal) {
    return requestBlob(`/documents/${encodeURIComponent(documentId)}/download`, { signal, timeoutMs: 60_000 });
  },
  retry(documentId: string, signal?: AbortSignal) {
    return request<DocumentSummary>(`/documents/${encodeURIComponent(documentId)}/retry`, { method: "POST", body: {}, signal });
  },
  delete(documentId: string, signal?: AbortSignal) {
    return request<void>(`/documents/${encodeURIComponent(documentId)}`, { method: "DELETE", signal });
  },
};

export function isDocumentProcessing(document: DocumentSummary): boolean {
  return document.job_status === "queued" || document.job_status === "processing";
}

export function canRetryDocument(document: DocumentSummary): boolean {
  return (document.job_status === "failed" || document.job_status === "blocked")
    && document.malware_scan_state !== "infected";
}
