"""Change governed knowledge vectors to Gemini Embedding 001's 768 dimensions.

Existing vectors are derived index artifacts and cannot be compared across model and
dimension changes. This migration drops them so eligible published content can be
reindexed with the configured provider. Live governance joins protect student reads.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "c195dd7e5955"
down_revision: str | Sequence[str] | None = "d4c2a9420f31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_knowledge_chunks_embedding_hnsw", table_name="knowledge_chunks")
    op.execute(sa.text("DELETE FROM knowledge_chunks"))
    op.drop_constraint("ck_knowledge_chunks_embedding_dimension", "knowledge_chunks", type_="check")
    op.alter_column(
        "knowledge_chunks",
        "embedding",
        existing_type=Vector(384),
        type_=Vector(768),
        existing_nullable=False,
        postgresql_using="embedding::vector(768)",
    )
    op.create_check_constraint(
        "ck_knowledge_chunks_embedding_dimension",
        "knowledge_chunks",
        "embedding_dimension = 768",
    )
    op.create_index(
        "ix_knowledge_chunks_embedding_hnsw",
        "knowledge_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_chunks_embedding_hnsw", table_name="knowledge_chunks")
    op.execute(sa.text("DELETE FROM knowledge_chunks"))
    op.drop_constraint("ck_knowledge_chunks_embedding_dimension", "knowledge_chunks", type_="check")
    op.alter_column(
        "knowledge_chunks",
        "embedding",
        existing_type=Vector(768),
        type_=Vector(384),
        existing_nullable=False,
        postgresql_using="embedding::vector(384)",
    )
    op.create_check_constraint(
        "ck_knowledge_chunks_embedding_dimension",
        "knowledge_chunks",
        "embedding_dimension = 384",
    )
    op.create_index(
        "ix_knowledge_chunks_embedding_hnsw",
        "knowledge_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
