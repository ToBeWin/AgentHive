"""add license knowledge storage capacity

Revision ID: 0012_license_kb_capacity
Revises: 0011_llm_budget_custom_period
Create Date: 2026-06-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_license_kb_capacity"
down_revision = "0011_llm_budget_custom_period"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "licenses",
        sa.Column("max_kb_size_gb", sa.Numeric(10, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("licenses", "max_kb_size_gb")
