"""Add private document analysis jobs and report manifests."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e82fb314a6c1"
down_revision: str | Sequence[str] | None = "c195dd7e5955"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for value in ("validating", "validated", "extracted", "analyzing", "completed", "unsupported"):
        op.execute(sa.text(f"ALTER TYPE document_status ADD VALUE IF NOT EXISTS '{value}'"))

    op.add_column("documents", sa.Column("page_count", sa.Integer(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("extraction_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("documents", sa.Column("document_type", sa.String(length=48), nullable=True))
    op.add_column("documents", sa.Column("classification_confidence", sa.Float(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("needs_ocr", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "documents",
        sa.Column(
            "malware_scan_state",
            sa.String(length=24),
            server_default="not_configured",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_documents_classification_confidence",
        "documents",
        "classification_confidence IS NULL OR "
        "(classification_confidence >= 0 AND classification_confidence <= 1)",
    )

    op.create_table(
        "document_processing_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_document_jobs_nonnegative_attempts"),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed', 'blocked')",
            name="ck_document_jobs_status",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id"),
    )
    op.create_index(
        "ix_document_jobs_claim", "document_processing_jobs", ["status", "available_at"]
    )

    op.create_table(
        "document_analysis_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("report_version", sa.Integer(), nullable=False),
        sa.Column("manifest", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("report_version > 0", name="ck_document_report_positive_version"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "report_version", name="uq_document_report_version"),
    )
    op.create_index(
        "ix_document_reports_manifest_hash", "document_analysis_reports", ["manifest_sha256"]
    )


def downgrade() -> None:
    op.drop_index("ix_document_reports_manifest_hash", table_name="document_analysis_reports")
    op.drop_table("document_analysis_reports")
    op.drop_index("ix_document_jobs_claim", table_name="document_processing_jobs")
    op.drop_table("document_processing_jobs")
    op.drop_constraint("ck_documents_classification_confidence", "documents", type_="check")
    for column in (
        "malware_scan_state",
        "needs_ocr",
        "classification_confidence",
        "document_type",
        "extraction_metadata",
        "page_count",
    ):
        op.drop_column("documents", column)
    # PostgreSQL cannot remove enum labels safely; the added unused values remain.
