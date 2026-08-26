"""add mcp_server_configs table for MCP tool integration

Revision ID: 0016_mcp_server_configs
Revises: 0015_channel_previous_secret_ref
Create Date: 2026-06-27 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0016_mcp_server_configs"
down_revision = "0015_channel_previous_secret_ref"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_server_configs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("server_key", sa.String(length=120), nullable=False),
        sa.Column("transport", sa.String(length=20), nullable=False, server_default="http"),
        sa.Column("endpoint_url", sa.String(length=1024), nullable=False),
        sa.Column("auth_ref", sa.String(length=4096), nullable=True),
        sa.Column("auth_configured", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("timeout_seconds", sa.Float(), nullable=False, server_default="30.0"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "server_key",
            name="uq_mcp_servers_tenant_key",
        ),
    )
    op.create_index(
        "ix_mcp_server_configs_tenant_id",
        "mcp_server_configs",
        ["tenant_id"],
    )
    op.create_index(
        "ix_mcp_server_configs_server_key",
        "mcp_server_configs",
        ["server_key"],
    )
    op.create_index(
        "ix_mcp_server_configs_status",
        "mcp_server_configs",
        ["status"],
    )
    op.create_index(
        "ix_mcp_server_configs_created_by",
        "mcp_server_configs",
        ["created_by"],
    )


def downgrade() -> None:
    op.drop_index("ix_mcp_server_configs_created_by", table_name="mcp_server_configs")
    op.drop_index("ix_mcp_server_configs_status", table_name="mcp_server_configs")
    op.drop_index("ix_mcp_server_configs_server_key", table_name="mcp_server_configs")
    op.drop_index("ix_mcp_server_configs_tenant_id", table_name="mcp_server_configs")
    op.drop_table("mcp_server_configs")
