import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Jurisdiction & Source Schemas
# ---------------------------------------------------------------------------


class JurisdictionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    parent_id: uuid.UUID | None = None


class JurisdictionCreate(BaseModel):
    code: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=2, max_length=160)
    parent_id: uuid.UUID | None = None


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    jurisdiction_id: uuid.UUID
    title: str
    publisher: str | None = None
    source_url: str
    citation: str | None = None
    retrieved_at: datetime
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    is_active: bool


class SourceCreate(BaseModel):
    jurisdiction_id: uuid.UUID
    title: str = Field(min_length=3, max_length=300)
    publisher: str | None = Field(default=None, max_length=200)
    source_url: str = Field(min_length=5, max_length=2048)
    citation: str | None = Field(default=None, max_length=500)
    retrieved_at: datetime | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None


# ---------------------------------------------------------------------------
# Knowledge Version Schemas
# ---------------------------------------------------------------------------


class KnowledgeVersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    knowledge_item_id: uuid.UUID
    source_id: uuid.UUID
    version_number: int
    title: str
    summary: str | None = None
    publication_state: str
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    reviewed_at: datetime | None = None
    reviewed_by_id: uuid.UUID | None = None
    published_at: datetime | None = None
    published_by_id: uuid.UUID | None = None
    review_due_at: datetime | None = None
    change_summary: str | None = None
    created_at: datetime
    updated_at: datetime


class KnowledgeVersionDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    knowledge_item_id: uuid.UUID
    source_id: uuid.UUID
    version_number: int
    title: str
    summary: str | None = None
    content: str
    applicability_notes: str | None = None
    escalation_guidance: str | None = None
    publication_state: str
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    reviewed_at: datetime | None = None
    reviewed_by_id: uuid.UUID | None = None
    published_at: datetime | None = None
    published_by_id: uuid.UUID | None = None
    review_due_at: datetime | None = None
    change_summary: str | None = None
    source: SourceRead
    created_at: datetime
    updated_at: datetime


class KnowledgeVersionCreate(BaseModel):
    source_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=300)
    summary: str | None = None
    content: str = Field(min_length=10)
    applicability_notes: str | None = None
    escalation_guidance: str | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    review_due_at: datetime | None = None
    change_summary: str | None = Field(default=None, max_length=500)


class KnowledgeVersionUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    summary: str | None = None
    content: str | None = Field(default=None, min_length=10)
    applicability_notes: str | None = None
    escalation_guidance: str | None = None
    source_id: uuid.UUID | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    review_due_at: datetime | None = None
    change_summary: str | None = Field(default=None, max_length=500)


class ReviewDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    notes: str | None = Field(default=None, max_length=1000)


class ScheduleReviewRequest(BaseModel):
    review_due_at: datetime


# ---------------------------------------------------------------------------
# Knowledge Item Schemas
# ---------------------------------------------------------------------------


class KnowledgeItemCreate(BaseModel):
    jurisdiction_id: uuid.UUID
    category: str = Field(min_length=2, max_length=80)
    topic: str | None = Field(default=None, max_length=120)
    audience: str = Field(default="students", max_length=60)
    slug: str = Field(min_length=2, max_length=160)
    title: str = Field(min_length=3, max_length=300)
    source_id: uuid.UUID
    content: str = Field(min_length=10)
    summary: str | None = None
    applicability_notes: str | None = None
    escalation_guidance: str | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    review_due_at: datetime | None = None


class KnowledgeItemAdminDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    jurisdiction_id: uuid.UUID
    category: str
    topic: str | None = None
    audience: str
    slug: str
    title: str
    status: str
    jurisdiction: JurisdictionRead
    versions: list[KnowledgeVersionSummary]
    created_at: datetime
    updated_at: datetime


class KnowledgeItemAdminListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    jurisdiction_id: uuid.UUID
    category: str
    topic: str | None = None
    audience: str
    slug: str
    title: str
    status: str
    latest_version_number: int
    latest_publication_state: str
    review_due_at: datetime | None = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Student Read Schemas (Strict Safety Boundary)
# ---------------------------------------------------------------------------


class StudentArticleListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    title: str
    category: str
    topic: str | None = None
    audience: str
    summary: str | None = None
    jurisdiction: JurisdictionRead
    effective_from: datetime | None = None
    last_reviewed_at: datetime | None = None
    source_title: str | None = None


class StudentArticleDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    title: str
    category: str
    topic: str | None = None
    audience: str
    jurisdiction: JurisdictionRead
    version_number: int
    summary: str | None = None
    content: str
    applicability_notes: str | None = None
    escalation_guidance: str | None = None
    effective_from: datetime | None = None
    last_reviewed_at: datetime | None = None
    source: SourceRead


class CategorySummary(BaseModel):
    category: str
    article_count: int
