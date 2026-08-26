"""add llm budget custom period

Revision ID: 0011_llm_budget_custom_period
Revises: 0010_llm_budget_ledger
Create Date: 2026-06-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_llm_budget_custom_period"
down_revision = "0010_llm_budget_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "llm_budgets",
        sa.Column("custom_period_start", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "llm_budgets",
        sa.Column("custom_period_end", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_llm_budgets_custom_period_start",
        "llm_budgets",
        ["custom_period_start"],
    )
    op.create_index(
        "ix_llm_budgets_custom_period_end",
        "llm_budgets",
        ["custom_period_end"],
    )


def downgrade() -> None:
    op.drop_index("ix_llm_budgets_custom_period_end", table_name="llm_budgets")
    op.drop_index("ix_llm_budgets_custom_period_start", table_name="llm_budgets")
    op.drop_column("llm_budgets", "custom_period_end")
    op.drop_column("llm_budgets", "custom_period_start")
