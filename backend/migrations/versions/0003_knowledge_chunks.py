"""knowledge chunks

Revision ID: 0003_knowledge_chunks
Revises: 0002_knowledge_persistence
Create Date: 2026-06-09
"""

from alembic import op

revision = "0003_knowledge_chunks"
down_revision = "0002_knowledge_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_chunks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(id),
            document_id UUID NOT NULL REFERENCES knowledge_documents(id),
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            token_count INTEGER NOT NULL DEFAULT 0,
            source_name VARCHAR(255),
            search_text TEXT NOT NULL,
            metadata_json JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (document_id, chunk_index)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_base_document "
        "ON knowledge_chunks (tenant_id, knowledge_base_id, document_id, chunk_index)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_search_trgm "
        "ON knowledge_chunks USING gin (search_text gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS knowledge_chunks CASCADE")
