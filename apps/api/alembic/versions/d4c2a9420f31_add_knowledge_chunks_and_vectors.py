"""add governed knowledge chunk vectors

Revision ID: d4c2a9420f31
Revises: bc0d4f8a21e6
Create Date: 2026-09-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "d4c2a9420f31"
down_revision: str | Sequence[str] | None = "bc0d4f8a21e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_version_id", sa.Uuid(), nullable=False),
        sa.Column("section_key", sa.String(length=80), nullable=False),
        sa.Column("section_title", sa.String(length=200), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("chunking_version", sa.String(length=80), nullable=False),
        sa.Column("indexed_version_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("embedding_model", sa.String(length=160), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("ordinal >= 0", name="ck_knowledge_chunks_nonnegative_ordinal"),
        sa.CheckConstraint(
            "embedding_dimension = 384", name="ck_knowledge_chunks_embedding_dimension"
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_version_id"], ["knowledge_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "knowledge_version_id",
            "chunking_version",
            "section_key",
            "ordinal",
            name="uq_knowledge_chunks_version_section_ordinal",
        ),
    )
    op.create_index("ix_knowledge_chunks_version", "knowledge_chunks", ["knowledge_version_id"])
    op.create_index(
        "ix_knowledge_chunks_model", "knowledge_chunks", ["embedding_model", "embedding_dimension"]
    )
    # HNSW gives a useful approximate cosine index at this bounded scale. All returned
    # candidates are still joined to current governance rows and filtered before use.
    op.create_index(
        "ix_knowledge_chunks_embedding_hnsw",
        "knowledge_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_chunks_embedding_hnsw", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_model", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_version", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
