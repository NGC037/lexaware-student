import type { DocumentFinding, DocumentReport, ExtractionQuality } from "../../api/documents";

const qualitySummary: Record<ExtractionQuality, string> = {
  high: "Text extraction quality: high", medium: "Text extraction quality: medium",
  low: "Text extraction quality: limited", unavailable: "Text extraction quality: unavailable",
};
const importanceText: Record<DocumentFinding["importance"], string> = {
  informational: "Informational", attention: "Potentially important", urgent_review: "May need timely review",
};

function FindingCard({ finding, index }: { finding: DocumentFinding; index: number }) {
  return <article className="document-finding">
    <header className="document-finding__header">
      <div><p className="eyebrow">Review signal {index + 1}</p><h3>{finding.title}</h3></div>
      <span className={`badge ${finding.importance === "urgent_review" ? "badge--warning" : "badge--neutral"}`}>{importanceText[finding.importance]}</span>
    </header>
    <p>{finding.explanation}</p>
    <section className="document-evidence" aria-label={`Evidence for ${finding.title}`}>
      <p className="document-evidence__label">Document evidence · page {finding.evidence.page_number}</p>
      <blockquote>{finding.evidence.excerpt}</blockquote>
      <p className="document-evidence__quality">{qualitySummary[finding.evidence.extraction_quality]} · Document version {finding.evidence.document_version}</p>
    </section>
    <section className="document-finding__caveat" aria-label="Finding uncertainty and limitation">
      <h4>Uncertainty</h4><p>{finding.uncertainty}</p>
      <h4>Limitation</h4><p>{finding.limitation}</p>
    </section>
    <section className="document-finding__next"><h4>Suggested next step</h4><p>{finding.recommended_next_step}</p></section>
  </article>;
}

export function DocumentReportView({ report }: { report: DocumentReport }) {
  return <article className="document-report" aria-labelledby="document-report-title">
    <header className="document-report__header">
      <p className="eyebrow">Informational document review · Version {report.report_version}</p>
      <h2 id="document-report-title">Review summary</h2>
      <p className="document-report__recommendation">{report.review_recommendation}</p>
      <p className="document-report__quality">{qualitySummary[report.extraction_quality]}{report.page_count !== null ? ` · ${report.page_count} ${report.page_count === 1 ? "page" : "pages"} reviewed` : ""}</p>
    </header>

    {report.needs_ocr && <aside className="document-uncertainty document-uncertainty--prominent" role="note">
      <h3>Text extraction is limited</h3>
      <p>This document may need OCR or manual review. Scanned pages or text that could not be selected may not be reflected below. OCR is not available in this review.</p>
    </aside>}

    {report.findings.length > 0
      ? <section className="document-report__findings" aria-labelledby="document-findings-title">
        <div className="document-section-heading"><div><p className="eyebrow">Evidence and review signals</p><h3 id="document-findings-title">Sections to consider</h3></div><p>These are not legal judgments.</p></div>
        <div className="document-finding-list">{report.findings.map((finding, index) => <FindingCard key={`${finding.category}-${index}`} finding={finding} index={index} />)}</div>
      </section>
      : <section className="document-report__findings"><h3>No specific review signals are listed</h3><p>The review did not identify a supported text pattern. This does not confirm that every term is suitable or complete.</p></section>}

    <section className="document-next-steps" aria-labelledby="document-next-steps-title">
      <p className="eyebrow">What you can do next</p><h3 id="document-next-steps-title">Consider these steps</h3>
      <ol>{report.next_steps.map((step, index) => <li key={`${index}-${step}`}>{step}</li>)}</ol>
    </section>

    {report.limitations.length > 0 && <section className="document-limitations" aria-labelledby="document-limitations-title">
      <h3 id="document-limitations-title">Limitations and uncertainty</h3>
      <ul>{report.limitations.map((limitation, index) => <li key={`${index}-${limitation}`}>{limitation}</li>)}</ul>
    </section>}

    <aside className="document-disclaimer" aria-label="Important review information"><h3>Review assistant, not a legal opinion</h3><p>{report.disclaimer}</p></aside>
    <p className="document-report__generated">Report generated {new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeZone: "UTC" }).format(new Date(report.generated_at))}</p>
  </article>;
}
