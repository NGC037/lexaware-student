"""Add the provenance anchor outbox and ledger status."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f9a17b2c6d40"
down_revision: str | Sequence[str] | None = "b71d2459c30a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "help_resources",
        sa.Column("version_number", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_check_constraint(
        "ck_help_resources_positive_version", "help_resources", "version_number > 0"
    )
    op.create_table(
        "provenance_anchors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("object_type", sa.String(length=32), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("network", sa.String(length=80), nullable=False),
        sa.Column("anchor_status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("action", sa.String(length=16), server_default="anchor", nullable=False),
        sa.Column("transaction_id", sa.String(length=128), nullable=True),
        sa.Column("anchored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by_version", sa.Integer(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_failure_code", sa.String(length=64), nullable=True),
        sa.Column("requested_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_provenance_anchor_positive_version"),
        sa.CheckConstraint("attempts >= 0", name="ck_provenance_anchor_nonnegative_attempts"),
        sa.CheckConstraint(
            "anchor_status IN ('pending', 'anchored', 'failed', 'revoked', 'superseded')",
            name="ck_provenance_anchor_status",
        ),
        sa.CheckConstraint("action IN ('anchor', 'revoke', 'supersede')", name="ck_provenance_anchor_action"),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_type", "object_id", "version", name="uq_provenance_anchor_object_version"),
    )
    op.create_index("ix_provenance_anchors_claim", "provenance_anchors", ["anchor_status", "next_attempt_at"])
    op.create_index("ix_provenance_anchors_owner_object", "provenance_anchors", ["object_type", "object_id"])


def downgrade() -> None:
    op.drop_index("ix_provenance_anchors_owner_object", table_name="provenance_anchors")
    op.drop_index("ix_provenance_anchors_claim", table_name="provenance_anchors")
    op.drop_table("provenance_anchors")
    op.drop_constraint("ck_help_resources_positive_version", "help_resources", type_="check")
    op.drop_column("help_resources", "version_number")
