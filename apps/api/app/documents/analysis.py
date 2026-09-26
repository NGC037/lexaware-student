from __future__ import annotations

import asyncio
import io
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pypdf import PdfReader

from app.provenance.service import canonical_sha256


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    page_number: int
    text: str


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    pages: tuple[ExtractedPage, ...]
    quality: str
    needs_ocr: bool
    warnings: tuple[str, ...]

    @property
    def character_count(self) -> int:
        return sum(len(page.text) for page in self.pages)


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    document_type: str
    confidence: float | None
    supported: bool


_MAX_PAGES = 250
_MAX_EXTRACTED_CHARACTERS = 1_000_000


def extract_pdf(data: bytes) -> ExtractionResult:
    """Extract bounded per-page text. Extracted content is transient unless quoted as evidence."""
    reader = PdfReader(io.BytesIO(data), strict=True)
    if reader.is_encrypted:
        raise ValueError("password_protected")
    if len(reader.pages) > _MAX_PAGES:
        raise ValueError("page_limit_exceeded")
    pages: list[ExtractedPage] = []
    char_count = 0
    for number, page in enumerate(reader.pages, start=1):
        text = page.extract_text(extraction_mode="plain") or ""
        text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        char_count += len(text)
        if char_count > _MAX_EXTRACTED_CHARACTERS:
            raise ValueError("extraction_limit_exceeded")
        pages.append(ExtractedPage(page_number=number, text=text))
    short_pages = [page for page in pages if len(page.text.strip()) < 30]
    needs_ocr = bool(short_pages)
    if char_count == 0 or len(short_pages) == len(pages):
        quality = "low"
    elif short_pages:
        quality = "medium"
    elif char_count / max(len(pages), 1) < 250:
        quality = "medium"
    else:
        quality = "high"
    warnings: list[str] = []
    if short_pages:
        warnings.append("Some pages contain little or no selectable text and may require OCR.")
    if quality != "high":
        warnings.append("Text extraction may be incomplete; review the original document.")
    return ExtractionResult(tuple(pages), quality, needs_ocr, tuple(warnings))


async def extract_pdf_with_timeout(data: bytes, timeout_seconds: float) -> ExtractionResult:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "app.documents.extraction_worker",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(data), timeout_seconds)
    except TimeoutError as exc:
        await _terminate_extraction_process(process)
        raise ValueError("extraction_timeout") from exc
    except asyncio.CancelledError:
        await _terminate_extraction_process(process)
        raise
    if process.returncode != 0:
        raise ValueError("extraction_failed")
    try:
        result = json.loads(output)
        pages = tuple(
            ExtractedPage(page_number=page["page_number"], text=page["text"])
            for page in result["pages"]
        )
        return ExtractionResult(
            pages=pages,
            quality=result["quality"],
            needs_ocr=result["needs_ocr"],
            warnings=tuple(result["warnings"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("extraction_failed") from exc


async def _terminate_extraction_process(process: asyncio.subprocess.Process) -> None:
    try:
        process.kill()
    except ProcessLookupError:
        pass
    await process.wait()


_TYPE_TERMS: dict[str, tuple[str, ...]] = {
    "internship_agreement": ("internship", "intern", "stipend", "training period"),
    "employment_bond": ("employment bond", "service bond", "bond amount", "liquidated damages"),
    "offer_letter": ("offer of employment", "offer letter", "date of joining", "annual ctc"),
    "hostel_agreement": ("hostel rules", "hostel agreement", "resident student", "warden"),
    "rental_agreement": ("rental agreement", "tenancy", "landlord", "tenant", "security deposit"),
}


def classify_document(pages: tuple[ExtractedPage, ...]) -> ClassificationResult:
    text = "\n".join(page.text for page in pages).casefold()
    counts = {
        kind: sum(len(re.findall(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text)) for term in terms)
        for kind, terms in _TYPE_TERMS.items()
    }
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    best_type, best_count = ranked[0]
    second_count = ranked[1][1]
    if best_count == 0 or best_count < 2 or (second_count > 0 and best_count - second_count < 2):
        return ClassificationResult("unknown", None if best_count == 0 else 0.35, False)
    confidence = min(0.95, 0.55 + 0.08 * best_count + 0.08 * (best_count - second_count))
    return ClassificationResult(best_type, round(confidence, 2), True)


_FINDING_RULES: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "bond_or_penalty",
        r"\b(?:bond|liquidated damages|penalty|training cost recovery)\b",
        "Bond, penalty, or repayment term to review",
        (
            "This document appears to mention a bond, penalty, or repayment term. "
            "Its effect depends on the full agreement and applicable rules."
        ),
        (
            "Consider asking an appropriate student support service to explain "
            "this term before signing."
        ),
    ),
    (
        "payment_or_deduction",
        r"\b(?:withhold|deduct(?:ion)?|salary|stipend|compensation)\b",
        "Payment or deduction term to review",
        (
            "This passage refers to payment, compensation, or a deduction. Confirm "
            "the amount, timing, and conditions in the complete document."
        ),
        "Compare this term with the offer and ask for unclear amounts in writing.",
    ),
    (
        "termination_or_notice",
        r"\b(?:termination|terminate|notice period|end this agreement)\b",
        "Termination or notice term to review",
        (
            "This passage appears to describe how the arrangement may end. Check "
            "the notice period and any stated consequences."
        ),
        "Confirm that the process and notice period are clear to you.",
    ),
    (
        "liability_or_indemnity",
        r"\b(?:indemnif(?:y|ication)|liable|liability)\b",
        "Responsibility or liability term to review",
        (
            "This passage appears to allocate responsibility or liability. The "
            "scope may depend on other clauses and circumstances."
        ),
        "Ask for clarification about the situations and costs covered by this term.",
    ),
    (
        "confidentiality_or_restriction",
        r"\b(?:confidential|non[- ]disclosure|intellectual property|non[- ]compete)\b",
        "Confidentiality or restriction term to review",
        (
            "This passage refers to confidentiality, intellectual property, or a "
            "work restriction. Check its scope and duration."
        ),
        "Clarify what information or activity is covered and for how long.",
    ),
)


def _bounded_excerpt(text: str, start: int, end: int, maximum: int = 220) -> str:
    if len(text) <= maximum:
        return text
    left = max(0, start - (maximum - (end - start)) // 2)
    right = min(len(text), left + maximum)
    left = max(0, right - maximum)
    excerpt = text[left:right]
    return ("..." if left else "") + excerpt + ("..." if right < len(text) else "")


def build_findings(extraction: ExtractionResult) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for page in extraction.pages:
        for category, pattern, title, explanation, next_step in _FINDING_RULES:
            match = re.search(pattern, page.text, flags=re.IGNORECASE)
            if match is None:
                continue
            findings.append(
                {
                    "category": category,
                    "title": title,
                    "explanation": explanation,
                    "importance": "attention",
                    "evidence": {
                        "page_number": page.page_number,
                        "excerpt": _bounded_excerpt(page.text, match.start(), match.end()),
                        "document_version": 1,
                        "extraction_quality": extraction.quality,
                    },
                    "uncertainty": "This is a keyword-based review signal, not a legal conclusion.",
                    "limitation": (
                        "The clause was not assessed against the complete facts or "
                        "current jurisdiction-specific law."
                    ),
                    "recommended_next_step": next_step,
                }
            )
            if len(findings) >= 50:
                return findings
    return findings


def create_report_manifest(
    document_id: UUID,
    extraction: ExtractionResult,
    classification: ClassificationResult,
) -> tuple[dict[str, Any], str]:
    findings = (
        build_findings(extraction) if classification.supported and not extraction.needs_ocr else []
    )
    limitations = [
        (
            "This informational review is not a binding legal opinion or a "
            "determination that a clause is lawful or unlawful."
        ),
        "Automated keyword checks can miss relevant terms and may flag terms "
        "that are not concerns.",
        "Only selectable text was reviewed; missing or image-only page text "
        "may affect this report.",
    ]
    next_steps = [
        "Read the complete agreement and compare each finding with the surrounding clauses.",
        "Seek help from a trusted student support service or qualified "
        "professional if a term is unclear.",
    ]
    if not classification.supported:
        limitations.append(
            "The document type could not be identified confidently; "
            "clause review was not performed."
        )
        next_steps.insert(0, "Confirm the document type before relying on any automated review.")
    if extraction.needs_ocr:
        limitations.append(
            "OCR is not implemented; pages with little or no selectable text were not analyzed."
        )
        next_steps.insert(
            0,
            "Use a readable text PDF or request an accessible copy; this report "
            "does not include OCR.",
        )
    manifest: dict[str, Any] = {
        "manifest_schema_version": "document-report-v1",
        "document_id": str(document_id),
        "document_version": 1,
        "document_type": classification.document_type,
        "classification_confidence": classification.confidence,
        "extraction": {
            "quality": extraction.quality,
            "page_count": len(extraction.pages),
            "character_count": extraction.character_count,
            "needs_ocr": extraction.needs_ocr,
            "warnings": list(extraction.warnings),
        },
        "findings": findings,
        "limitations": limitations,
        "next_steps": next_steps,
        "review_recommendation": (
            "Review the complete document with an appropriate human support resource."
        ),
        "disclaimer": "Informational education support only; not a binding legal opinion.",
        "generated_at": datetime.now(UTC).isoformat(),
    }
    return manifest, hash_report_manifest(manifest)


def hash_report_manifest(manifest: dict[str, Any]) -> str:
    """Hash the canonical manifest using the shared provenance serializer."""
    return canonical_sha256(manifest)
