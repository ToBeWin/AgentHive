"""add agent_user_assignments table

Revision ID: 0018_agent_user_assignments
Revises: 0017_knowledge_chunks_fts
Create Date: 2026-07-06 00:00:00.000000

Adds the ``agent_user_assignments`` table that links users to agent
instances with a role (``owner`` / ``operator`` / ``viewer``) scoped to a
tenant. Used by the "My Agents" view and per-agent user management UI.
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_agent_user_assignments"
down_revision = "0017_knowledge_chunks_fts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_user_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agent_instances.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False, server_default="user"),
        # role: "owner" / "operator" / "viewer"
        sa.Column("assigned_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "agent_id",
            "user_id",
            name="uq_agent_user_tenant_agent_user",
        ),
    )
    op.create_index("ix_agent_user_tenant_id", "agent_user_assignments", ["tenant_id"])
    op.create_index("ix_agent_user_agent_id", "agent_user_assignments", ["agent_id"])
    op.create_index("ix_agent_user_user_id", "agent_user_assignments", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_user_user_id", table_name="agent_user_assignments")
    op.drop_index("ix_agent_user_agent_id", table_name="agent_user_assignments")
    op.drop_index("ix_agent_user_tenant_id", table_name="agent_user_assignments")
    op.drop_table("agent_user_assignments")
