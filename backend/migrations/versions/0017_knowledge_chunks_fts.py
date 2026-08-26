"""add fts_tsvector column to knowledge_chunks for hybrid retrieval

Revision ID: 0017_knowledge_chunks_fts
Revises: 0016_mcp_server_configs
Create Date: 2026-07-06 00:00:00.000000

Adds a tsvector column and GIN index to knowledge_chunks to enable
PostgreSQL full-text search alongside pgvector semantic search. The
tsvector is populated by the application layer (knowledge_service) using
a CJK-bigram-aware tokenizer so that Chinese text is properly segmented.
"""

from alembic import op
import sqlalchemy as sa

revision = "0017_knowledge_chunks_fts"
down_revision = "0016_mcp_server_configs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.add_column(
        "knowledge_chunks",
        sa.Column("fts_tsvector", sa.Text(), nullable=True),
    )
    # Cast to tsvector type after adding as text (avoids needing tsvector
    # column type in SQLAlchemy model).
    op.execute("ALTER TABLE knowledge_chunks ALTER COLUMN fts_tsvector TYPE tsvector USING fts_tsvector::tsvector")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_fts "
        "ON knowledge_chunks USING gin (fts_tsvector)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_fts")
    op.drop_column("knowledge_chunks", "fts_tsvector")
