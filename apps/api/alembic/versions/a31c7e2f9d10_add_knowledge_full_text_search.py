"""add PostgreSQL full-text search to knowledge versions

Revision ID: a31c7e2f9d10
Revises: 45bd284b1395
Create Date: 2026-09-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a31c7e2f9d10"
down_revision: str | Sequence[str] | None = "45bd284b1395"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_SEARCH_VECTOR_SQL = """
to_tsvector(
    'english'::regconfig,
    concat_ws(
        ' ',
        coalesce(NEW.title, ''),
        coalesce(NEW.summary, ''),
        coalesce(NEW.content, ''),
        coalesce(NEW.tags::text, ''),
        coalesce(NEW.keywords::text, ''),
        coalesce(NEW.synonyms, '')
    )
)
"""


def upgrade() -> None:
    op.add_column(
        "knowledge_versions",
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "knowledge_versions",
        sa.Column(
            "keywords",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("knowledge_versions", sa.Column("synonyms", sa.Text(), nullable=True))
    op.add_column(
        "knowledge_versions", sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True)
    )
    op.execute(
        """
        UPDATE knowledge_versions
        SET search_vector = to_tsvector(
            'english'::regconfig,
            concat_ws(
                ' ', title, coalesce(summary, ''), content,
                tags::text, keywords::text, coalesce(synonyms, '')
            )
        )
        """
    )
    op.alter_column("knowledge_versions", "search_vector", nullable=False)
    op.create_index(
        "ix_knowledge_versions_search_vector",
        "knowledge_versions",
        ["search_vector"],
        postgresql_using="gin",
    )
    op.execute(
        f"""
        CREATE FUNCTION knowledge_versions_set_search_vector()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            NEW.search_vector := {_SEARCH_VECTOR_SQL};
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_knowledge_versions_search_vector
        BEFORE INSERT OR UPDATE OF title, summary, content, tags, keywords, synonyms
        ON knowledge_versions
        FOR EACH ROW EXECUTE FUNCTION knowledge_versions_set_search_vector()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_knowledge_versions_search_vector ON knowledge_versions")
    op.execute("DROP FUNCTION IF EXISTS knowledge_versions_set_search_vector()")
    op.drop_index("ix_knowledge_versions_search_vector", table_name="knowledge_versions")
    op.drop_column("knowledge_versions", "search_vector")
    op.drop_column("knowledge_versions", "synonyms")
    op.drop_column("knowledge_versions", "keywords")
    op.drop_column("knowledge_versions", "tags")
