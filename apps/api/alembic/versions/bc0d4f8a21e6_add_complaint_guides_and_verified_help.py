"""add governed complaint guides and verified help resources

Revision ID: bc0d4f8a21e6
Revises: a31c7e2f9d10
Create Date: 2026-09-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "bc0d4f8a21e6"
down_revision: str | Sequence[str] | None = "a31c7e2f9d10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "help_resources",
        sa.Column("category", sa.String(length=80), server_default="general", nullable=False),
    )
    op.add_column(
        "help_resources",
        sa.Column("resource_type", sa.String(length=60), server_default="support", nullable=False),
    )
    op.add_column(
        "help_resources",
        sa.Column(
            "assistance_type", sa.String(length=80), server_default="general", nullable=False
        ),
    )
    op.add_column(
        "help_resources",
        sa.Column(
            "contact_method", sa.String(length=30), server_default="in_person", nullable=False
        ),
    )
    op.add_column("help_resources", sa.Column("contact_email", sa.String(length=254)))
    op.add_column("help_resources", sa.Column("source_id", sa.Uuid()))
    op.add_column("help_resources", sa.Column("verified_at", sa.DateTime(timezone=True)))
    op.add_column("help_resources", sa.Column("verified_by_id", sa.Uuid()))
    op.add_column("help_resources", sa.Column("verification_due_at", sa.DateTime(timezone=True)))
    op.add_column("help_resources", sa.Column("expires_at", sa.DateTime(timezone=True)))
    op.execute(
        """
        UPDATE help_resources
        SET contact_method = CASE
            WHEN phone IS NOT NULL AND contact_url IS NOT NULL THEN 'multiple'
            WHEN phone IS NOT NULL THEN 'phone'
            WHEN contact_url IS NOT NULL THEN 'website'
            ELSE 'in_person'
        END
        """
    )
    op.create_foreign_key(
        "fk_help_resources_source_id_sources",
        "help_resources",
        "sources",
        ["source_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_help_resources_verified_by_id_users",
        "help_resources",
        "users",
        ["verified_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_help_resources_jurisdiction_category_assistance_status",
        "help_resources",
        ["jurisdiction_id", "category", "assistance_type", "status"],
    )
    op.create_index("ix_help_resources_source_id", "help_resources", ["source_id"])

    op.create_table(
        "complaint_guides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="knowledge_status", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_complaint_guides_status", "complaint_guides", ["status"])

    op.create_table(
        "complaint_guide_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("guide_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("jurisdiction_id", sa.Uuid(), nullable=False),
        sa.Column("audience", sa.String(length=60), server_default="students", nullable=False),
        sa.Column("short_description", sa.String(length=500), nullable=False),
        sa.Column(
            "guidance_steps",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "publication_state",
            postgresql.ENUM(name="publication_state", create_type=False),
            nullable=False,
        ),
        sa.Column("effective_from", sa.DateTime(timezone=True)),
        sa.Column("effective_until", sa.DateTime(timezone=True)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by_id", sa.Uuid()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("published_by_id", sa.Uuid()),
        sa.Column("review_due_at", sa.DateTime(timezone=True)),
        sa.Column("change_summary", sa.String(length=500)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "version_number > 0", name="ck_complaint_guide_versions_positive_number"
        ),
        sa.ForeignKeyConstraint(["guide_id"], ["complaint_guides.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["jurisdiction_id"], ["jurisdictions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["published_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "guide_id", "version_number", name="uq_complaint_guide_versions_guide_number"
        ),
    )
    op.create_index(
        "ix_complaint_guide_versions_guide_state",
        "complaint_guide_versions",
        ["guide_id", "publication_state"],
    )
    op.create_index(
        "ix_complaint_guide_versions_jurisdiction",
        "complaint_guide_versions",
        ["jurisdiction_id"],
    )
    op.create_index(
        "ix_complaint_guide_versions_effective_dates",
        "complaint_guide_versions",
        ["effective_from", "effective_until"],
    )
    op.create_index(
        "ix_complaint_guide_versions_review_due_at",
        "complaint_guide_versions",
        ["review_due_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_complaint_guide_versions_review_due_at", table_name="complaint_guide_versions"
    )
    op.drop_index(
        "ix_complaint_guide_versions_effective_dates", table_name="complaint_guide_versions"
    )
    op.drop_index("ix_complaint_guide_versions_jurisdiction", table_name="complaint_guide_versions")
    op.drop_index("ix_complaint_guide_versions_guide_state", table_name="complaint_guide_versions")
    op.drop_table("complaint_guide_versions")
    op.drop_index("ix_complaint_guides_status", table_name="complaint_guides")
    op.drop_table("complaint_guides")
    op.drop_index(
        "ix_help_resources_jurisdiction_category_assistance_status", table_name="help_resources"
    )
    op.drop_index("ix_help_resources_source_id", table_name="help_resources")
    op.drop_constraint(
        "fk_help_resources_verified_by_id_users", "help_resources", type_="foreignkey"
    )
    op.drop_constraint("fk_help_resources_source_id_sources", "help_resources", type_="foreignkey")
    op.drop_column("help_resources", "expires_at")
    op.drop_column("help_resources", "verification_due_at")
    op.drop_column("help_resources", "verified_by_id")
    op.drop_column("help_resources", "verified_at")
    op.drop_column("help_resources", "source_id")
    op.drop_column("help_resources", "contact_email")
    op.drop_column("help_resources", "contact_method")
    op.drop_column("help_resources", "assistance_type")
    op.drop_column("help_resources", "resource_type")
    op.drop_column("help_resources", "category")
