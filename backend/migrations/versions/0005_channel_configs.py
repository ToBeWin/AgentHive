"""add channel configs

Revision ID: 0005_channel_configs
Revises: 0004_llm_policies
Create Date: 2026-06-09
"""

from alembic import op

revision = "0005_channel_configs"
down_revision = "0004_llm_policies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE channel_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            name VARCHAR(120) NOT NULL,
            channel_type VARCHAR(40) NOT NULL,
            channel_key VARCHAR(120) NOT NULL,
            agent_id UUID,
            created_by UUID REFERENCES users(id),
            status VARCHAR(30) NOT NULL DEFAULT 'active',
            config JSONB NOT NULL DEFAULT '{}',
            secret_ref TEXT,
            secret_configured BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (channel_type, channel_key)
        )
        """
    )
    op.execute("CREATE INDEX ix_channel_configs_type_key ON channel_configs (channel_type, channel_key)")
    op.execute("CREATE INDEX ix_channel_configs_tenant_status ON channel_configs (tenant_id, status)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_channel_configs_tenant_status")
    op.execute("DROP INDEX IF EXISTS ix_channel_configs_type_key")
    op.execute("DROP TABLE IF EXISTS channel_configs")
