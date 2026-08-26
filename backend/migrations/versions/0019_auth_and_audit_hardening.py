"""add session revocation version and make audit logs immutable

Revision ID: 0019_auth_and_audit_hardening
Revises: 0018_agent_user_assignments
Create Date: 2026-07-19 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0019_auth_and_audit_hardening"
down_revision = "0018_agent_user_assignments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.drop_column("audit_logs", "updated_at")
    op.execute(
        """
        CREATE FUNCTION agenthive_reject_audit_log_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'AgentHive audit logs are immutable'
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_agenthive_audit_logs_immutable
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW
        EXECUTE FUNCTION agenthive_reject_audit_log_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_agenthive_audit_logs_immutable ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS agenthive_reject_audit_log_mutation()")
    op.add_column(
        "audit_logs",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.drop_column("users", "auth_version")
