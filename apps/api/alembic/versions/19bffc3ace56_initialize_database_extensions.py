"""initialize database extensions

Revision ID: 19bffc3ace56
Revises:
Create Date: 2026-09-04 21:09:56.098796

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "19bffc3ace56"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Enable PostgreSQL extensions required by LexAware Student."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    """Remove PostgreSQL extensions created by this migration."""
    op.execute("DROP EXTENSION IF EXISTS vector")
