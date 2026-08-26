"""add llm budget reservation ledger

Revision ID: 0010_llm_budget_ledger
Revises: 0009_llm_credential_secret_text
Create Date: 2026-06-12 00:00:00.000000
"""

from alembic import op


revision = "0010_llm_budget_ledger"
down_revision = "0009_llm_credential_secret_text"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE llm_budget_ledger (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            budget_id UUID REFERENCES llm_budgets(id),
            reservation_id VARCHAR(64) NOT NULL,
            request_id VARCHAR(64) NOT NULL,
            event_type VARCHAR(30) NOT NULL,
            scope_type VARCHAR(30) NOT NULL,
            scope_id UUID,
            user_id UUID REFERENCES users(id),
            department_id UUID REFERENCES departments(id),
            cost_center_id UUID REFERENCES cost_centers(id),
            agent_id UUID,
            channel_id UUID,
            conversation_id UUID REFERENCES conversation_sessions(id),
            estimated_tokens INTEGER NOT NULL DEFAULT 0,
            actual_tokens INTEGER NOT NULL DEFAULT 0,
            estimated_cost_usd NUMERIC(12,6) NOT NULL DEFAULT 0,
            actual_cost_usd NUMERIC(12,6) NOT NULL DEFAULT 0,
            reason VARCHAR(240),
            metadata_json JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_llm_budget_ledger_policy ON llm_budget_ledger "
        "(tenant_id, budget_id, created_at)"
    )
    op.execute(
        "CREATE INDEX ix_llm_budget_ledger_reservation ON llm_budget_ledger "
        "(tenant_id, reservation_id, event_type)"
    )
    op.execute(
        "CREATE INDEX ix_llm_budget_ledger_scope ON llm_budget_ledger "
        "(tenant_id, scope_type, scope_id, created_at)"
    )
    op.execute(
        "CREATE INDEX ix_llm_budget_ledger_request ON llm_budget_ledger "
        "(tenant_id, request_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS llm_budget_ledger CASCADE")
