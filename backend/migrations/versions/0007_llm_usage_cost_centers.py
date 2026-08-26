"""add cost center attribution to llm usage

Revision ID: 0007_llm_usage_cost_centers
Revises: 0006_agent_instances
Create Date: 2026-06-11
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_llm_usage_cost_centers"
down_revision = "0006_agent_instances"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llm_usage", sa.Column("cost_center_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_llm_usage_cost_center_id",
        "llm_usage",
        "cost_centers",
        ["cost_center_id"],
        ["id"],
    )
    op.create_index("ix_llm_usage_cost_center_id", "llm_usage", ["cost_center_id"])


def downgrade() -> None:
    op.drop_index("ix_llm_usage_cost_center_id", table_name="llm_usage")
    op.drop_constraint("fk_llm_usage_cost_center_id", "llm_usage", type_="foreignkey")
    op.drop_column("llm_usage", "cost_center_id")
