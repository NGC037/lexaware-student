from __future__ import annotations

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.knowledge.rag.config import RetrievalConfig


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class UserStatus(enum.StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class KnowledgeStatus(enum.StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class PublicationState(enum.StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class DocumentStatus(enum.StrEnum):
    UPLOADED = "uploaded"
    VALIDATING = "validating"
    VALIDATED = "validated"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    READY = "ready"  # Legacy state retained for existing records.
    FAILED = "failed"
    UNSUPPORTED = "unsupported"
    DELETED = "deleted"


class DocumentPermission(enum.StrEnum):
    VIEW = "view"
    EDIT = "edit"


class ComplaintStatus(enum.StrEnum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    CLOSED = "closed"


class ResourceStatus(enum.StrEnum):
    ACTIVE = "active"
    RETIRED = "retired"


def enum_values(enum_type: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_type]


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # external_subject is reserved for OAuth/SSO integration.
    # For local password authentication it is NULL; see ADR 0004.
    external_subject: Mapped[str | None] = mapped_column(String(255), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status", values_callable=enum_values),
        default=UserStatus.ACTIVE,
        nullable=False,
    )

    credential: Mapped[UserCredential | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    roles: Mapped[list[UserRole]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    documents: Mapped[list[Document]] = relationship(back_populates="owner")
    document_access: Mapped[list[DocumentAccess]] = relationship(
        back_populates="user", foreign_keys="DocumentAccess.user_id"
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(back_populates="actor")
    complaints: Mapped[list[Complaint]] = relationship(back_populates="reporter")


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))

    users: Mapped[list[UserRole]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (Index("ix_user_roles_role_id", "role_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="roles")
    role: Mapped[Role] = relationship(back_populates="users")


class Jurisdiction(TimestampMixin, Base):
    __tablename__ = "jurisdictions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jurisdictions.id"))

    parent: Mapped[Jurisdiction | None] = relationship(remote_side="Jurisdiction.id")
    knowledge_items: Mapped[list[KnowledgeItem]] = relationship(back_populates="jurisdiction")
    sources: Mapped[list[Source]] = relationship(back_populates="jurisdiction")
    help_resources: Mapped[list[HelpResource]] = relationship(back_populates="jurisdiction")
    complaint_guide_versions: Mapped[list[ComplaintGuideVersion]] = relationship(
        back_populates="jurisdiction"
    )
    complaints: Mapped[list[Complaint]] = relationship(back_populates="jurisdiction")


class Source(TimestampMixin, Base):
    __tablename__ = "sources"
    __table_args__ = (Index("ix_sources_jurisdiction_id", "jurisdiction_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    jurisdiction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jurisdictions.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    publisher: Mapped[str | None] = mapped_column(String(200))
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    citation: Mapped[str | None] = mapped_column(String(500))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str | None] = mapped_column(String(128), unique=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    jurisdiction: Mapped[Jurisdiction] = relationship(back_populates="sources")
    knowledge_versions: Mapped[list[KnowledgeVersion]] = relationship(back_populates="source")
    help_resources: Mapped[list[HelpResource]] = relationship(back_populates="source")


class KnowledgeItem(TimestampMixin, Base):
    __tablename__ = "knowledge_items"
    __table_args__ = (
        Index("ix_knowledge_items_jurisdiction_status", "jurisdiction_id", "status"),
        Index("ix_knowledge_items_category", "category"),
        Index(
            "ix_knowledge_items_jurisdiction_category_status",
            "jurisdiction_id",
            "category",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    jurisdiction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jurisdictions.id", ondelete="RESTRICT"), nullable=False
    )
    category: Mapped[str] = mapped_column(
        String(80), nullable=False, default="general", server_default="general"
    )
    topic: Mapped[str | None] = mapped_column(String(120))
    audience: Mapped[str] = mapped_column(
        String(60), nullable=False, default="students", server_default="students"
    )
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[KnowledgeStatus] = mapped_column(
        Enum(KnowledgeStatus, name="knowledge_status", values_callable=enum_values),
        default=KnowledgeStatus.ACTIVE,
        nullable=False,
    )

    jurisdiction: Mapped[Jurisdiction] = relationship(back_populates="knowledge_items")
    versions: Mapped[list[KnowledgeVersion]] = relationship(
        back_populates="knowledge_item", cascade="all, delete-orphan"
    )


class KnowledgeVersion(TimestampMixin, Base):
    __tablename__ = "knowledge_versions"
    __table_args__ = (
        UniqueConstraint(
            "knowledge_item_id", "version_number", name="uq_knowledge_versions_item_number"
        ),
        CheckConstraint("version_number > 0", name="ck_knowledge_versions_positive_number"),
        Index("ix_knowledge_versions_publication_state", "publication_state"),
        Index("ix_knowledge_versions_item_state", "knowledge_item_id", "publication_state"),
        Index("ix_knowledge_versions_effective_dates", "effective_from", "effective_until"),
        Index("ix_knowledge_versions_review_due_at", "review_due_at"),
        Index("ix_knowledge_versions_search_vector", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    knowledge_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False, default="", server_default="")
    summary: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    keywords: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    synonyms: Mapped[str | None] = mapped_column(Text)
    search_vector: Mapped[str] = mapped_column(TSVECTOR, nullable=False)
    applicability_notes: Mapped[str | None] = mapped_column(Text)
    escalation_guidance: Mapped[str | None] = mapped_column(Text)
    publication_state: Mapped[PublicationState] = mapped_column(
        Enum(PublicationState, name="publication_state", values_callable=enum_values),
        default=PublicationState.DRAFT,
        nullable=False,
    )
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    review_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    change_summary: Mapped[str | None] = mapped_column(String(500))

    knowledge_item: Mapped[KnowledgeItem] = relationship(back_populates="versions")
    source: Mapped[Source] = relationship(back_populates="knowledge_versions")
    reviewed_by: Mapped[User | None] = relationship(foreign_keys=[reviewed_by_id])
    published_by: Mapped[User | None] = relationship(foreign_keys=[published_by_id])


class KnowledgeChunk(TimestampMixin, Base):
    """Internal indexed passage; visibility is always resolved through live parent rows."""

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        CheckConstraint("ordinal >= 0", name="ck_knowledge_chunks_nonnegative_ordinal"),
        CheckConstraint(
            "embedding_dimension = 768", name="ck_knowledge_chunks_embedding_dimension"
        ),
        UniqueConstraint(
            "knowledge_version_id",
            "chunking_version",
            "section_key",
            "ordinal",
            name="uq_knowledge_chunks_version_section_ordinal",
        ),
        Index("ix_knowledge_chunks_version", "knowledge_version_id"),
        Index("ix_knowledge_chunks_model", "embedding_model", "embedding_dimension"),
        Index(
            "ix_knowledge_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    knowledge_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_versions.id", ondelete="CASCADE"), nullable=False
    )
    section_key: Mapped[str] = mapped_column(String(80), nullable=False)
    section_title: Mapped[str] = mapped_column(String(200), nullable=False)
    ordinal: Mapped[int] = mapped_column(nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    chunking_version: Mapped[str] = mapped_column(String(80), nullable=False)
    indexed_version_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    embedding_model: Mapped[str] = mapped_column(String(160), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(nullable=False)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(RetrievalConfig().embedding_dimension), nullable=False
    )
    knowledge_version: Mapped[KnowledgeVersion] = relationship()


class Document(TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="ck_documents_nonnegative_size"),
        CheckConstraint(
            "classification_confidence IS NULL OR "
            "(classification_confidence >= 0 AND classification_confidence <= 1)",
            name="ck_documents_classification_confidence",
        ),
        Index("ix_documents_owner_status", "owner_id", "status"),
        Index(
            "uq_documents_owner_content_hash_active",
            "owner_id",
            "content_hash",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND content_hash IS NOT NULL"),
        ),
        UniqueConstraint("storage_key", name="uq_documents_storage_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(127), nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", values_callable=enum_values),
        default=DocumentStatus.UPLOADED,
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    page_count: Mapped[int | None] = mapped_column()
    extraction_metadata: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    document_type: Mapped[str | None] = mapped_column(String(48))
    classification_confidence: Mapped[float | None] = mapped_column()
    needs_ocr: Mapped[bool] = mapped_column(default=False, nullable=False, server_default="false")
    malware_scan_state: Mapped[str] = mapped_column(
        String(24), nullable=False, default="not_configured", server_default="not_configured"
    )

    owner: Mapped[User] = relationship(back_populates="documents")
    access_grants: Mapped[list[DocumentAccess]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    processing_job: Mapped[DocumentProcessingJob | None] = relationship(
        back_populates="document", cascade="all, delete-orphan", uselist=False
    )
    analysis_report: Mapped[DocumentAnalysisReport | None] = relationship(
        back_populates="document", cascade="all, delete-orphan", uselist=False
    )


class DocumentProcessingJob(TimestampMixin, Base):
    __tablename__ = "document_processing_jobs"
    __table_args__ = (
        CheckConstraint("attempts >= 0", name="ck_document_jobs_nonnegative_attempts"),
        CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed', 'blocked')",
            name="ck_document_jobs_status",
        ),
        Index("ix_document_jobs_claim", "status", "available_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    attempts: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(80))

    document: Mapped[Document] = relationship(back_populates="processing_job")


class DocumentAnalysisReport(TimestampMixin, Base):
    __tablename__ = "document_analysis_reports"
    __table_args__ = (
        UniqueConstraint("document_id", "report_version", name="uq_document_report_version"),
        CheckConstraint("report_version > 0", name="ck_document_report_positive_version"),
        Index("ix_document_reports_manifest_hash", "manifest_sha256"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    report_version: Mapped[int] = mapped_column(default=1, nullable=False)
    manifest: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    document: Mapped[Document] = relationship(back_populates="analysis_report")


class DocumentAccess(TimestampMixin, Base):
    __tablename__ = "document_access"
    __table_args__ = (
        UniqueConstraint("document_id", "user_id", name="uq_document_access_document_user"),
        Index("ix_document_access_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    permission: Mapped[DocumentPermission] = mapped_column(
        Enum(DocumentPermission, name="document_permission", values_callable=enum_values),
        nullable=False,
    )
    granted_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="access_grants")
    user: Mapped[User] = relationship(back_populates="document_access", foreign_keys=[user_id])
    granted_by: Mapped[User] = relationship(foreign_keys=[granted_by_id])


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_actor_occurred_at", "actor_id", "occurred_at"),
        Index("ix_audit_events_resource", "resource_type", "resource_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    request_id: Mapped[str | None] = mapped_column(String(128))
    details: Mapped[dict[str, object] | None] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    actor: Mapped[User | None] = relationship(back_populates="audit_events")


class HelpResource(TimestampMixin, Base):
    __tablename__ = "help_resources"
    __table_args__ = (
        Index("ix_help_resources_jurisdiction_status", "jurisdiction_id", "status"),
        Index(
            "ix_help_resources_jurisdiction_category_assistance_status",
            "jurisdiction_id",
            "category",
            "assistance_type",
            "status",
        ),
        Index("ix_help_resources_source_id", "source_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    jurisdiction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jurisdictions.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(
        String(80), nullable=False, default="general", server_default="general"
    )
    resource_type: Mapped[str] = mapped_column(
        String(60), nullable=False, default="support", server_default="support"
    )
    assistance_type: Mapped[str] = mapped_column(
        String(80), nullable=False, default="general", server_default="general"
    )
    contact_method: Mapped[str] = mapped_column(
        String(30), nullable=False, default="in_person", server_default="in_person"
    )
    description: Mapped[str | None] = mapped_column(Text)
    contact_url: Mapped[str | None] = mapped_column(String(2048))
    phone: Mapped[str | None] = mapped_column(String(40))
    contact_email: Mapped[str | None] = mapped_column(String(254))
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sources.id", ondelete="RESTRICT")
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    verification_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[ResourceStatus] = mapped_column(
        Enum(ResourceStatus, name="resource_status", values_callable=enum_values),
        default=ResourceStatus.ACTIVE,
        nullable=False,
    )

    jurisdiction: Mapped[Jurisdiction] = relationship(back_populates="help_resources")
    source: Mapped[Source | None] = relationship(back_populates="help_resources")


class ComplaintGuide(TimestampMixin, Base):
    __tablename__ = "complaint_guides"
    __table_args__ = (Index("ix_complaint_guides_status", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    status: Mapped[KnowledgeStatus] = mapped_column(
        Enum(KnowledgeStatus, name="knowledge_status", values_callable=enum_values),
        default=KnowledgeStatus.ACTIVE,
        nullable=False,
    )

    versions: Mapped[list[ComplaintGuideVersion]] = relationship(
        back_populates="guide",
        cascade="all, delete-orphan",
        order_by="ComplaintGuideVersion.version_number",
    )


class ComplaintGuideVersion(TimestampMixin, Base):
    __tablename__ = "complaint_guide_versions"
    __table_args__ = (
        UniqueConstraint(
            "guide_id", "version_number", name="uq_complaint_guide_versions_guide_number"
        ),
        CheckConstraint("version_number > 0", name="ck_complaint_guide_versions_positive_number"),
        Index("ix_complaint_guide_versions_guide_state", "guide_id", "publication_state"),
        Index("ix_complaint_guide_versions_jurisdiction", "jurisdiction_id"),
        Index("ix_complaint_guide_versions_effective_dates", "effective_from", "effective_until"),
        Index("ix_complaint_guide_versions_review_due_at", "review_due_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    guide_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complaint_guides.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    jurisdiction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jurisdictions.id", ondelete="RESTRICT"), nullable=False
    )
    audience: Mapped[str] = mapped_column(
        String(60), nullable=False, default="students", server_default="students"
    )
    short_description: Mapped[str] = mapped_column(String(500), nullable=False)
    guidance_steps: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    publication_state: Mapped[PublicationState] = mapped_column(
        Enum(PublicationState, name="publication_state", values_callable=enum_values),
        default=PublicationState.DRAFT,
        nullable=False,
    )
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    review_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    change_summary: Mapped[str | None] = mapped_column(String(500))

    guide: Mapped[ComplaintGuide] = relationship(back_populates="versions")
    jurisdiction: Mapped[Jurisdiction] = relationship(back_populates="complaint_guide_versions")


class Complaint(TimestampMixin, Base):
    __tablename__ = "complaints"
    __table_args__ = (Index("ix_complaints_reporter_status", "reporter_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    jurisdiction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jurisdictions.id", ondelete="RESTRICT"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ComplaintStatus] = mapped_column(
        Enum(ComplaintStatus, name="complaint_status", values_callable=enum_values),
        default=ComplaintStatus.OPEN,
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    reporter: Mapped[User] = relationship(back_populates="complaints")
    jurisdiction: Mapped[Jurisdiction] = relationship(back_populates="complaints")


class UserCredential(TimestampMixin, Base):
    """Stores local-authentication credentials for a user.

    This table is intentionally separate from User so the identity record
    remains clean for future OAuth/SSO integration.  The email field stores
    the normalised (lower-cased) address and acts as the login identifier.
    The password_hash field stores the Argon2id digest â€” never plaintext.

    Constraint: 1-to-1 with User; deleting a User cascades to this record.
    """

    __tablename__ = "user_credentials"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    email_verified: Mapped[bool] = mapped_column(default=False, nullable=False)

    user: Mapped[User] = relationship(back_populates="credential")
