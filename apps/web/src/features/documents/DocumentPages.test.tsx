import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import { documentsApi, type DocumentReport, type DocumentSummary } from "../../api/documents";
import { DocumentDetailPage } from "./DocumentDetailPage";
import { DocumentVaultPage } from "./DocumentVaultPage";

vi.mock("../../api/documents", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/documents")>();
  return { ...actual, documentsApi: {
    list: vi.fn(), upload: vi.fn(), get: vi.fn(), report: vi.fn(), download: vi.fn(), retry: vi.fn(), delete: vi.fn(),
  } };
});

const NativeURL = URL;
function makeDocument(overrides: Partial<DocumentSummary> = {}): DocumentSummary {
  return {
    id: "document-1", original_filename: "internship-agreement.pdf", media_type: "application/pdf", size_bytes: 4096,
    status: "validated", malware_scan_state: "clean", page_count: 2, document_type: "internship_agreement",
    classification_confidence: 0.8, needs_ocr: false, job_status: "queued", attempts: 0,
    created_at: "2026-09-10T00:00:00Z", updated_at: "2026-09-10T00:00:00Z", ...overrides,
  };
}
function makeReport(overrides: Partial<DocumentReport> = {}): DocumentReport {
  return {
    id: "report-1", document_id: "document-1", report_version: 1, document_type: "internship_agreement",
    classification_confidence: 0.8, extraction_quality: "high", page_count: 2, needs_ocr: false,
    findings: [{
      category: "bond_or_repayment", title: "Repayment term to review",
      explanation: "This passage describes a payment condition. Check the complete agreement.", importance: "attention",
      evidence: { page_number: 2, excerpt: "A service bond applies during the training period.", document_version: 1, extraction_quality: "high" },
      uncertainty: "This is a keyword-based review signal, not a legal conclusion.",
      limitation: "The full facts and applicable rules were not assessed.",
      recommended_next_step: "Ask for clarification about the term.",
    }],
    limitations: ["Automated keyword checks can miss terms or flag text that is not a concern."],
    next_steps: ["Read the complete agreement.", "Seek appropriate help if a term is unclear."],
    review_recommendation: "Review the marked passage in context.",
    disclaimer: "This informational review is not legal advice or a legal conclusion.",
    generated_at: "2026-09-10T00:00:00Z", manifest_sha256: "a".repeat(64), ...overrides,
  };
}
function renderVault() {
  return render(<MemoryRouter initialEntries={["/app/documents"]}><Routes><Route path="/app/documents" element={<DocumentVaultPage />} /></Routes></MemoryRouter>);
}
function renderDetail(id = "document-1") {
  return render(<MemoryRouter initialEntries={[`/app/documents/${id}`]}><Routes>
    <Route path="/app/documents/:id" element={<DocumentDetailPage />} />
    <Route path="/app/documents" element={<h1>My Documents</h1>} />
  </Routes></MemoryRouter>);
}

describe("private document vault and review pages", () => {
  beforeEach(() => {
    vi.mocked(documentsApi.list).mockResolvedValue([]);
    vi.mocked(documentsApi.get).mockResolvedValue(makeDocument());
    vi.mocked(documentsApi.report).mockResolvedValue(makeReport());
    vi.mocked(documentsApi.upload).mockResolvedValue({ document: makeDocument(), duplicate: false, detail: "Upload accepted." });
    vi.mocked(documentsApi.download).mockResolvedValue(new Blob(["%PDF-1.4"], { type: "application/pdf" }));
    vi.mocked(documentsApi.retry).mockResolvedValue(makeDocument({ status: "validated", job_status: "queued", malware_scan_state: "unavailable" }));
    vi.mocked(documentsApi.delete).mockResolvedValue(undefined);
    vi.stubGlobal("localStorage", { getItem: vi.fn(), setItem: vi.fn(), removeItem: vi.fn(), clear: vi.fn(), key: vi.fn(), length: 0 });
    vi.stubGlobal("sessionStorage", { getItem: vi.fn(), setItem: vi.fn(), removeItem: vi.fn(), clear: vi.fn(), key: vi.fn(), length: 0 });
    class TestURL extends NativeURL {}
    Object.assign(TestURL, { createObjectURL: vi.fn(() => "blob:private-document"), revokeObjectURL: vi.fn() });
    vi.stubGlobal("URL", TestURL);
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it("shows a truthful empty state for an empty vault", async () => {
    renderVault();
    expect(await screen.findByRole("heading", { name: "Your vault is empty" })).toBeInTheDocument();
    expect(screen.getByText(/private to your account/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Upload document" })).toHaveAttribute("href", "#document-upload");
  });

  it("renders owner document metadata and backend lifecycle status", async () => {
    vi.mocked(documentsApi.list).mockResolvedValue([makeDocument({ status: "processing", job_status: "processing" })]);
    renderVault();
    expect(await screen.findByRole("link", { name: "internship-agreement.pdf" })).toHaveAttribute("href", "/app/documents/document-1");
    expect(screen.getByLabelText("Document status: Processing")).toBeInTheDocument();
    expect(screen.getByText("Safety check and review in progress")).toBeInTheDocument();
  });

  it("validates file type, empty content, and configured default size before upload", async () => {
    renderVault();
    const input = await screen.findByLabelText("Choose a PDF from this device");
    fireEvent.change(input, { target: { files: [new File(["not pdf"], "notes.txt", { type: "text/plain" })] } });
    expect(screen.getByRole("alert")).toHaveTextContent("Choose a PDF file");
    expect(documentsApi.upload).not.toHaveBeenCalled();
    fireEvent.change(input, { target: { files: [new File([], "empty.pdf", { type: "application/pdf" })] } });
    expect(screen.getByRole("alert")).toHaveTextContent("file is empty");
    const tooLarge = new File(["x"], "large.pdf", { type: "application/pdf" });
    Object.defineProperty(tooLarge, "size", { value: 10 * 1024 * 1024 + 1 });
    fireEvent.change(input, { target: { files: [tooLarge] } });
    expect(screen.getByRole("alert")).toHaveTextContent("larger than the 10 MiB");
    expect(screen.getByRole("button", { name: "Upload document" })).toBeDisabled();
  });

  it("uploads PDF multipart data and immediately adds the accepted backend document", async () => {
    vi.mocked(documentsApi.list).mockResolvedValue([]);
    const user = userEvent.setup(); renderVault();
    const input = await screen.findByLabelText("Choose a PDF from this device");
    await user.upload(input, new File(["%PDF-1.4"], "student-agreement.pdf", { type: "application/pdf" }));
    await user.click(screen.getByRole("button", { name: "Upload document" }));
    expect(await screen.findByRole("link", { name: "internship-agreement.pdf" })).toBeInTheDocument();
    expect(documentsApi.upload).toHaveBeenCalledWith(expect.objectContaining({ name: "student-agreement.pdf" }));
    expect(screen.getByRole("status")).toHaveTextContent("Upload accepted");
    expect(localStorage.setItem).not.toHaveBeenCalled(); expect(sessionStorage.setItem).not.toHaveBeenCalled();
  });

  it("maps upload failure to a safe message without exposing backend internals", async () => {
    vi.mocked(documentsApi.upload).mockRejectedValueOnce(new ApiError(503, { message: "MinIO bucket path and secret diagnostic" }));
    const user = userEvent.setup(); renderVault();
    const input = await screen.findByLabelText("Choose a PDF from this device");
    await user.upload(input, new File(["%PDF"], "agreement.pdf", { type: "application/pdf" }));
    await user.click(screen.getByRole("button", { name: "Upload document" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("document service is temporarily unavailable");
    expect(screen.queryByText(/MinIO|secret diagnostic/)).not.toBeInTheDocument();
  });

  it("shows queued status without fabricating an upload percentage", async () => {
    let completeUpload: ((value: { document: DocumentSummary; duplicate: boolean; detail: string }) => void) | undefined;
    vi.mocked(documentsApi.upload).mockReturnValueOnce(new Promise((resolve) => { completeUpload = resolve; }));
    const user = userEvent.setup(); renderVault();
    const input = await screen.findByLabelText("Choose a PDF from this device");
    await user.upload(input, new File(["%PDF"], "agreement.pdf", { type: "application/pdf" }));
    await user.click(screen.getByRole("button", { name: "Upload document" }));
    expect(screen.getByText("Uploading your PDF to the private document service…")).toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
    completeUpload?.({ document: makeDocument(), duplicate: false, detail: "accepted" });
    await screen.findByRole("link", { name: "internship-agreement.pdf" });
  });

  it("renders report findings as evidence and review signals with uncertainty and next steps", async () => {
    vi.mocked(documentsApi.get).mockResolvedValue(makeDocument({ status: "completed", job_status: "completed" }));
    renderDetail();
    expect(await screen.findByRole("heading", { name: "Review summary" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Repayment term to review" })).toBeInTheDocument();
    expect(screen.getByText("Document evidence · page 2")).toBeInTheDocument();
    expect(screen.getByText(/service bond applies/)).toBeInTheDocument();
    expect(screen.getByText("This is a keyword-based review signal, not a legal conclusion.")).toBeInTheDocument();
    expect(screen.getByText("The full facts and applicable rules were not assessed.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Consider these steps" })).toBeInTheDocument();
    expect(screen.getByText(/not legal advice or a legal conclusion/)).toBeInTheDocument();
    expect(screen.queryByText(/classification confidence.*%/i)).not.toBeInTheDocument();
  });

  it("prominently explains OCR limitation and unsupported document report", async () => {
    vi.mocked(documentsApi.get).mockResolvedValue(makeDocument({ status: "unsupported", job_status: "completed", needs_ocr: true }));
    vi.mocked(documentsApi.report).mockResolvedValue(makeReport({ needs_ocr: true, extraction_quality: "low", findings: [] }));
    renderDetail();
    expect(await screen.findByRole("heading", { name: "Text extraction is limited" })).toBeInTheDocument();
    expect(screen.getByText(/OCR is not available in this review/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "No specific review signals are listed" })).toBeInTheDocument();
    expect(screen.getByText(/Automated keyword checks can miss/)).toBeInTheDocument();
  });

  it("renders scan-blocked status without offering retry for infected files", async () => {
    vi.mocked(documentsApi.get).mockResolvedValue(makeDocument({ status: "failed", job_status: "failed", malware_scan_state: "infected" }));
    renderDetail();
    expect(await screen.findByRole("heading", { name: "This file was blocked after a safety scan" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry analysis" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Download original PDF" })).not.toBeInTheDocument();
  });

  it("downloads through the authenticated API and does not persist report data", async () => {
    vi.mocked(documentsApi.get).mockResolvedValue(makeDocument({ status: "completed", job_status: "completed" }));
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const user = userEvent.setup(); renderDetail();
    await screen.findByRole("heading", { name: "Review summary" });
    await user.click(screen.getByRole("button", { name: "Download original PDF" }));
    expect(documentsApi.download).toHaveBeenCalledWith("document-1");
    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(localStorage.setItem).not.toHaveBeenCalled(); expect(sessionStorage.setItem).not.toHaveBeenCalled();
  });

  it("retries a backend-blocked scan once and refreshes lifecycle status", async () => {
    vi.mocked(documentsApi.get).mockResolvedValue(makeDocument({ status: "validated", job_status: "blocked", malware_scan_state: "unavailable" }));
    const user = userEvent.setup(); renderDetail();
    expect(await screen.findByRole("heading", { name: "Safety scanning could not complete" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry analysis" }));
    expect(documentsApi.retry).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(/Processing was restarted/)).toBeInTheDocument();
  });

  it("requires delete confirmation, removes the document on success, and returns to the vault", async () => {
    vi.mocked(documentsApi.get).mockResolvedValue(makeDocument({ status: "completed", job_status: "completed" }));
    const user = userEvent.setup(); renderDetail(); await screen.findByRole("heading", { name: "Review summary" });
    await user.click(screen.getByRole("button", { name: "Delete document" }));
    const dialog = screen.getByRole("dialog", { name: "Delete this document?" });
    expect(within(dialog).getByText(/and its report will be deleted/)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Keep document" })).toHaveFocus();
    await user.click(within(dialog).getByRole("button", { name: "Delete document" }));
    expect(documentsApi.delete).toHaveBeenCalledWith("document-1");
    expect(await screen.findByRole("heading", { name: "My Documents" })).toBeInTheDocument();
  });

  it("keeps the vault entry and reports a safe message when deletion fails", async () => {
    vi.mocked(documentsApi.list).mockResolvedValue([makeDocument({ status: "completed", job_status: "completed" })]);
    vi.mocked(documentsApi.delete).mockRejectedValueOnce(new ApiError(503, { message: "private object storage path unavailable" }));
    const user = userEvent.setup(); renderVault();
    await user.click(await screen.findByRole("button", { name: "Delete" }));
    const dialog = screen.getByRole("dialog", { name: "Delete this document?" });
    await user.click(within(dialog).getByRole("button", { name: "Delete document" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("document service is temporarily unavailable");
    expect(screen.getByRole("link", { name: "internship-agreement.pdf" })).toBeInTheDocument();
    expect(screen.queryByText(/storage path unavailable/)).not.toBeInTheDocument();
  });

  it("shows safe missing-document and backend-unavailable states", async () => {
    vi.mocked(documentsApi.get).mockRejectedValueOnce(new ApiError(404, { message: "Document not found." }));
    const missing = renderDetail("missing");
    expect(await screen.findByRole("heading", { name: "This document is not available" })).toBeInTheDocument();
    missing.unmount();
    vi.mocked(documentsApi.get).mockRejectedValueOnce(new ApiError(503, { message: "database password internals" }));
    renderDetail();
    expect(await screen.findByRole("heading", { name: "Document details are temporarily unavailable" })).toBeInTheDocument();
    expect(screen.queryByText(/database password/)).not.toBeInTheDocument();
  });

  it("offers retry on a failed report request without exposing raw errors", async () => {
    vi.mocked(documentsApi.get).mockResolvedValue(makeDocument({ status: "completed", job_status: "completed" }));
    vi.mocked(documentsApi.report).mockRejectedValueOnce(new ApiError(500, { message: "report manifest storage key" }));
    renderDetail();
    expect(await screen.findByRole("heading", { name: "The report could not be loaded" })).toBeInTheDocument();
    expect(screen.queryByText(/manifest storage/)).not.toBeInTheDocument();
  });

  it("explains safety scanner blocks and allows retry when the scanner was unavailable", async () => {
    vi.mocked(documentsApi.list).mockResolvedValue([makeDocument({ status: "validated", job_status: "blocked", malware_scan_state: "unavailable" })]);
    renderVault();
    expect(await screen.findByText("Safety scan unavailable")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry analysis" })).toBeEnabled();
  });

  it("keeps external storage paths out of the rendered UI", async () => {
    vi.mocked(documentsApi.list).mockResolvedValue([makeDocument({ original_filename: "safe-name.pdf" })]);
    renderVault();
    expect(await screen.findByRole("link", { name: "safe-name.pdf" })).toBeInTheDocument();
    expect(screen.queryByText(/storage_key|MinIO|s3:|bucket/i)).not.toBeInTheDocument();
  });

  it("announces list loading and leaves keyboard focus on the upload action", async () => {
    let finish: ((items: DocumentSummary[]) => void) | undefined;
    vi.mocked(documentsApi.list).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
    renderVault();
    expect(screen.getByRole("heading", { name: "Loading your vault" })).toBeInTheDocument();
    const uploadLink = screen.getByRole("link", { name: "Upload document" });
    uploadLink.focus(); expect(uploadLink).toHaveFocus();
    finish?.([]);
    expect(await screen.findByRole("heading", { name: "Your vault is empty" })).toBeInTheDocument();
  });
});
