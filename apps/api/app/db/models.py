from __future__ import annotations

import enum
import uuid
from datetime import datetime

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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


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
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
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


class KnowledgeItem(TimestampMixin, Base):
    __tablename__ = "knowledge_items"
    __table_args__ = (Index("ix_knowledge_items_jurisdiction_status", "jurisdiction_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    jurisdiction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jurisdictions.id", ondelete="RESTRICT"), nullable=False
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
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    knowledge_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    publication_state: Mapped[PublicationState] = mapped_column(
        Enum(PublicationState, name="publication_state", values_callable=enum_values),
        default=PublicationState.DRAFT,
        nullable=False,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    knowledge_item: Mapped[KnowledgeItem] = relationship(back_populates="versions")
    source: Mapped[Source] = relationship(back_populates="knowledge_versions")


class Document(TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="ck_documents_nonnegative_size"),
        Index("ix_documents_owner_status", "owner_id", "status"),
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

    owner: Mapped[User] = relationship(back_populates="documents")
    access_grants: Mapped[list[DocumentAccess]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


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
    __table_args__ = (Index("ix_help_resources_jurisdiction_status", "jurisdiction_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    jurisdiction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jurisdictions.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    contact_url: Mapped[str | None] = mapped_column(String(2048))
    phone: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[ResourceStatus] = mapped_column(
        Enum(ResourceStatus, name="resource_status", values_callable=enum_values),
        default=ResourceStatus.ACTIVE,
        nullable=False,
    )

    jurisdiction: Mapped[Jurisdiction] = relationship(back_populates="help_resources")


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
    The password_hash field stores the Argon2id digest — never plaintext.

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
