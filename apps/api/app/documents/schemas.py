from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    media_type: str
    size_bytes: int
    status: str
    malware_scan_state: str
    page_count: int | None
    document_type: str | None
    classification_confidence: float | None
    needs_ocr: bool
    job_status: str | None = None
    attempts: int = 0
    created_at: datetime
    updated_at: datetime


class Evidence(BaseModel):
    page_number: int = Field(ge=1)
    excerpt: str = Field(max_length=240)
    document_version: int = Field(ge=1)
    extraction_quality: Literal["high", "medium", "low", "unavailable"]


class Finding(BaseModel):
    category: str
    title: str
    explanation: str
    importance: Literal["informational", "attention", "urgent_review"]
    evidence: Evidence
    uncertainty: str
    limitation: str
    recommended_next_step: str


class AnalysisReport(BaseModel):
    id: UUID
    document_id: UUID
    report_version: int
    document_type: str
    classification_confidence: float | None
    extraction_quality: Literal["high", "medium", "low", "unavailable"]
    page_count: int | None
    needs_ocr: bool
    findings: list[Finding]
    limitations: list[str]
    next_steps: list[str]
    review_recommendation: str
    disclaimer: str
    generated_at: datetime
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class UploadAccepted(BaseModel):
    document: DocumentSummary
    duplicate: bool = False
    detail: str
