"""add tenant agent instances

Revision ID: 0006_agent_instances
Revises: 0005_channel_configs
Create Date: 2026-06-09
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_agent_instances"
down_revision = "0005_channel_configs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_instances",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("agent_key", sa.String(length=100), nullable=False),
        sa.Column("module_key", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("visibility", sa.String(length=30), nullable=False, server_default="tenant"),
        sa.Column("department_id", sa.Uuid(), nullable=True),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("model_routing_key", sa.String(length=120), nullable=True),
        sa.Column("model_key", sa.String(length=120), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_agent_instances_tenant_slug"),
    )
    op.create_index("ix_agent_instances_tenant_status", "agent_instances", ["tenant_id", "status"])
    op.create_index("ix_agent_instances_tenant_agent_key", "agent_instances", ["tenant_id", "agent_key"])
    op.create_index("ix_agent_instances_tenant_module_key", "agent_instances", ["tenant_id", "module_key"])


def downgrade() -> None:
    op.drop_index("ix_agent_instances_tenant_module_key", table_name="agent_instances")
    op.drop_index("ix_agent_instances_tenant_agent_key", table_name="agent_instances")
    op.drop_index("ix_agent_instances_tenant_status", table_name="agent_instances")
    op.drop_table("agent_instances")
