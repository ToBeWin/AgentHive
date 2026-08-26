"""knowledge persistence

Revision ID: 0002_knowledge_persistence
Revises: 0001_initial_enterprise_core
Create Date: 2026-06-09
"""

from alembic import op

revision = "0002_knowledge_persistence"
down_revision = "0001_initial_enterprise_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_bases (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            name VARCHAR(120) NOT NULL,
            description TEXT,
            visibility VARCHAR(30) NOT NULL DEFAULT 'tenant',
            department_ids JSONB NOT NULL DEFAULT '[]',
            rag_engine VARCHAR(40) NOT NULL DEFAULT 'ragflow',
            embedding_model_key VARCHAR(120),
            retrieval_config JSONB NOT NULL DEFAULT '{}',
            status VARCHAR(30) NOT NULL DEFAULT 'active',
            document_count INTEGER NOT NULL DEFAULT 0,
            tags JSONB NOT NULL DEFAULT '[]',
            metadata_json JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            deleted_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_documents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(id),
            filename VARCHAR(255) NOT NULL,
            content_type VARCHAR(160),
            size_bytes BIGINT,
            checksum_sha256 VARCHAR(64),
            source VARCHAR(40) NOT NULL DEFAULT 'api_upload',
            status VARCHAR(40) NOT NULL DEFAULT 'pending_upload',
            storage_bucket VARCHAR(120) NOT NULL,
            storage_object_key VARCHAR(1024) NOT NULL,
            rag_document_id VARCHAR(255),
            chunk_count INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            metadata_json JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            deleted_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_bases_tenant_status "
        "ON knowledge_bases (tenant_id, status, updated_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_bases_tenant_visibility "
        "ON knowledge_bases (tenant_id, visibility)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_documents_base_status "
        "ON knowledge_documents (tenant_id, knowledge_base_id, status, updated_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_documents_checksum "
        "ON knowledge_documents (tenant_id, checksum_sha256)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS knowledge_documents CASCADE")
    op.execute("DROP TABLE IF EXISTS knowledge_bases CASCADE")
