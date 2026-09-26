"""Make same-owner active document uploads idempotent under concurrency."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b71d2459c30a"
down_revision: str | Sequence[str] | None = "e82fb314a6c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_documents_owner_content_hash_active",
        "documents",
        ["owner_id", "content_hash"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND content_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_documents_owner_content_hash_active", table_name="documents")
