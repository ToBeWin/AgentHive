"""knowledge chunk embeddings

Revision ID: 0008_knowledge_chunk_embeddings
Revises: 0007_llm_usage_cost_centers
Create Date: 2026-06-12
"""

from alembic import op

revision = "0008_knowledge_chunk_embeddings"
down_revision = "0007_llm_usage_cost_centers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        ALTER TABLE knowledge_chunks
        ADD COLUMN IF NOT EXISTS embedding_model_key VARCHAR(120),
        ADD COLUMN IF NOT EXISTS embedding_dimensions INTEGER,
        ADD COLUMN IF NOT EXISTS embedding vector(1536)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding_cosine
        ON knowledge_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        WHERE embedding IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding_cosine")
    op.execute(
        """
        ALTER TABLE knowledge_chunks
        DROP COLUMN IF EXISTS embedding,
        DROP COLUMN IF EXISTS embedding_dimensions,
        DROP COLUMN IF EXISTS embedding_model_key
        """
    )
