"""add llm policies

Revision ID: 0004_llm_policies
Revises: 0003_knowledge_chunks
Create Date: 2026-06-09
"""

from alembic import op

revision = "0004_llm_policies"
down_revision = "0003_knowledge_chunks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE llm_policies (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            name VARCHAR(120) NOT NULL,
            description TEXT,
            scope_type VARCHAR(30) NOT NULL,
            scope_id UUID,
            effect VARCHAR(20) NOT NULL DEFAULT 'allow',
            allowed_models JSONB NOT NULL DEFAULT '[]',
            allowed_routing_keys JSONB NOT NULL DEFAULT '[]',
            default_model_key VARCHAR(120),
            default_routing_key VARCHAR(120),
            max_tokens INTEGER,
            priority INTEGER NOT NULL DEFAULT 100,
            is_active BOOLEAN NOT NULL DEFAULT true,
            metadata_json JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (tenant_id, scope_type, scope_id, name)
        )
        """
    )
    op.execute("CREATE INDEX ix_llm_policies_tenant_scope ON llm_policies (tenant_id, scope_type, scope_id)")
    op.execute("CREATE INDEX ix_llm_policies_tenant_active_priority ON llm_policies (tenant_id, is_active, priority)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_llm_policies_tenant_active_priority")
    op.execute("DROP INDEX IF EXISTS ix_llm_policies_tenant_scope")
    op.execute("DROP TABLE IF EXISTS llm_policies")
